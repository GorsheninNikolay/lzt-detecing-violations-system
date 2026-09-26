vi.mock('./engagement', () => ({ startActivity: () => () => {}, track: async () => {}, attributionHeaders: () => ({}) }))
beforeEach(() => localStorage.setItem('construction-onboarding', 'completed'))
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import demoCases from './demoCases.json'

const a = 'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa'
const b = 'bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb'
const zone = 'cccccccc-cccc-4ccc-cccc-cccccccccccc'
const run = 'dddddddd-dddd-4ddd-dddd-dddddddddddd'
const projects = [{ id: a, name: 'Первый объект', timezone: 'UTC' }, { id: b, name: 'Второй объект', timezone: 'UTC' }]
const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
const file = () => new File([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], 'photo.jpg', { type: 'image/jpeg' })
const reads = (url: string) => url === '/api/projects' ? json({ projects })
  : url.includes('/zones') && !url.includes('/plan') ? json({ zones: [{ id: zone, name: 'Основной участок' }] })
    : url.includes('/plan') ? json({ revision_number: 0, entries: [] })
      : url === '/api/catalog/works' ? json({ works: [] })
        : url.includes('/signals') ? json({ new_count: 0, signals: [] })
          : url.includes('/runs?') ? json({ total: 0, runs: [], next_offset: null })
            : json({ run_id: run, project_id: a, state: 'queued', stages: [], context: { project_id: a } })

beforeEach(() => {
  sessionStorage.clear()
  history.replaceState({}, '', `/projects/${a}/new`)
  vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: null }])
  vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 10, height: 10, close() {} })))
  vi.stubGlobal('fetch', vi.fn(async (url: string) => reads(url)))
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:photo')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('creates a project from an empty shared list with browser timezone', async () => {
  history.replaceState({}, '', '/')
  const user = userEvent.setup()
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => url === '/api/projects' ? options?.method === 'POST' ? json(projects[0], 201) : json({ projects: [] }) : reads(url))
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  expect(await screen.findByText(/Проектов пока нет/)).toBeTruthy()
  await user.type(screen.getByLabelText('Название проекта'), 'Первый объект')
  await user.click(screen.getByRole('button', { name: 'Создать проект' }))
  await waitFor(() => expect(location.pathname).toBe(`/projects/${a}`))
  const post = fetcher.mock.calls.find(([, options]) => options?.method === 'POST')!
  expect(JSON.parse(String(post[1]?.body))).toEqual({ name: 'Первый объект', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })
})

it('submits photos without a plan with immutable workspace and frame times', async () => {
  const user = userEvent.setup()
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => options?.method === 'POST' ? json({ run_id: run }, 202) : reads(url))
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  await screen.findByText('Плана пока нет. Можно анализировать фотографии и добавить план позже.')
  await waitFor(() => expect(screen.getByLabelText('Участок')).toHaveProperty('value', zone))
  await user.upload(screen.getByLabelText('Выбрать изображение'), file())
  fireEvent.change(await screen.findByLabelText('Время съёмки'), { target: { value: '2026-09-26T12:30' } })
  await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
  await waitFor(() => expect(location.pathname).toBe(`/projects/${a}/runs/${run}`))
  const request = fetcher.mock.calls.find(([, options]) => options?.method === 'POST')!
  const body = JSON.parse(String(request[1]?.body))
  expect(body).toMatchObject({ project_id: a, zone_id: zone, intent: 'observation_only', scenario: 'Наблюдение за строительством', observation_area: 'Основной участок', capture_times: [expect.stringMatching(/^2026-09-26T12:30:00/)] })
  expect(body.plan_revision_id).toBeUndefined()
})

it('retains upload on declined project switch and clears it after accepted switch', async () => {
  const user = userEvent.setup()
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  render(<App />)
  await screen.findByText('Первый объект', { selector: 'strong' })
  await user.upload(screen.getByLabelText('Выбрать изображение'), file())
  await user.selectOptions(screen.getByLabelText('Выбрать проект'), b)
  expect(location.pathname).toBe(`/projects/${a}/new`)
  expect(screen.getByText('photo.jpg')).toBeTruthy()
  confirm.mockReturnValue(true)
  await user.selectOptions(screen.getByLabelText('Выбрать проект'), b)
  await waitFor(() => expect(location.pathname).toBe(`/projects/${b}`))
  expect(screen.queryByText('photo.jpg')).toBeNull()
})

