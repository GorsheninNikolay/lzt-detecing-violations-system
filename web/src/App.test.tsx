import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xd9])
const image = (name: string, marker = 0) => new File([jpeg, new Uint8Array([marker])], name, { type: 'image/jpeg' })
const stageNames = ['input_registration', 'frame_usability', 'equipment_observation', 'series_aggregation', 'rule_evaluation', 'result_projection']
const snapshot = (state: string, states = Array(6).fill('pending'), reasons: Record<number, string> = {}) => ({
  state, stages: stageNames.map((name, index) => ({ name, state: states[index], ...(reasons[index] ? { reason: reasons[index] } : {}) })),
})

describe('Observation result', () => {
  const runId = '12345678-1234-1234-1234-123456789abc'
  const inputs = [0, 1].map(ordinal => ({ input_id: `input-${ordinal}`, ordinal, sha256: 'same', artifact_id: `image-${ordinal}` }))
  const observations = inputs.flatMap(input => ['excavator', 'dump_truck'].map(class_name => ({
    input_id: input.input_id, ordinal: input.ordinal, class_name,
    state: class_name === 'excavator' && input.ordinal === 0 ? 'detected' : 'not_detected_in_frame', reason: null,
    source_artifact_id: input.artifact_id,
  })))
  const completed = { ...snapshot('succeeded'), context: { period: '2026-09-23T12:00:00+03:00', observation_area: 'north_gate' },
    inputs, observations, requested_classes: ['excavator', 'dump_truck'], outcome: 'observations_only',
    result_projection: { outcome: 'observations_only', series: { usable_count: 2,
      usable_input_ids: inputs.map(item => item.input_id), declared_observation_area: 'north_gate',
      input_order: inputs.map(item => item.input_id), excavator_supporting_input_ids: [inputs[0].input_id],
      dump_truck_persistence_input_ids: inputs.map(item => item.input_id),
      dump_truck_persistence_text: 'Самосвал не обнаружен ни в одном из 2 пригодных кадров.' } },
    native_evidence_by_frame: [{ artifact_id: 'native-0', input_id: 'input-0', ordinal: 0, sha256: 'native-hash',
      invocation_id: 'invocation-0', profile_id: 'profile-0', profile_revision: 1, preprocessing_revision: 'pre-1' }],
  }

  beforeEach(() => {
    history.replaceState({}, '', `/runs/${runId}`)
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() })
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
    HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
  })

  it('shows source-bound rows, series evidence, focus jump, and native provenance', async () => {
    const user = userEvent.setup()
    const projected = { ...completed, result_projection: { ...completed.result_projection,
      series: { ...completed.result_projection.series, input_order: ['input-1', 'input-0'] } } }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/runs/${runId}`
      ? { ok: true, json: async () => projected }
      : url.endsWith('native-0') ? { ok: true, text: async () => '{"detections":[]}' }
        : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Только наблюдения' })).toBeTruthy()
    expect(screen.getByText('Правило этапа не проверялось')).toBeTruthy()
    expect(screen.getAllByText(/Не обнаружен в кадре/)).toHaveLength(3)
    expect(screen.getByText(/Самосвал не обнаружен ни в одном из 2 пригодных кадров/)).toBeTruthy()
    expect(screen.getByText(/Порядок: Кадр 2 \(input-1\) → Кадр 1 \(input-0\)/)).toBeTruthy()
    expect(screen.getByText('Кадры с экскаватором: input-0.')).toBeTruthy()
    const cards = screen.getAllByRole('article')
    expect(inputs[0].sha256).toBe(inputs[1].sha256)
    expect(within(cards[0]).getByText('Экскаватор: Обнаружен')).toBeTruthy()
    expect(within(cards[0]).getAllByText(/Кадр 1, входной ID/).every(item => item.textContent?.includes('input-0'))).toBe(true)
    expect(within(cards[1]).getByText('Экскаватор: Не обнаружен в кадре')).toBeTruthy()
    expect(within(cards[1]).getAllByText(/Кадр 2, входной ID/).every(item => item.textContent?.includes('input-1'))).toBe(true)
    expect(screen.getByText(/по изображениям не подтверждена/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Перейти к результату' }))
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Только наблюдения' }))
    await user.click(screen.getByRole('button', { name: 'Открыть кадр 1' }))
    expect(screen.getByRole('dialog', { name: 'Просмотр исходных кадров' })).toBeTruthy()
    await user.click(screen.getByText('Технические данные наблюдателя'))
    expect(await screen.findByText('{"detections":[]}')).toBeTruthy()
    expect(screen.getByText(/invocation-0/)).toBeTruthy()
    expect(screen.getByText(/native-hash/)).toBeTruthy()
    expect(screen.getByText(/ревизия допуска: 1/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Следующий кадр' }))
    expect(within(screen.getByRole('dialog')).getByRole('status').textContent).toContain('Кадр 2 из 2')
  })

  it('shows a single-frame result without inventing series evidence', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, inputs: inputs.slice(0, 1),
        observations: observations.slice(0, 2), result_projection: { outcome: 'observations_only' } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Только наблюдения' })).toBeTruthy()
    expect(screen.getByText('Самосвал: Не обнаружен в кадре')).toBeTruthy()
    expect(await screen.findByRole('img', { name: /Исходное изображение: Кадр 1\. Экскаватор: Обнаружен/ })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Данные серии' })).toBeNull()
  })

  it('keeps single-frame text and native metadata when verified bytes fail', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, inputs: inputs.slice(0, 1), observations: observations.slice(0, 2), result_projection: { outcome: 'observations_only' } }) }
      : { ok: false, json: async () => ({ code: 'artifact_integrity_failed' }) }))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Только наблюдения' })).toBeTruthy()
    expect(await screen.findByText('Целостность артефакта не подтверждена')).toBeTruthy()
    expect(screen.getByText('Самосвал: Не обнаружен в кадре')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Открыть кадр 1' }))
    await user.click(screen.getByText('Технические данные наблюдателя'))
    expect((await within(screen.getByRole('dialog')).findAllByText('Целостность артефакта не подтверждена')).length).toBeGreaterThan(0)
    expect(screen.getByText(/invocation-0/)).toBeTruthy()
  })

  it('keeps legacy result and partial failed evidence readable when source retrieval fails', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (url: string): Promise<unknown> => url === `/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, result_projection: { outcome: 'observations_only' } }) }
      : { ok: false, json: async () => ({ code: 'artifact_integrity_failed' }) })
    vi.stubGlobal('fetch', fetchMock)
    const view = render(<App />)
    expect(await screen.findByText('Сводные данные серии недоступны для этого анализа.')).toBeTruthy()
    expect((await screen.findAllByText('Целостность артефакта не подтверждена')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Не обнаружен в кадре/)).toHaveLength(3)
    view.unmount()
    fetchMock.mockImplementation(async (url: string) => url === `/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, state: 'failed', outcome: null, result_projection: null,
        observations: [{ ...observations[0], state: 'insufficient_data', reason: 'frame_unassessable' },
          { ...observations[1], state: 'not_analyzed', reason: 'unsupported_class' }] }) }
      : { ok: false, json: async () => ({ code: 'artifact_read_unavailable' }) })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Частичные наблюдения — анализ не завершён' })).toBeTruthy()
    expect(screen.getByText('Кадр непригоден для распознавания.')).toBeTruthy()
    expect(screen.getByText('Класс не поддерживается профилем распознавания.')).toBeTruthy()
    expect(screen.queryByText('Правило этапа не проверялось')).toBeNull()
    expect(await screen.findByText('Не удалось открыть исходное изображение')).toBeTruthy()
  })

  it('retries one source without disturbing the other frame', async () => {
    const user = userEvent.setup()
    let resolveRetry!: (value: unknown) => void
    let firstReads = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === `/runs/${runId}`) return Promise.resolve({ ok: true, json: async () => completed })
      if (url.endsWith('image-0') && ++firstReads === 1) return Promise.resolve({ ok: false, json: async () => ({ code: 'artifact_read_unavailable' }) })
      if (url.endsWith('image-0')) return new Promise(resolve => { resolveRetry = resolve })
      return Promise.resolve({ ok: true, blob: async () => new Blob(['jpeg']) })
    }))
    render(<App />)
    const cards = await screen.findAllByRole('article')
    expect(await within(cards[1]).findByRole('img', { name: /Кадр 2/ })).toBeTruthy()
    await user.click(await within(cards[0]).findByRole('button', { name: 'Повторить' }))
    expect(within(cards[0]).getByText('Загружаем изображение…')).toBeTruthy()
    expect(within(cards[1]).getByRole('img', { name: /Кадр 2/ })).toBeTruthy()
    await act(async () => { resolveRetry({ ok: true, blob: async () => new Blob(['recovered']) }) })
    expect(await within(cards[0]).findByRole('img', { name: /Кадр 1/ })).toBeTruthy()
  })

  it('shows a later native failure instead of stale successful content', async () => {
    const user = userEvent.setup()
    let firstNativeReads = 0
    const run = { ...completed, native_evidence_by_frame: [...completed.native_evidence_by_frame,
      { ...completed.native_evidence_by_frame[0], artifact_id: 'native-1', input_id: 'input-1', ordinal: 1 }] }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/runs/${runId}`
      ? { ok: true, json: async () => run }
      : url.endsWith('native-0') ? ++firstNativeReads === 1
        ? { ok: true, text: async () => 'old native result' }
        : { ok: false, json: async () => ({ code: 'artifact_read_unavailable' }) }
        : url.endsWith('native-1') ? { ok: true, text: async () => 'second native result' }
          : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    await screen.findByRole('heading', { name: 'Только наблюдения' })
    await user.click(screen.getByRole('button', { name: 'Открыть кадр 1' }))
    await user.click(screen.getByText('Технические данные наблюдателя'))
    expect(await screen.findByText('old native result')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Следующий кадр' }))
    expect(await screen.findByText('second native result')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Предыдущий кадр' }))
    expect(await within(screen.getByRole('dialog')).findByText('Не удалось открыть технические данные')).toBeTruthy()
    expect(screen.queryByText('old native result')).toBeNull()
  })
})

