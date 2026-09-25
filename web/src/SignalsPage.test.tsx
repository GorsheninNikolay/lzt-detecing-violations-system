import { createRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SignalsPage from './SignalsPage'

const base = {
  zone_id: 'zone-1', revision_id: 'revision-1', work_entry_id: null, state: 'new', comment: '',
  basis: {}, created_at: '2026-09-25T11:00:00Z', project_name: 'Объект А', zone_name: 'Север',
} as const
const signal = (id: string, kind = 'completion_unconfirmed', extra = {}) => ({ ...base, id, kind, run_id: null, ...extra })
const json = (value: unknown) => ({ ok: true, json: async () => value })
const page = () => render(<SignalsPage heading={createRef<HTMLHeadingElement>()} onOpenRun={vi.fn()} />)

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); delete (URL as unknown as { createObjectURL?: unknown }).createObjectURL; delete (URL as unknown as { revokeObjectURL?: unknown }).revokeObjectURL })

describe('SignalsPage', () => {
  it('shows twenty rows, loads more, and filters by state', async () => {
    const records = Array.from({ length: 21 }, (_, index) => signal(`signal-${index}`))
    const fetchMock = vi.fn(async (url: string) => json({ new_count: 21, signals: url.includes('state=closed') ? [] : records }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    page()
    await waitFor(() => expect(document.querySelectorAll('.signals-row')).toHaveLength(20))
    await user.click(screen.getByRole('button', { name: 'Показать ещё' }))
    expect(document.querySelectorAll('.signals-row')).toHaveLength(21)
    await user.selectOptions(screen.getByLabelText('Показать'), 'closed')
    expect(await screen.findByText('Сигналов по выбранному фильтру нет.')).toBeTruthy()
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/signals?state=closed')).toBe(true)
  })

  it('loads the saved plan revision and a real preview, then revokes its URL', async () => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:signal-preview') })
    const revoke = vi.fn()
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke })
    const record = signal('signal-1', 'expected_equipment_missing', {
      run_id: 'run-1', revision_id: 'revision-2', plan_revision_number: 2, work_entry_id: 'entry-1', work_title: 'Подготовка',
      preview: { input_id: 'input-1', ordinal: 0, artifact_id: 'artifact-1' }, basis: { supporting_input_ids: ['input-1'], class_name: 'excavator' },
    })
    const fetchMock = vi.fn(async (url: string) => url === '/api/signals' ? json({ new_count: 1, signals: [record] })
      : url === '/api/runs/run-1/artifacts/artifact-1' ? { ok: true, blob: async () => new Blob(['image']) }
        : url === '/api/runs/run-1' ? json({ state: 'succeeded', inputs: [{ input_id: 'input-1' }], result_projection: { outcome: 'check_requested' } })
          : url === '/api/zones/zone-1/plan?revision=2' ? json({ revision_id: 'revision-2', revision_number: 2, entries: [{ id: 'entry-1', state: 'active', stage_key: 'excavation', starts_at: '2026-09-25T08:00:00Z', ends_at: '2026-09-25T18:00:00Z', expected_equipment: ['excavator'] }] })
            : { ok: false })
    vi.stubGlobal('fetch', fetchMock)
    const view = page()
    expect(await screen.findByAltText('Поддерживающий кадр 1')).toHaveProperty('src', 'blob:signal-preview')
    expect(await screen.findByText('Ожидается: Экскаватор')).toBeTruthy()
    expect(screen.getByText(/Итог: Рекомендована проверка человеком/)).toBeTruthy()
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/zones/zone-1/plan?revision=2')).toBe(true)
    view.unmount()
    expect(revoke).toHaveBeenCalledWith('blob:signal-preview')
  })

  it('labels a fallback analysis frame and rejects a plan with the wrong revision ID', async () => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:fallback') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    const record = signal('signal-1', 'stage_plan_mismatch', {
      run_id: 'run-1', revision_id: 'recorded-revision', plan_revision_number: 1, state: 'closed',
      preview: { input_id: 'input-1', ordinal: 2, artifact_id: 'artifact-1' },
    })
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/signals' ? json({ new_count: 0, signals: [record] })
      : url.includes('/artifacts/') ? { ok: true, blob: async () => new Blob(['image']) }
        : url.includes('/plan?') ? json({ revision_id: 'different-revision', revision_number: 1, entries: [{ id: 'wrong-entry' }] })
          : json({ state: 'succeeded', inputs: [], result_projection: { outcome: 'no_check' } })))
    page()
    expect(await screen.findByAltText('Кадр анализа 3')).toBeTruthy()
    expect(await screen.findByText('Полученная ревизия плана не совпадает с сигналом.')).toBeTruthy()
    expect(screen.queryByText('Работа 1')).toBeNull()
    expect(screen.getByText('Закрыт означает завершение ручной обработки, а не подтверждение безопасности.')).toBeTruthy()
  })

  it('preserves each comment across selection and filtering, including a failed save', async () => {
    const first = signal('signal-1')
    const second = signal('signal-2', 'insufficient_observations')
    let failSave = true
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') {
        if (failSave) { failSave = false; return { ok: false } }
        return json(JSON.parse(String(options.body)))
      }
      return json({ new_count: 2, signals: [first, second] })
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    page()
    await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    await user.type(screen.getByLabelText('Комментарий'), 'Первый черновик')
    await user.click(screen.getByRole('button', { name: /Недостаточно наблюдений.*Север/ }))
    await user.type(screen.getByLabelText('Комментарий'), 'Второй черновик')
    await user.selectOptions(screen.getByLabelText('Показать'), 'new')
    await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    await user.click(screen.getByRole('button', { name: /Недостаточно наблюдений.*Север/ }))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Второй черновик')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByText('Не удалось сохранить сигнал. Комментарий остался в черновике.')).toBeTruthy()
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Второй черновик')
    await user.click(screen.getByRole('button', { name: /Завершение не подтверждено.*Север/ }))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Первый черновик')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'PATCH')).toHaveLength(2))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === '/api/signals?state=new').length).toBeGreaterThan(1))
  })

  it('keeps a submitted draft stable while its save is pending', async () => {
    let finishSave!: (response: ReturnType<typeof json>) => void
    const pendingSave = new Promise<ReturnType<typeof json>>(resolve => { finishSave = resolve })
    vi.stubGlobal('fetch', vi.fn((_url: string, options?: RequestInit) => options?.method === 'PATCH'
      ? pendingSave : Promise.resolve(json({ new_count: 1, signals: [signal('signal-1')] }))))
    const user = userEvent.setup()
    page()
    await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    await user.type(screen.getByLabelText('Комментарий'), 'Черновик')
    await user.selectOptions(screen.getByLabelText('Состояние'), 'in_progress')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('disabled', true)
    expect(screen.getByLabelText('Состояние')).toHaveProperty('disabled', true)
    finishSave(json({ state: 'in_progress', comment: 'Черновик' }))
    await waitFor(() => expect(screen.getByLabelText('Комментарий')).toHaveProperty('disabled', false))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Черновик')
  })

  it('aborts old detail reads and ignores responses that arrive after selection changes', async () => {
    let releaseOld!: () => void
    const old = new Promise<void>(resolve => { releaseOld = resolve })
    const first = signal('signal-1', 'expected_equipment_missing', { run_id: 'run-1', revision_id: 'revision-1', plan_revision_number: 1 })
    const second = signal('signal-2', 'stage_plan_mismatch', { run_id: 'run-2', revision_id: 'revision-2', plan_revision_number: 2 })
    const fetchMock = vi.fn(async (url: string, _options?: RequestInit) => {
      if (url === '/api/signals') return json({ new_count: 2, signals: [first, second] })
      if (url.includes('run-1') || url.includes('revision=1')) {
        await old
        return url.includes('revision=1') ? json({ revision_id: 'revision-1', revision_number: 1, entries: [{ id: 'old', state: 'active', starts_at: '2026-09-25T08:00:00Z', ends_at: '2026-09-25T18:00:00Z', expected_equipment: ['dump_truck'] }] }) : json({ state: 'succeeded', inputs: [], result_projection: { outcome: 'no_check' } })
      }
      return url.includes('revision=2') ? json({ revision_id: 'revision-2', revision_number: 2, entries: [{ id: 'new', state: 'active', starts_at: '2026-09-25T08:00:00Z', ends_at: '2026-09-25T18:00:00Z', expected_equipment: ['excavator'] }] }) : json({ state: 'succeeded', inputs: [], result_projection: { outcome: 'check_requested' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    page()
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === '/api/runs/run-1')).toBe(true))
    await user.click(screen.getByRole('button', { name: /Этап расходится с планом.*Север/ }))
    expect(await screen.findByText('Ожидается: Экскаватор')).toBeTruthy()
    expect(fetchMock.mock.calls.find(([url]) => url === '/api/runs/run-1')?.[1]?.signal?.aborted).toBe(true)
    releaseOld()
    await waitFor(() => expect(screen.queryByText('Ожидается: Самосвал')).toBeNull())
    expect(screen.getByText(/Итог: Рекомендована проверка человеком/)).toBeTruthy()
  })

  it('places selected details directly after its row on a phone and explains a calendar signal', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    vi.stubGlobal('fetch', vi.fn(async () => json({ new_count: 1, signals: [signal('signal-1', 'completion_unconfirmed', { basis: { due_at: '2026-09-25T10:00:00Z' } })] })))
    page()
    const row = await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    const item = row.closest('li')!
    expect(within(item).getByRole('article')).toBeTruthy()
    expect(within(item).getByText('Сигнал сформирован по сроку плана. Связанных кадров нет.')).toBeTruthy()
    expect(within(item).getByText('Анализ не связан. Кадров нет.')).toBeTruthy()
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 })
    fireEvent(window, new Event('resize'))
  })
})