it('recovers the exact request and original workspace from another URL', async () => {
  history.replaceState({}, '', `/projects/${b}/new`)
  const saved = { endpoint: '/api/runs/single-image', key: 'same-key', body: JSON.stringify({ project_id: a, zone_id: zone, capture_times: ['2026-09-26T12:30:00+03:00'], image_base64: 'unchanged' }) }
  sessionStorage.setItem('observation-pending', JSON.stringify(saved))
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => options?.method === 'POST' ? json({ run_id: run }, 202) : reads(url))
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  await waitFor(() => expect(location.pathname).toBe(`/projects/${a}/new`))
  fireEvent.click(await screen.findByRole('button', { name: 'Повторить отправку' }))
  await waitFor(() => expect(location.pathname).toBe(`/projects/${a}/runs/${run}`))
  const request = fetcher.mock.calls.find(([, options]) => options?.method === 'POST')!
  expect(request[1]?.body).toBe(saved.body)
  expect(request[1]?.headers).toMatchObject({ 'Idempotency-Key': saved.key })
})

it('resolves a wrong project run URL to server ownership before showing the result', async () => {
  history.replaceState({}, '', `/projects/${b}/runs/${run}`)
  render(<App />)
  await waitFor(() => expect(location.pathname).toBe(`/projects/${a}/runs/${run}`))
  expect(await screen.findByRole('heading', { name: 'Анализ поставлен в очередь' })).toBeTruthy()
})

it('aborts old project history and ignores its late response', async () => {
  history.replaceState({}, '', `/projects/${a}/analyses`)
  let finish!: (result: unknown) => void
  let signal: AbortSignal | undefined
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    if (url === `/api/runs?project_id=${a}`) { signal = options?.signal as AbortSignal; return new Promise(resolve => { finish = resolve }) }
    return Promise.resolve(reads(url))
  })
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  await waitFor(() => expect(finish).toBeTruthy())
  fireEvent.change(await screen.findByLabelText('Выбрать проект'), { target: { value: b } })
  await waitFor(() => expect(signal?.aborted).toBe(true))
  await act(async () => finish(json({ total: 1, runs: [{ id: run, state: 'queued' }], next_offset: null })))
  expect(location.pathname).toBe(`/projects/${b}`)
  expect(screen.queryByRole('link', { name: 'Открыть анализ' })).toBeNull()
})

it('shows explicit unknown project and keeps orphan archive separate', async () => {
  history.replaceState({}, '', `/projects/${run}`)
  const view = render(<App />)
  expect(await screen.findByRole('heading', { name: 'Проект не найден' })).toBeTruthy()
  view.unmount()
  history.replaceState({}, '', '/archive')
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Архив без проекта' })).toBeTruthy()
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => url === '/api/runs?unassigned=true')).toBe(true))
})

it('preserves a conflicting plan draft and guards browser Back', async () => {
  history.replaceState({}, '', `/projects/${b}`)
  history.pushState({}, '', `/projects/${a}/plan`)
  const work = 'eeeeeeee-eeee-4eee-eeee-eeeeeeeeeeee'
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => url === '/api/catalog/works'
    ? json({ works: [{ id: work, code: '1', source_row: 4, title: 'Подготовка' }] })
    : options?.method === 'PUT' ? json({ code: 'plan_revision_conflict' }, 409) : reads(url)))
  const user = userEvent.setup()
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Добавить работу' }))
  await user.selectOptions(screen.getByLabelText('Состояние'), 'active')
  await user.click(screen.getByRole('button', { name: 'Сохранить новую ревизию' }))
  expect(await screen.findByText(/План уже изменён/)).toBeTruthy()
  expect(screen.getByLabelText('Состояние')).toHaveProperty('value', 'active')
  await act(async () => { history.back(); await new Promise(resolve => setTimeout(resolve, 30)) })
  await waitFor(() => expect(confirm).toHaveBeenCalled())
  expect(location.pathname).toBe(`/projects/${a}/plan`)
  expect(screen.getByLabelText('Состояние')).toHaveProperty('value', 'active')
  confirm.mockReturnValue(true)
  await user.selectOptions(screen.getByLabelText('Выбрать проект'), b)
  await waitFor(() => expect(location.pathname).toBe(`/projects/${b}`))
  expect(screen.queryByLabelText('Состояние')).toBeNull()
})

