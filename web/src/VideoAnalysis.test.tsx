import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearPendingVideo, restorePendingVideo, savePendingVideo, videoScope } from './videoRecovery'
import { VideoAnalysisForm, VideoResult } from './VideoAnalysis'

const pending = vi.hoisted(() => new Map<string, unknown>())
vi.mock('./videoRecovery', () => ({
  videoScope: (account: string, project: string) => JSON.stringify([account, project]),
  savePendingVideo: vi.fn(async (scope: string, value: unknown) => { const existing = pending.get(scope); if (existing) return existing; pending.set(scope, value); return value }),
  restorePendingVideo: vi.fn(async (scope: string) => pending.get(scope) ?? null),
  clearPendingVideo: vi.fn(async (scope: string, key: string) => { if ((pending.get(scope) as { key: string } | undefined)?.key === key) { pending.delete(scope); return true } return false }),
}))
afterEach(() => { cleanup(); pending.clear(); localStorage.clear(); vi.clearAllMocks(); vi.unstubAllGlobals() })
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
describe('video analysis', () => {
  it('automatically consents and preserves the upload key after an unknown response', async () => {
    const requests: RequestInit[] = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
      if (_url.includes('/plan')) return json({ revision_number: 0 })
      if (!init?.method) return json({ zones: [{ id: 'zone', name: 'Участок' }] })
      requests.push(init!)
      if (requests.length === 1) throw new TypeError('network')
      return json({ run_id: 'video-run' })
    }))
    const open = vi.fn()
    render(<VideoAnalysisForm projectId="project" onOpen={open} onDirty={() => {}} />)
    await screen.findByRole('option', { name: 'Участок' })
    const submit = screen.getByRole('button', { name: 'Запустить анализ видео' }) as HTMLButtonElement
    fireEvent.change(document.getElementById('video-file')!, { target: { files: [new File(['video'], 'site.mp4', { type: 'video/mp4' })] } })
    await waitFor(() => expect(submit.disabled).toBe(false))
    expect(screen.queryByRole('checkbox', { name: /Разрешаю отправить/ })).toBeNull()
    fireEvent.click(submit)
    await screen.findByRole('button', { name: 'Восстановить отправку' })
    fireEvent.click(screen.getByRole('button', { name: 'Восстановить отправку' }))
    await waitFor(() => expect(open).toHaveBeenCalledWith('/runs/video-run'))
    expect((vi.mocked(fetch).mock.calls.find(([url, init]) => String(url).includes('/runs/video') && init?.method)?.[0] as string)).toContain('cloud_processing_consent=true')
    expect(requests[0].body).toBe(requests[1].body)
    expect(requests[0].headers).toEqual(requests[1].headers)
  })
  it('rejects a wrong format before upload', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    render(<VideoAnalysisForm projectId="" onOpen={() => {}} onDirty={() => {}} />)
    await waitFor(() => expect((document.getElementById('video-file') as HTMLInputElement).disabled).toBe(false))
    fireEvent.change(document.getElementById('video-file')!, { target: { files: [new File(['x'], 'site.avi')] } })
    expect(screen.getByRole('alert').textContent).toContain('MP4 и MOV')
    expect(fetch).not.toHaveBeenCalled()
    expect(savePendingVideo).not.toHaveBeenCalled()
  })
  it('keeps a partial YOLO video available when explanation fails and seeks to selected moments', async () => {
    const snapshot = { state: 'failed', stage: 'deepseek', error: 'DeepSeek недоступен', result: { video_url: '/api/video-runs/run/media', selected_frames: [{ timestamp_seconds: 5.25 }] } }
    vi.stubGlobal('fetch', vi.fn(async () => json(snapshot)))
    render(<VideoResult runId="run" initial={snapshot} readOnly={false} onOpen={() => {}} />)
    expect(screen.getByRole('status').textContent).toBe('Обработка остановлена')
    expect(screen.getByRole('link', { name: 'Скачать MP4 с рамками' }).getAttribute('href')).toBe('/api/video-runs/run/media')
    fireEvent.click(screen.getByRole('button', { name: '5.25 с' }))
    expect((screen.getByLabelText('Видео с рамками двух YOLO') as HTMLVideoElement).currentTime).toBe(5.25)
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Обратитесь к администратору'))
  })
  it('retains the original file/query across unmount and prevents late upload navigation', async () => {
    let resolveUpload!: (response: Response) => void
    const writes: { url: string; init: RequestInit }[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (!init?.method) return json(url.includes('/plan') ? { revision_number: 0 } : { zones: [{ id: 'zone', name: 'Участок' }] })
      writes.push({ url, init })
      if (writes.length === 1) return new Promise<Response>(resolve => { resolveUpload = resolve })
      return json({ run_id: 'restored' })
    }))
    const open = vi.fn()
    const first = render(<VideoAnalysisForm accountId="alice" projectId="project" onOpen={open} onDirty={() => {}} />)
    await waitFor(() => expect((document.getElementById('video-file') as HTMLInputElement).disabled).toBe(false))
    fireEvent.change(document.getElementById('video-file')!, { target: { files: [new File(['payload'], 'site.mov')] } })
    await waitFor(() => expect((screen.getByRole('button', { name: 'Запустить анализ видео' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Запустить анализ видео' }))
    await waitFor(() => expect(writes).toHaveLength(1))
    first.unmount()
    expect((writes[0].init.signal as AbortSignal).aborted).toBe(true)
    resolveUpload(json({ run_id: 'late' }))
    await Promise.resolve()
    expect(open).not.toHaveBeenCalled()
    expect(await restorePendingVideo(videoScope('bob', 'project'))).toBe(null)
    expect(await restorePendingVideo(videoScope('alice', 'other-project'))).toBe(null)
    render(<VideoAnalysisForm accountId="alice" projectId="project" provider="changed" onOpen={open} onDirty={() => {}} />)
    const restore = await screen.findByRole('button', { name: 'Восстановить отправку' })
    fireEvent.click(restore)
    await waitFor(() => expect(open).toHaveBeenCalledWith('/runs/restored'))
    expect(writes[1].url).toBe(writes[0].url)
    expect(writes[1].init.body).toBe(writes[0].init.body)
    expect(writes[1].init.headers).toEqual(writes[0].init.headers)
    expect(clearPendingVideo).toHaveBeenCalledWith(videoScope('alice', 'project'), (writes[0].init.headers as Record<string, string>)['Idempotency-Key'])
  })
  it('never uploads if recovery storage cannot commit', async () => {
    vi.mocked(savePendingVideo).mockRejectedValueOnce(new Error('quota'))
    const fetch = vi.fn(async (url: string) => json(url.includes('/plan') ? { revision_number: 0 } : { zones: [{ id: 'zone', name: 'Участок' }] }))
    vi.stubGlobal('fetch', fetch)
    render(<VideoAnalysisForm projectId="project" onOpen={() => {}} onDirty={() => {}} />)
    await waitFor(() => expect((document.getElementById('video-file') as HTMLInputElement).disabled).toBe(false))
    fireEvent.change(document.getElementById('video-file')!, { target: { files: [new File(['payload'], 'site.mp4')] } })
    await waitFor(() => expect((screen.getByRole('button', { name: 'Запустить анализ видео' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Запустить анализ видео' }))
    await screen.findByRole('alert')
    expect(fetch.mock.calls.every(call => !call[0].includes('/runs/video?'))).toBe(true)
  })
  it('aborts CPU retry and suppresses late navigation after unmount', async () => {
    let resolveRetry!: (response: Response) => void
    let retrySignal: AbortSignal | undefined
    const snapshot = { state: 'failed', retry_cpu_eligible: true }
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') { retrySignal = init.signal as AbortSignal; return new Promise<Response>(resolve => { resolveRetry = resolve }) }
      return json(snapshot)
    }))
    const open = vi.fn()
    const view = render(<VideoResult runId="run" initial={snapshot} readOnly={false} onOpen={open} />)
    fireEvent.click(screen.getByRole('button', { name: 'Повторить обработку' }))
    await waitFor(() => expect(retrySignal).toBeDefined())
    view.unmount()
    expect(retrySignal!.aborted).toBe(true)
    resolveRetry(json({ run_id: 'late' }))
    await Promise.resolve()
    expect(open).not.toHaveBeenCalled()
  })

  it('reuses the CPU retry key after an unknown outcome and reload', async () => {
    const keys: string[] = []
    const snapshot = { state: 'failed', retry_cpu_eligible: true }
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        keys.push((init.headers as Record<string, string>)['Idempotency-Key'])
        if (keys.length === 1) throw new TypeError('lost response')
        return json({ run_id: 'cpu-restored' })
      }
      return json(snapshot)
    }))
    const open = vi.fn()
    const first = render(<VideoResult runId="run" initial={snapshot} readOnly={false} onOpen={open} />)
    fireEvent.click(screen.getByRole('button', { name: 'Повторить обработку' }))
    await screen.findByRole('alert')
    first.unmount()
    render(<VideoResult runId="run" initial={snapshot} readOnly={false} onOpen={open} />)
    fireEvent.click(screen.getByRole('button', { name: 'Повторить обработку' }))
    await waitFor(() => expect(open).toHaveBeenCalledWith('/runs/cpu-restored'))
    expect(keys).toHaveLength(2)
    expect(keys[1]).toBe(keys[0])
  })

  it('recovers another tab request without transmitting the replacement file', async () => {
    const writes: RequestInit[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') writes.push(init)
      return json(url.includes('/plan') ? { revision_number: 0 } : { zones: [{ id: 'zone', name: 'Участок' }] })
    }))
    render(<VideoAnalysisForm accountId="alice" projectId="project" onOpen={() => {}} onDirty={() => {}} />)
    await waitFor(() => expect((document.getElementById('video-file') as HTMLInputElement).disabled).toBe(false))
    fireEvent.change(document.getElementById('video-file')!, { target: { files: [new File(['new'], 'replacement.mp4')] } })
    await waitFor(() => expect((screen.getByRole('button', { name: 'Запустить анализ видео' }) as HTMLButtonElement).disabled).toBe(false))
    const original = { key: 'other-tab', query: 'project_id=project&zone_id=zone&cloud_provider=deepseek', file: new File(['original'], 'original.mov') }
    pending.set(videoScope('alice', 'project'), original)
    fireEvent.click(screen.getByRole('button', { name: 'Запустить анализ видео' }))
    expect((await screen.findByRole('alert')).textContent).toContain('В другой вкладке')
    expect(screen.getByRole('status').textContent).toContain('original.mov')
    expect(writes).toHaveLength(0)
    expect(pending.get(videoScope('alice', 'project'))).toBe(original)
  })

})
