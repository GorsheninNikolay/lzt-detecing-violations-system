vi.mock('./engagement', () => ({ startActivity: () => () => {}, track: async () => {}, attributionHeaders: () => ({}) }))

import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { EntryScene } from './VariantDesign'
import { MotionPreference } from './MotionPreference'

const firstId = 'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa'
const secondId = 'bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb'
const firstSha = 'a'.repeat(64)
const secondSha = 'b'.repeat(64)
const projects = [
  { id: firstId, name: 'Первый объект', timezone: 'UTC', cover_sha256: firstSha },
  { id: secondId, name: 'Второй объект', timezone: 'UTC', cover_sha256: null },
]
const json = (body: unknown) => ({ ok: true, json: async () => body })
const photo = () => new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'site.png', { type: 'image/png' })
const drawImage = vi.fn()
const fillRect = vi.fn()

beforeEach(() => {
  history.replaceState({}, '', '/')
  localStorage.setItem('construction-onboarding', 'completed')
  sessionStorage.clear()
  drawImage.mockClear()
  fillRect.mockClear()
  vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 3200, height: 1600, close: vi.fn() })))
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage, fillRect, fillStyle: '' } as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(callback => callback(new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], { type: 'image/jpeg' })))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.restoreAllMocks() })

it('shows a compact demo marker without the removed sentence', async () => {
  vi.stubEnv('MODE', 'demo')
  vi.stubGlobal('fetch', vi.fn(async () => json({ projects })))
  render(<App />)
  expect(await screen.findByText('Демо')).toBeTruthy()
  expect(screen.queryByText(/Демонстрация интерфейса · фотографии и разметка/)).toBeNull()
})

it('shows individual covers and updates only the uploaded project and its cube', async () => {
  let current = projects
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'PUT' && url === `/api/projects/${secondId}/cover`) {
      current = projects.map(item => item.id === secondId ? { ...item, cover_sha256: secondSha } : item)
      return json({ cover_sha256: secondSha })
    }
    return json({ projects: current })
  })
  vi.stubGlobal('fetch', fetcher)
  render(<App />)

  const input = await screen.findByLabelText('Загрузить обложку проекта Второй объект') as HTMLInputElement
  await waitFor(() => expect(input.disabled).toBe(false))
  const cards = document.querySelectorAll('.project-card')
  expect(cards).toHaveLength(2)
  expect(cards[0].querySelector('img.project-cover-photo')?.getAttribute('src')).toBe(`/api/projects/${firstId}/cover?revision=${firstSha}`)
  expect(cards[1].querySelector('img.project-cover-photo')).toBeNull()
  expect(document.querySelectorAll('.marquee-slot--filled')).toHaveLength(2)
  expect(document.querySelectorAll('.marquee-slot--empty')).toHaveLength(10)
  expect(document.querySelectorAll('.marquee-column:nth-child(1) .marquee-slot:nth-child(3).marquee-slot--photo')).toHaveLength(1)
  expect(document.querySelectorAll('.marquee-column:nth-child(2) .marquee-slot:nth-child(3).marquee-slot--filled')).toHaveLength(1)
  expect(document.querySelectorAll('.marquee-column:nth-child(1) .marquee-slot:nth-child(1).marquee-slot--empty')).toHaveLength(1)
  expect(screen.getByText('Обложки видны всем. Любой посетитель может их заменить.')).toBeTruthy()
  expect(screen.queryByText(/Демонстрация интерфейса · фотографии и разметка/)).toBeNull()

  await userEvent.setup().upload(input, photo())
  await waitFor(() => expect(cards[1].querySelector('img.project-cover-photo')?.getAttribute('src')).toBe(`/api/projects/${secondId}/cover?revision=${secondSha}`))
  expect(cards[0].querySelector('img.project-cover-photo')?.getAttribute('src')).toBe(`/api/projects/${firstId}/cover?revision=${firstSha}`)
  expect(document.querySelectorAll('.marquee-cover-photo')).toHaveLength(2)
  const request = fetcher.mock.calls.find(([url, options]) => url === `/api/projects/${secondId}/cover` && options?.method === 'PUT')
  expect(request?.[1]?.headers).toMatchObject({ 'Idempotency-Key': expect.any(String) })
  expect(JSON.parse(String(request?.[1]?.body))).toEqual({ data: '/9j/2Q==' })
  expect(drawImage).toHaveBeenCalledWith(expect.objectContaining({ width: 3200, height: 1600 }), 0, 0, 1600, 800)
  expect(fillRect).toHaveBeenCalledWith(0, 0, 1600, 800)
  expect(HTMLCanvasElement.prototype.toBlob).toHaveBeenCalledWith(expect.any(Function), 'image/jpeg', 0.82)
})

it('rejects unsupported or oversized covers before upload', async () => {
  const fetcher = vi.fn(async (_url: string, _options?: RequestInit) => json({ projects }))
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  const input = await screen.findByLabelText('Загрузить обложку проекта Второй объект') as HTMLInputElement
  await waitFor(() => expect(input.disabled).toBe(false))
  fireEvent.change(input, { target: { files: [new File(['image'], 'site.gif', { type: 'image/gif' })] } })
  expect(await screen.findByText('Выберите фотографию JPEG, PNG или WEBP.')).toBeTruthy()
  fireEvent.change(input, { target: { files: [new File([new Uint8Array(5_000_001)], 'large.png', { type: 'image/png' })] } })
  expect(await screen.findByText('Размер фотографии должен быть не больше 5 МБ.')).toBeTruthy()
  expect(fetcher.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false)
})