it('ignores a slow area response after switching to another project', async () => {
  let finish!: (value: unknown) => void
  vi.stubGlobal('fetch', vi.fn((url: string) => url === `/api/projects/${a}/zones`
    ? new Promise(resolve => { finish = resolve }) : Promise.resolve(reads(url))))
  render(<App />)
  await waitFor(() => expect(finish).toBeTruthy())
  fireEvent.change(screen.getByLabelText('Выбрать проект'), { target: { value: b } })
  await act(async () => finish(json({ zones: [{ id: zone, name: 'Старый участок A' }] })))
  await screen.findByRole('heading', { name: 'Второй объект' })
  expect(screen.queryByText('Старый участок A')).toBeNull()
})

it('fences delayed file validation across projects', async () => {
  let finish!: (value: unknown) => void
  vi.stubGlobal('createImageBitmap', vi.fn(() => new Promise(resolve => { finish = resolve })))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const user = userEvent.setup()
  render(<App />)
  await user.upload(screen.getByLabelText('Выбрать изображение'), file())
  await waitFor(() => expect(finish).toBeTruthy())
  await user.selectOptions(screen.getByLabelText('Выбрать проект'), b)
  await user.click(screen.getByRole('link', { name: 'Загрузить фотографии' }))
  await act(async () => finish({ width: 10, height: 10, close() {} }))
  expect(screen.queryByText('photo.jpg')).toBeNull()
  expect(screen.getByLabelText('Выбрать изображение')).toHaveProperty('disabled', false)
})

it('shows pending recovery only in its original project and fences late accepted navigation', async () => {
  const saved = { endpoint: '/api/runs/single-image', key: 'pending-a', body: JSON.stringify({ project_id: a }) }
  sessionStorage.setItem('observation-pending', JSON.stringify(saved))
  let finish!: (value: unknown) => void
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => options?.method === 'POST'
    ? new Promise(resolve => { finish = resolve }) : Promise.resolve(url === '/api/catalog/works' ? json({ works: [{ id: run, title: 'Работа B', source_row: 4 }] }) : reads(url))))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Повторить отправку' }))
  await user.selectOptions(screen.getByLabelText('Выбрать проект'), b)
  await user.click(screen.getByRole('link', { name: 'Загрузить фотографии' }))
  expect(screen.queryByRole('button', { name: 'Повторить отправку' })).toBeNull()
  expect(document.getElementById('submit-action')).toHaveProperty('disabled', true)
  expect(screen.getByRole('link', { name: 'Вернуться к отправке' }).getAttribute('href')).toBe(`/projects/${a}/new`)
  await user.click(screen.getAllByRole('link', { name: 'План работ' })[0])
  await user.click(await screen.findByRole('button', { name: 'Добавить работу' }))
  await user.selectOptions(screen.getByLabelText('Состояние'), 'active')
  await act(async () => finish(json({ run_id: run }, 202)))
  expect(location.pathname).toBe(`/projects/${b}/plan`)
  expect(screen.getByLabelText('Состояние')).toHaveProperty('value', 'active')
  expect(sessionStorage.getItem('observation-pending')).toBe(JSON.stringify(saved))
})