beforeEach(() => {
  history.replaceState({}, '', '/')
  sessionStorage.clear()
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 2, height: 2, close: vi.fn() })))
  vi.stubGlobal('crypto', { randomUUID: vi.fn().mockReturnValueOnce('frame-1').mockReturnValueOnce('frame-2').mockReturnValueOnce('frame-3').mockReturnValue('key-1') })
})
afterEach(() => { vi.useRealTimers(); cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

async function fillContext(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Сценарий'), 'Земляные работы')
  await user.type(screen.getByLabelText('Зона наблюдения'), 'Северная зона')
}

describe('New Analysis', () => {
  it('submits reordered distinct bytes and retains duplicate frames', async () => {
    const user = userEvent.setup()
    const post = vi.fn().mockImplementation(async (url: string) => /^\/runs\/[0-9a-f-]{36}$/i.test(url)
      ? { ok: true, json: async () => snapshot('queued') }
      : { status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), [image('first.jpg', 1), image('second.jpg', 2), image('duplicate.jpg', 1)])
    await screen.findByText('Кадр 3')
    await user.click(screen.getByRole('button', { name: /Выше: second.jpg/ }))
    const rows = screen.getAllByRole('listitem').filter(row => row.classList.contains('frame'))
    expect(within(rows[0]).getByText('second.jpg')).toBeTruthy()
    expect(within(rows[1]).getByText('first.jpg')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await screen.findByText('Анализ поставлен в очередь')
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Анализ поставлен в очередь' }))
    expect(document.title).toBe('Анализ — Контроль строительства')
    expect(location.pathname).toBe('/runs/12345678-1234-1234-1234-123456789abc')
    const [url, options] = post.mock.calls[0]
    expect(url).toBe('/runs/series')
    const body = JSON.parse(options.body)
    expect(body.intent).toBe('observation_only')
    expect(body.images_base64).toHaveLength(3)
    expect(body.images_base64).toEqual([btoa(String.fromCharCode(...jpeg, 2)), btoa(String.fromCharCode(...jpeg, 1)), btoa(String.fromCharCode(...jpeg, 1))])
    expect(body.period).toMatch(/[+-]\d\d:\d\d$/)
  })

  it('rejects only invalid file and restores a removed frame in its prior position', async () => {
    const user = userEvent.setup({ applyAccept: false })
    render(<App />)
    expect(screen.getByRole('link', { name: 'К основному содержимому' })).toHaveProperty('hash', '#main')
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), [image('first.jpg'), new File(['bad'], 'bad.png', { type: 'image/png' }), image('third.jpg')])
    expect((await screen.findAllByText(/bad.png: Поддерживаются только файлы JPEG/)).length).toBeGreaterThan(0)
    expect(screen.getByText('third.jpg')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Удалить: first.jpg/ }))
    await user.click(screen.getByRole('button', { name: 'Вернуть' }))
    const rows = screen.getAllByRole('listitem').filter(row => row.classList.contains('frame'))
    expect(within(rows[0]).getByText('first.jpg')).toBeTruthy()
    expect(within(rows[1]).getByText('third.jpg')).toBeTruthy()
    expect(screen.getByLabelText('Сценарий')).toHaveProperty('value', 'Земляные работы')
  })

  it('preserves exact request and idempotency key after an uncertain response', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error('connection lost'))
      .mockResolvedValueOnce({ status: 503, json: async () => ({ code: 'service_not_ready' }) })
      .mockResolvedValueOnce({ status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
      .mockResolvedValue({ ok: true, json: async () => snapshot('queued') })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText(/Ответ сервера не получен/)).toBeTruthy()
    expect(screen.getByLabelText('Сценарий')).toHaveProperty('value', 'Земляные работы')
    cleanup()
    render(<App />)
    await screen.findByRole('button', { name: 'Повторить отправку' })
    await user.click(screen.getByRole('button', { name: 'Повторить отправку' }))
    expect(await screen.findByText(/Результат отправки пока неизвестен/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Повторить отправку' }))
    await screen.findByText('Анализ поставлен в очередь')
    const requests = fetchMock.mock.calls.slice(0, 3)
    expect(requests.map(call => call[0])).toEqual(['/runs/single-image', '/runs/single-image', '/runs/single-image'])
    expect(requests[0][1].body).toBe(requests[1][1].body)
    expect(requests[1][1].body).toBe(requests[2][1].body)
    expect(requests[0][1].headers['Idempotency-Key']).toBe(requests[1][1].headers['Idempotency-Key'])
    expect(requests[1][1].headers['Idempotency-Key']).toBe(requests[2][1].headers['Idempotency-Key'])
  })

  it('keeps files offline and explains denied camera access', async () => {
    const user = userEvent.setup()
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError')) } })
    render(<App />)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
    await user.click(screen.getByRole('button', { name: 'Снять камерой' }))
    expect((await screen.findAllByText(/Доступ к камере не предоставлен/)).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Снять камерой' })).toHaveProperty('disabled', true)
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    fireEvent(window, new Event('offline'))
    expect(await screen.findByText(/Нет соединения/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Запустить анализ' })).toHaveProperty('disabled', true)
    expect(screen.getByText('one.jpg')).toBeTruthy()
  })

  it('rejects undecodable and oversized pixel images while retaining an accepted frame', async () => {
    const user = userEvent.setup()
    const decode = vi.fn().mockResolvedValueOnce({ width: 2, height: 2, close: vi.fn() })
      .mockRejectedValueOnce(new Error('decode'))
      .mockResolvedValueOnce({ width: 8000, height: 6000, close: vi.fn() })
    vi.stubGlobal('createImageBitmap', decode)
    render(<App />)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), [image('good.jpg'), image('broken.jpg'), image('large.jpg')])
    expect(await screen.findByText('good.jpg')).toBeTruthy()
    expect(screen.queryByText('broken.jpg')).toBeNull()
    expect(screen.queryByText('large.jpg')).toBeNull()
    expect((await screen.findAllByText(/broken.jpg: Файл не удалось прочитать/)).length).toBeGreaterThan(0)
    expect((await screen.findAllByText(/large.jpg: Изображение превышает/)).length).toBeGreaterThan(0)
  })

  it('waits for file validation before preparing the request', async () => {
    const user = userEvent.setup()
    let finishDecode!: (value: { width: number; height: number; close: () => void }) => void
    vi.stubGlobal('createImageBitmap', vi.fn(() => new Promise(resolve => { finishDecode = resolve })))
    const post = vi.fn().mockResolvedValue({ status: 202, json: async () => ({ code: 'submission_in_progress' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    fireEvent.change(screen.getByLabelText('Выбрать JPEG'), { target: { files: [image('slow.jpg')] } })
    await waitFor(() => expect(finishDecode).toBeTypeOf('function'))
    fireEvent.submit(screen.getByRole('button', { name: 'Запустить анализ' }).closest('form')!)
    expect(post).not.toHaveBeenCalled()
    finishDecode({ width: 2, height: 2, close: vi.fn() })
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(JSON.parse(post.mock.calls[0][1].body).image_base64).toBe(btoa(String.fromCharCode(...jpeg, 0)))
  })

  it('treats a malformed definitive rejection as resolved and permits a new key', async () => {
    const user = userEvent.setup()
    const post = vi.fn().mockResolvedValueOnce({ status: 400, json: async () => { throw new Error('bad JSON') } })
      .mockResolvedValueOnce({ status: 202, json: async () => ({ code: 'submission_in_progress' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText(/Сервер отклонил запрос/)).toBeTruthy()
    expect(sessionStorage.getItem('observation-pending')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText(/Результат отправки пока неизвестен/)).toBeTruthy()
    expect(post).toHaveBeenCalledTimes(2)
  })

  it('shows a missing run accurately and retries a failed run read', async () => {
    const user = userEvent.setup()
    history.replaceState({}, '', '/runs/12345678-1234-1234-1234-123456789abc')
    const fetchMock = vi.fn().mockResolvedValueOnce({ status: 404, ok: false })
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ status: 200, ok: true, json: async () => snapshot('queued') })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByRole('heading', { name: 'Анализ не найден' })
    expect(screen.queryByRole('heading', { name: 'Этапы анализа' })).toBeNull()
    cleanup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Статус анализа неизвестен' })
    await user.click(screen.getByRole('button', { name: 'Проверить статус' }))
    await screen.findByRole('heading', { name: 'Анализ поставлен в очередь' })
  })

  it('shows committed transitions in order, announces them once, and preserves completed stages after failure', async () => {
    history.replaceState({}, '', '/runs/12345678-1234-1234-1234-123456789abc')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('queued') })
      .mockResolvedValueOnce({ ok: true, json: async () => {
        const data = snapshot('running', ['succeeded', 'running', 'pending', 'pending', 'pending', 'pending'])
        return { ...data, stages: data.stages.map((stage, index) => index === 1 ? { ...stage, timestamp: '2026-09-23T08:00:00Z' } : stage) }
      } })
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('running', ['succeeded', 'running', 'pending', 'pending', 'pending', 'pending']) })
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('failed', ['succeeded', 'failed', 'skipped', 'skipped', 'skipped', 'skipped'], { 1: 'executor_interrupted', 2: 'dependency_failed', 3: 'dependency_failed', 4: 'dependency_failed', 5: 'dependency_failed' }) })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    expect(screen.getByRole('heading', { name: 'Анализ поставлен в очередь' })).toBeTruthy()
    const list = screen.getByRole('list', { name: '' })
    expect(within(list).getAllByRole('listitem').map(item => within(item).getByRole('heading').textContent)).toEqual([
      'Регистрация входных данных', 'Проверка пригодности кадров', 'Распознавание техники',
      'Объединение наблюдений серии', 'Проверка правила', 'Формирование результата',
    ])
    const navigationButton = screen.getByRole('button', { name: 'Новый анализ' })
    navigationButton.focus()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(within(list).getAllByRole('listitem')[0].textContent).toContain('Завершено')
    expect(within(list).getByText('2026-09-23T08:00:00Z').getAttribute('datetime')).toBe('2026-09-23T08:00:00Z')
    expect(document.activeElement).toBe(navigationButton)
    expect(screen.getByRole('status').textContent).toContain('Проверка пригодности кадров: Выполняется.')
    const announcement = screen.getByRole('status').textContent
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(announcement).toContain('Проверка пригодности кадров: Выполняется.')
    expect(screen.getByRole('status').textContent).toBe('')
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByRole('heading', { name: 'Анализ завершился ошибкой' })).toBeTruthy()
    expect(within(list).getAllByRole('listitem')[0].textContent).toContain('Завершено')
    expect(within(list).getAllByRole('listitem')[1].textContent).toContain('Выполнение анализа прервалось.')
    expect(within(list).getAllByRole('listitem')[2].textContent).toContain('Предыдущий этап завершился ошибкой.')
    expect(screen.getByRole('status').textContent).toContain('Проверка пригодности кадров: Ошибка выполнения.')
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(fetchMock).toHaveBeenCalledTimes(4)
    vi.useRealTimers()
  })

  it('keeps the last snapshot on disconnect, retries the same run, and ignores a response after route switch', async () => {
    const runId = '12345678-1234-1234-1234-123456789abc'
    history.replaceState({}, '', `/runs/${runId}`)
    let resolveLate!: (value: unknown) => void
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('running', ['succeeded', 'running', 'pending', 'pending', 'pending', 'pending']) })
      .mockRejectedValueOnce(new Error('offline'))
      .mockImplementationOnce(() => new Promise(resolve => { resolveLate = resolve }))
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    expect(screen.getByRole('heading', { name: 'Анализ выполняется' })).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByRole('status').textContent).toBe('Связь потеряна. Анализ может продолжаться на сервере.')
    expect(screen.getByText('Проверка пригодности кадров')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Проверить статус' }))
    await act(async () => { await Promise.resolve() })
    expect(screen.getByRole('button', { name: 'Проверяем статус…' })).toHaveProperty('disabled', true)
    expect(screen.getByRole('heading', { name: 'Анализ выполняется' }).closest('.run-workspace')?.getAttribute('aria-busy')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Проверяем статус…' }))
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[2][0]).toBe(`/runs/${runId}`)
    fireEvent.click(screen.getByRole('button', { name: 'Новый анализ' }))
    await act(async () => { resolveLate({ ok: true, json: async () => snapshot('failed') }); await Promise.resolve() })
    expect(fetchMock.mock.calls[2][1].signal.aborted).toBe(true)
    expect(screen.getByRole('heading', { name: 'Наблюдение за техникой' })).toBeTruthy()
    expect(screen.queryByText('Проверка пригодности кадров')).toBeNull()
    vi.useRealTimers()
  })

  it('clears a disconnect warning after a successful terminal read and explains skipped stages', async () => {
    history.replaceState({}, '', '/runs/12345678-1234-1234-1234-123456789abc')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('running', ['succeeded', 'running', 'pending', 'pending', 'pending', 'pending']) })
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('succeeded', ['succeeded', 'succeeded', 'succeeded', 'skipped', 'skipped', 'succeeded'], { 3: 'not_applicable', 4: 'not_applicable' }) })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByRole('status').textContent).toContain('Связь потеряна')
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Проверить статус' })) })
    expect(screen.getByRole('heading', { name: 'Анализ завершён' })).toBeTruthy()
    expect(screen.queryByText('Связь потеряна. Анализ может продолжаться на сервере.')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Анализ завершён' }).closest('.run-workspace')?.getAttribute('aria-busy')).toBe('false')
    const stages = screen.getAllByRole('listitem')
    expect(stages[3].textContent).toContain('Не требуется для этого анализа.')
    expect(stages[4].textContent).toContain('Не требуется для этого анализа.')
    expect(screen.getByRole('status').textContent).toContain('Формирование результата: Завершено.')
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('keeps a known run when a later read returns 404 and does not label an unknown state as running', async () => {
    history.replaceState({}, '', '/runs/12345678-1234-1234-1234-123456789abc')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('running') })
      .mockResolvedValueOnce({ status: 404, ok: false })
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('unknown_state') })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByRole('heading', { name: 'Анализ выполняется' })).toBeTruthy()
    expect(screen.getByText('Проверка пригодности кадров')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Не удалось получить актуальный статус')
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Проверить статус' })) })
    expect(screen.getByRole('heading', { name: 'Статус анализа неизвестен' })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('times out a stalled status request, retains the snapshot, and offers retry', async () => {
    history.replaceState({}, '', '/runs/12345678-1234-1234-1234-123456789abc')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot('running') })
      .mockImplementationOnce(() => new Promise(() => {}))
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByRole('heading', { name: 'Анализ выполняется' }).closest('.run-workspace')?.getAttribute('aria-busy')).toBe('true')
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(fetchMock.mock.calls[1][1].signal.aborted).toBe(true)
    expect(screen.getByRole('button', { name: 'Проверить статус' })).toBeTruthy()
    expect(screen.getByText('Проверка пригодности кадров')).toBeTruthy()
  })

  it('keeps undo disabled when a restored frame would exceed eight', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), Array.from({ length: 8 }, (_, index) => image(`${index}.jpg`, index)))
    await screen.findByText('Кадр 8')
    await user.click(screen.getByRole('button', { name: /Удалить: 0.jpg/ }))
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('replacement.jpg'))
    await screen.findByText('replacement.jpg')
    expect(screen.getByRole('button', { name: 'Вернуть' })).toHaveProperty('disabled', true)
  })

  it('allows a transient camera retry and stops a late stream after leaving', async () => {
    const user = userEvent.setup()
    let resolveStream!: (stream: MediaStream) => void
    const getUserMedia = vi.fn().mockRejectedValueOnce(new Error('temporary failure'))
      .mockImplementationOnce(() => new Promise(resolve => { resolveStream = resolve }))
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Снять камерой' }))
    expect((await screen.findAllByText(/Не удалось открыть камеру/)).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Снять камерой' })).toHaveProperty('disabled', false)
    await user.click(screen.getByRole('button', { name: 'Снять камерой' }))
    await waitFor(() => expect(resolveStream).toBeTypeOf('function'))
    await user.click(screen.getByRole('link', { name: /Контроль строительства/ }))
    const stop = vi.fn()
    resolveStream({ getTracks: () => [{ stop }] } as unknown as MediaStream)
    await waitFor(() => expect(stop).toHaveBeenCalledTimes(1))
  })

  it('rejects a nonexistent local DST time', async () => {
    vi.stubEnv('TZ', 'America/New_York')
    try {
      const user = userEvent.setup()
      render(<App />)
      await fillContext(user)
      await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
      fireEvent.change(screen.getByLabelText('Дата и время наблюдения'), { target: { value: '2026-03-08T02:30' } })
      await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      expect((await screen.findAllByText(/Укажите существующие местные дату и время/)).length).toBeGreaterThan(0)
    } finally { vi.unstubAllEnvs() }
  })
})