it('does not send a cover when browser storage cannot preserve its retry request', async () => {
  const fetcher = vi.fn(async (_url: string, _options?: RequestInit) => json({ projects }))
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  const input = await screen.findByLabelText('Загрузить обложку проекта Второй объект') as HTMLInputElement
  await waitFor(() => expect(input.disabled).toBe(false))
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota') })
  vi.stubGlobal('indexedDB', { open: () => { throw new Error('blocked') } })
  await userEvent.setup().upload(input, photo())
  expect(await screen.findByText(/Новая обложка не отправлена: браузер не смог сохранить запрос/)).toBeTruthy()
  expect(fetcher.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false)
  expect(screen.queryByRole('button', { name: 'Повторить отправку обложки' })).toBeNull()
})

it('rejects a corrupt image and oversized normalized JPEG before saving or sending', async () => {
  const fetcher = vi.fn(async (_url: string, _options?: RequestInit) => json({ projects }))
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  const input = await screen.findByLabelText('Загрузить обложку проекта Второй объект') as HTMLInputElement
  await waitFor(() => expect(input.disabled).toBe(false))
  vi.stubGlobal('createImageBitmap', vi.fn(async () => { throw new Error('decode_failed') }))
  await userEvent.setup().upload(input, photo())
  expect(await screen.findByText(/Не удалось прочитать фотографию/)).toBeTruthy()
  expect(fetcher.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false)

  vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 1600, height: 1200, close: vi.fn() })))
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(callback => callback(new Blob([new Uint8Array(5_000_001)], { type: 'image/jpeg' })))
  await userEvent.setup().upload(input, new File(['different'], 'other.png', { type: 'image/png' }))
  expect(await screen.findByText('После подготовки фотография больше 5 МБ. Выберите другое изображение.')).toBeTruthy()
  expect(fetcher.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false)
})

it('retries an unknown outcome after remount with the exact body and key', async () => {
  let uploads = 0
  let current = projects
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url === `/api/projects/${secondId}/cover` && options?.method === 'PUT') {
      uploads += 1
      if (uploads === 1) throw new Error('connection_lost')
      current = projects.map(item => item.id === secondId ? { ...item, cover_sha256: secondSha } : item)
      return json({ cover_sha256: secondSha })
    }
    return json({ projects: current })
  })
  vi.stubGlobal('fetch', fetcher)
  const view = render(<App />)
  const input = await screen.findByLabelText('Загрузить обложку проекта Второй объект') as HTMLInputElement
  await waitFor(() => expect(input.disabled).toBe(false))
  await userEvent.setup().upload(input, photo())
  expect(await screen.findByText(/Ответ сервера не получен/)).toBeTruthy()
  view.unmount()

  render(<App />)
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Повторить отправку обложки' }))
  await waitFor(() => expect(document.querySelectorAll('img.project-cover-photo')).toHaveLength(2))
  const requests = fetcher.mock.calls.filter(([url, options]) => url === `/api/projects/${secondId}/cover` && options?.method === 'PUT')
  expect(requests).toHaveLength(2)
  expect(requests[1][1]?.body).toBe(requests[0][1]?.body)
  expect((requests[1][1]?.headers as Record<string, string>)['Idempotency-Key']).toBe((requests[0][1]?.headers as Record<string, string>)['Idempotency-Key'])
})

it('shows the current cover after a replay whose original result was superseded', async () => {
  const latestSha = 'c'.repeat(64)
  const fetcher = vi.fn(async (url: string, options?: RequestInit) =>
    options?.method === 'PUT' && url === `/api/projects/${secondId}/cover`
      ? json({ cover_sha256: secondSha })
      : json({ projects: projects.map(item => item.id === secondId ? { ...item, cover_sha256: latestSha } : item) }))
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  const input = await screen.findByLabelText('Загрузить обложку проекта Второй объект') as HTMLInputElement
  await waitFor(() => expect(input.disabled).toBe(false))
  await userEvent.setup().upload(input, photo())
  expect(await screen.findByText('Другой посетитель уже заменил обложку. Показана актуальная фотография.')).toBeTruthy()
  const second = document.querySelectorAll('.project-card')[1]
  expect(second.querySelector('img.project-cover-photo')?.getAttribute('src')).toBe(`/api/projects/${secondId}/cover?revision=${latestSha}`)
})

it('keeps an outlined slot for every unfilled position beyond the initial twelve', () => {
  localStorage.setItem('analysis-motion', 'off')
  const many = Array.from({ length: 13 }, (_, index) => ({ id: String(index), name: `Объект ${index}` }))
  const { container } = render(<MotionPreference><EntryScene projects={many} /></MotionPreference>)
  expect(container.querySelectorAll('.marquee-slot--filled')).toHaveLength(13)
  expect(container.querySelectorAll('.marquee-slot--empty')).toHaveLength(3)
  expect(container.querySelector('.marquee-scene')?.getAttribute('data-moving')).toBe('false')
})