it('resets optional comparison when switching to an area without a plan', async () => {
  const secondZone = 'eeeeeeee-eeee-4eee-eeee-eeeeeeeeeeee'
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/zones')
    ? json({ zones: [{ id: zone, name: 'С планом' }, { id: secondZone, name: 'Без плана' }] })
    : url === `/api/zones/${zone}/plan` ? json({ revision_id: run, revision_number: 1, entries: [] }) : reads(url)))
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByLabelText('Сопоставить с сохранённым планом'))
  await user.selectOptions(screen.getByLabelText('Участок'), secondZone)
  expect(await screen.findByText('Плана пока нет. Можно анализировать фотографии и добавить план позже.')).toBeTruthy()
  expect(screen.queryByLabelText('Сопоставить с сохранённым планом')).toBeNull()
  await user.upload(screen.getByLabelText('Выбрать изображение'), file())
  await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true))
  const post = vi.mocked(fetch).mock.calls.find(([, options]) => options?.method === 'POST')!
  expect(JSON.parse(String(post[1]?.body)).plan_revision_id).toBeUndefined()
})

it('displays immutable saved work and no-plan per-frame capture time', async () => {
  history.replaceState({}, '', `/projects/${a}/runs/${run}`)
  const capture = '2026-09-26T12:30:00+03:00'
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${run}` ? json({
    run_id: run, project_id: a, state: 'succeeded', stages: [],
    context: { project_id: a, capture_times: [capture] },
    inputs: [{ input_id: 'frame', ordinal: 0, artifact_id: null, sha256: 'hash' }],
    result_projection: { outcome: 'observations_only', frames: [{ input_id: 'frame', ordinal: 0, class_name: 'excavator', state: 'detected', source_artifact_id: null }] },
    plan_binding: null,
  }) : reads(url)))
  const view = render(<App />)
  await screen.findByText(/Время съёмки:/)
  expect(view.container.querySelector(`time[datetime="${capture}"]`)).toBeTruthy()
  view.unmount()
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${run}` ? json({
    run_id: run, project_id: a, state: 'succeeded', stages: [], context: { project_id: a },
    plan_binding: { zone_id: zone, revision_id: 'revision-1', capture_times: [capture] },
    planned_works: [{ title: 'Работа первой версии', stage_key: 'excavation', starts_at: capture, ends_at: '2026-09-27T12:30:00+03:00', state: 'active' }],
  }) : url.includes('/plan') ? json({ revision_number: 2, entries: [] }) : reads(url)))
  render(<App />)
  expect(await screen.findByText(/Работа первой версии: Земляные работы/)).toBeTruthy()
  expect(screen.queryByText('В выбранной версии плана нет работ.')).toBeNull()
})

it('locks plan editing while loading and confirms before creating another area', async () => {
  history.replaceState({}, '', `/projects/${a}/plan`)
  let finish!: (value: unknown) => void
  const fetcher = vi.fn((url: string) => url === `/api/zones/${zone}/plan`
    ? new Promise(resolve => { finish = resolve }) : Promise.resolve(url === '/api/catalog/works' ? json({ works: [{ id: run, title: 'Работа', source_row: 4 }] }) : reads(url)))
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  render(<App />)
  await waitFor(() => expect(finish).toBeTruthy())
  expect(screen.getByRole('button', { name: 'Добавить работу' })).toHaveProperty('disabled', true)
  expect(screen.getByLabelText('Участок')).toHaveProperty('disabled', true)
  await act(async () => finish(json({ revision_number: 0, entries: [] })))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Добавить работу' })).toHaveProperty('disabled', false))
  await user.click(screen.getByRole('button', { name: 'Добавить работу' }))
  expect(screen.getByLabelText('Работа каталога')).toBeTruthy()
  await user.type(screen.getByLabelText('Новый участок'), 'Другой')
  await user.click(screen.getByRole('button', { name: 'Создать участок' }))
  expect(confirm).toHaveBeenCalled()
  expect(screen.getByLabelText('Работа каталога')).toBeTruthy()
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/zones'))).toHaveLength(1)
})

it('resets canceled demo loading before opening another project upload', async () => {
  const demo = demoCases.cases[0]
  vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: { revision: demo.ruleRevision } }])
  vi.stubGlobal('fetch', vi.fn((url: string) => url.startsWith('/demo/') ? new Promise(() => {}) : Promise.resolve(reads(url))))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByText('Включённые примеры'))
  await user.click(screen.getByRole('button', { name: demo.label }))
  expect(await screen.findByText('Загружаем и проверяем кадры примера…')).toBeTruthy()
  await user.selectOptions(screen.getByLabelText('Выбрать проект'), b)
  await user.click(screen.getByRole('link', { name: 'Загрузить фотографии' }))
  expect(screen.queryByText('Загружаем и проверяем кадры примера…')).toBeNull()
  expect(screen.getByLabelText('Выбрать изображение')).toHaveProperty('disabled', false)
  await user.upload(screen.getByLabelText('Выбрать изображение'), file())
  expect(await screen.findByText('photo.jpg')).toBeTruthy()
})

it('preserves forward history after declined dirty Back then accepted traversal', async () => {
  const user = userEvent.setup()
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  history.replaceState({}, '', `/projects/${a}`)
  render(<App />)
  await user.click(await screen.findByRole('link', { name: 'Загрузить фотографии' }))
  await user.upload(screen.getByLabelText('Выбрать изображение'), file())
  const length = history.length
  await act(async () => { history.back(); await new Promise(resolve => setTimeout(resolve, 50)) })
  expect(location.pathname).toBe(`/projects/${a}/new`)
  expect(history.length).toBe(length)
  expect(screen.getByText('photo.jpg')).toBeTruthy()
  confirm.mockReturnValue(true)
  await act(async () => { history.back(); await new Promise(resolve => setTimeout(resolve, 30)) })
  expect(location.pathname).toBe(`/projects/${a}`)
  await act(async () => { history.forward(); await new Promise(resolve => setTimeout(resolve, 30)) })
  expect(location.pathname).toBe(`/projects/${a}/new`)
  expect(history.length).toBe(length)
})

it('bounds hung workspace GETs and exposes retry without retrying mutations', async () => {
  history.replaceState({}, '', `/projects/${a}/plan`)
  let hung = true
  vi.stubGlobal('fetch', vi.fn((url: string) => hung && (url === '/api/catalog/works' || url.endsWith('/zones'))
    ? new Promise(() => {}) : Promise.resolve(reads(url))))
  vi.useFakeTimers()
  try {
    render(<App />)
    await act(async () => { await vi.advanceTimersByTimeAsync(10001) })
    expect(screen.getByRole('alert').textContent).toMatch(/Не удалось загрузить/)
    hung = false
    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(screen.getByLabelText('Участок')).toHaveProperty('value', zone)
  } finally { vi.useRealTimers() }
})

it('locks area selection and draft editing throughout save readback and manual refresh', async () => {
  history.replaceState({}, '', `/projects/${a}/plan`)
  let save!: (value: unknown) => void
  let refresh!: (value: unknown) => void
  let gets = 0
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => {
    if (options?.method === 'PUT') return new Promise(resolve => { save = resolve })
    if (url === `/api/zones/${zone}/plan` && ++gets > 1) return new Promise(resolve => { refresh = resolve })
    return Promise.resolve(url === '/api/catalog/works' ? json({ works: [{ id: run, title: 'Работа', source_row: 4 }] }) : reads(url))
  }))
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Добавить работу' }))
  await user.click(screen.getByRole('button', { name: 'Сохранить новую ревизию' }))
  expect(screen.getByLabelText('Участок')).toHaveProperty('disabled', true)
  expect(screen.getByLabelText('Состояние').closest('fieldset')).toHaveProperty('disabled', true)
  await act(async () => save(json({ revision_number: 1 })))
  expect(screen.getByLabelText('Участок')).toHaveProperty('disabled', true)
  await act(async () => refresh(json({ revision_number: 1, entries: [] })))
  await user.click(screen.getByRole('button', { name: 'Обновить с сервера' }))
  expect(screen.getByLabelText('Участок')).toHaveProperty('disabled', true)
  await act(async () => refresh(json({ revision_number: 1, entries: [] })))
  await waitFor(() => expect(screen.getByLabelText('Участок')).toHaveProperty('disabled', false))
})

it('hands off an unassigned pending request from a project to the unscoped legacy upload', async () => {
  history.replaceState({}, '', `/projects/${b}/new`)
  const saved = { endpoint: '/api/runs/single-image', key: 'orphan-recovery', body: '{"scenario":"original"}' }
  sessionStorage.setItem('observation-pending', JSON.stringify(saved))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'Вернуться к отправке' }))
  await waitFor(() => expect(location.pathname).toBe('/new'))
  expect(await screen.findByRole('button', { name: 'Повторить отправку' })).toHaveProperty('disabled', false)
  expect(sessionStorage.getItem('observation-pending')).toBe(JSON.stringify(saved))
})

it('retains delayed IndexedDB recovery without replacing a newer dirty plan', async () => {
  history.replaceState({}, '', `/projects/${a}`)
  const saved = { endpoint: '/api/runs/single-image', key: 'slow-recovery', body: JSON.stringify({ project_id: a, original: true }) }
  sessionStorage.setItem('observation-pending-id', saved.key)
  let release!: () => void
  vi.stubGlobal('indexedDB', { open: () => {
    const read = { result: saved, onsuccess: null as null | (() => void), onerror: null }
    const request = { result: { close() {}, transaction: () => ({ objectStore: () => ({ get: () => {
      release = () => read.onsuccess?.()
      return read
    } }) }) }, onsuccess: null as null | (() => void), onerror: null }
    queueMicrotask(() => request.onsuccess?.())
    return request
  } })
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/catalog/works'
    ? json({ works: [{ id: run, title: 'Новая работа B', source_row: 4 }] }) : reads(url)))
  const user = userEvent.setup()
  render(<App />)
  await waitFor(() => expect(release).toBeTruthy())
  await user.selectOptions(screen.getByLabelText('Выбрать проект'), b)
  await user.click(screen.getAllByRole('link', { name: 'План работ' })[0])
  await user.click(await screen.findByRole('button', { name: 'Добавить работу' }))
  await user.selectOptions(screen.getByLabelText('Состояние'), 'active')
  await act(async () => release())
  expect(location.pathname).toBe(`/projects/${b}/plan`)
  expect(screen.getByLabelText('Состояние')).toHaveProperty('value', 'active')
  expect(screen.getByRole('link', { name: 'Вернуться к отправке' }).getAttribute('href')).toBe(`/projects/${a}/new`)
  expect(sessionStorage.getItem('observation-pending-id')).toBe(saved.key)
})

it('does not navigate a late training creation over a newly typed project draft', async () => {
  history.replaceState({}, '', '/')
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  let finish!: (response: ReturnType<typeof json>) => void
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => url === '/api/projects' && options?.method === 'POST' ? await new Promise(resolve => { finish = resolve }) : reads(url)))
  render(<App />)
  await screen.findByLabelText('Название проекта')
  fireEvent.click(screen.getByRole('button', {name:'Как пользоваться'}))
  fireEvent.click(screen.getByRole('button', {name:'Попробовать на примере'}))
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  fireEvent.change(screen.getByLabelText('Название проекта'), {target:{value:'Keep my draft'}})
  await act(async () => { finish(json(projects[0],201)) })
  expect(location.pathname).toBe('/')
  expect(screen.getByLabelText('Название проекта')).toHaveProperty('value','Keep my draft')
  expect(screen.getByRole('button',{name:'Попробовать на примере'})).toHaveProperty('disabled',true)
})

it('cancels late training creation on navigation and releases preparation busy state', async () => {
  history.replaceState({}, '', '/')
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  let finish!: (response: ReturnType<typeof json>) => void
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => url === '/api/projects' && options?.method === 'POST' ? await new Promise(resolve => { finish = resolve }) : reads(url)))
  render(<App />); await screen.findByLabelText('Название проекта')
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  fireEvent.click(screen.getByRole('button',{name:'Попробовать на примере'}))
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  fireEvent.click(screen.getByRole('link',{name:'Архив анализов без проекта'}))
  await act(async () => { finish(json(projects[0],201)) })
  expect(location.pathname).toBe('/archive')
  await waitFor(() => expect(screen.getByRole('button',{name:'Попробовать на примере'})).toHaveProperty('disabled',false))
})

it('binds training readiness to the staged sample and clears it when removed or starting another analysis', async () => {
  history.replaceState({}, '', '/')
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  const frame = demoCases.cases[0].frames[1]
  vi.spyOn(crypto.subtle,'digest').mockResolvedValue(Uint8Array.from(frame.sha256.match(/../g)!, byte => parseInt(byte,16)).buffer)
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => url.startsWith('/demo/') ? {ok:true,blob:async()=>file()} : url === '/api/projects' && options?.method === 'POST' ? json(projects[0],201) : reads(url)))
  render(<App />); await screen.findByLabelText('Название проекта')
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  fireEvent.click(screen.getByRole('button',{name:'Попробовать на примере'}))
  await screen.findByText('Screenshot_89.jpg')
  await screen.findByText(/Учебный проект и проверенная фотография готовы/)
  fireEvent.click(screen.getByRole('button',{name:/Удалить: Screenshot_89.jpg/}))
  expect(screen.queryByText(/Учебный проект и проверенная фотография готовы/)).toBeNull()
  expect(screen.queryByText(/Учебный пример: проверенная фотография/)).toBeNull()
})

it('binds the tutorial result only to its accepted sample run and clears it for a new analysis', async () => {
  history.replaceState({}, '', '/')
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  const frame = demoCases.cases[0].frames[1]
  vi.spyOn(crypto.subtle,'digest').mockResolvedValue(Uint8Array.from(frame.sha256.match(/../g)!, byte => parseInt(byte,16)).buffer)
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => url.startsWith('/demo/') ? {ok:true,blob:async()=>file()} : options?.method === 'POST' ? url === '/api/projects' ? json(projects[0],201) : json({run_id:run},202) : reads(url)))
  render(<App />); await screen.findByLabelText('Название проекта')
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  fireEvent.click(screen.getByRole('button',{name:'Попробовать на примере'}))
  await screen.findByText(/Учебный проект и проверенная фотография готовы/)
  fireEvent.click(screen.getByRole('button',{name:'Запустить анализ'}))
  await screen.findByText(/Это ваш реальный учебный анализ/)
  expect(location.pathname).toBe(`/projects/${a}/runs/${run}`)
  fireEvent.click(screen.getByRole('link',{name:'Загрузить фото'}))
  await waitFor(()=>expect(location.pathname).toBe(`/projects/${a}/new`))
  expect(screen.queryByText(/Это ваш реальный учебный анализ/)).toBeNull()
  expect(screen.queryByText(/Учебный проект и проверенная фотография готовы/)).toBeNull()
})

it('cancels sample preparation on navigation without installing the late photo or keeping the action busy', async () => {
  history.replaceState({}, '', '/')
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  vi.spyOn(window,'confirm').mockReturnValue(true)
  const frame = demoCases.cases[0].frames[1]
  vi.spyOn(crypto.subtle,'digest').mockResolvedValue(Uint8Array.from(frame.sha256.match(/../g)!, byte => parseInt(byte,16)).buffer)
  let finish!: (value: unknown)=>void
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => url.startsWith('/demo/') ? await new Promise(resolve=>{finish=resolve}) : url === '/api/projects' && options?.method === 'POST' ? json(projects[0],201) : reads(url)))
  render(<App />); await screen.findByLabelText('Название проекта')
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  fireEvent.click(screen.getByRole('button',{name:'Попробовать на примере'}))
  await waitFor(()=>expect(finish).toBeTypeOf('function'))
  fireEvent.change(screen.getByLabelText('Выбрать проект'),{target:{value:b}})
  await act(async()=>{finish({ok:true,blob:async()=>file()})})
  expect(location.pathname).toBe(`/projects/${b}`)
  expect(screen.queryByText('Screenshot_89.jpg')).toBeNull()
  await waitFor(()=>expect(screen.getByRole('button',{name:'Попробовать на примере'})).toHaveProperty('disabled',false))
})

it('opens and focuses project creation from the header when existing projects collapse the disclosure',async()=>{
 history.replaceState({},'', '/')
 const user=userEvent.setup();render(<App/> )
 await screen.findByRole('link',{name:'Первый объект'})
 const field=screen.getByLabelText('Название проекта')
 expect(field.closest('details')?.open).toBe(false)
 await user.click(screen.getByRole('link',{name:'Создать проект'}))
 await waitFor(()=>expect(field.closest('details')?.open).toBe(true))
 await waitFor(()=>expect(document.activeElement).toBe(field))
})
