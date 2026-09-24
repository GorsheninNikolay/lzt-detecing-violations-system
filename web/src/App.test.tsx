import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import demoCases from './demoCases.json'

const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xd9])
const image = (name: string, marker = 0) => new File([jpeg, new Uint8Array([marker])], name, { type: 'image/jpeg' })
const stageNames = ['input_registration', 'frame_usability', 'equipment_observation', 'series_aggregation', 'rule_evaluation', 'result_projection']
const snapshot = (state: string, states = Array(6).fill('pending'), reasons: Record<number, string> = {}) => ({
  state, stages: stageNames.map((name, index) => ({ name, state: states[index], ...(reasons[index] ? { reason: reasons[index] } : {}) })),
})

describe('Analysis history', () => {
  const first = '11111111-1111-1111-1111-111111111111'
  const second = '22222222-2222-2222-2222-222222222222'
  const row = (run_id: string, state: string, outcome: string | null = null) => ({
    run_id, state, outcome, created_at: '2026-09-24T10:00:00+00:00', stage: 'excavation',
    intent: 'observation_only', retry_predecessor_id: null, retry_successor_id: null,
  })

  beforeEach(() => history.replaceState({}, '', '/analyses'))

  it('shows empty and failed loading states with a recovery action', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ runs: [] }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(screen.getByText('Загружаем анализы…')).toBeTruthy()
    expect(await screen.findByText('Не удалось загрузить анализы.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByText('Запусков пока нет.')).toBeTruthy()
    expect(screen.getAllByRole('link', { name: 'Новый анализ' })).toHaveLength(2)
  })

  it('times out a stalled history read and recovers on retry', async () => {
    const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>(() => {}))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ runs: [] }) })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    expect(screen.getByText('Загружаем анализы…')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(screen.getByText('Не удалось загрузить анализы.')).toBeTruthy()
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Повторить' })) })
    expect(screen.getByText('Запусков пока нет.')).toBeTruthy()
  })

  it('loads fresh server order when returning to history', async () => {
    let reads = 0
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/runs'
      ? { ok: true, json: async () => ({ runs: ++reads === 1 ? [row(first, 'queued'), row(second, 'queued')] : [row(second, 'queued'), row(first, 'queued')] }) }
      : { ok: true, json: async () => snapshot('succeeded') }))
    render(<App />)
    await screen.findByRole('link', { name: `Анализ ${first}` })
    fireEvent.click(screen.getByRole('link', { name: `Анализ ${first}` }))
    await screen.findByRole('heading', { name: 'Анализ завершён' })
    fireEvent.click(screen.getByRole('link', { name: 'Анализы' }))
    await waitFor(() => expect(screen.getAllByRole('link', { name: /^Анализ / }).map(link => link.textContent))
      .toEqual([`Анализ ${second}`, `Анализ ${first}`]))
  })

  it('retains order and focus on polling, guards unfinished outcomes, and reopens a workspace', async () => {
    const initial = [
      { ...row(first, 'queued'), retry_successor_id: second },
      { ...row(second, 'succeeded', 'no_check'), retry_predecessor_id: first, stage: 'other', intent: 'rule_evaluation' },
    ]
    const third = '33333333-3333-3333-3333-333333333333'
    const changed = [row(third, 'queued'), initial[1], { ...initial[0], state: 'running', outcome: 'no_check' }]
    const fetchMock = vi.fn(async (url: string) => {
      if (url !== '/api/runs') return { ok: true, json: async () => snapshot('succeeded') }
      const count = fetchMock.mock.calls.filter(call => call[0] === '/api/runs').length
      if (count > 2) throw new Error('offline')
      return { ok: true, json: async () => ({ runs: count === 1 ? initial : changed }) }
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    const links = () => screen.getAllByRole('link', { name: /^Анализ / })
    expect(links().map(link => link.textContent)).toEqual([`Анализ ${first}`, `Анализ ${second}`])
    const succeededRow = links()[1].closest('li')!
    expect(within(succeededRow).getByText('Другой этап')).toBeTruthy()
    expect(within(succeededRow).getByText('Проверить правило этапа')).toBeTruthy()
    expect(within(succeededRow).getByText('Завершён')).toBeTruthy()
    expect(within(succeededRow).getByText('Проверка не запрошена')).toBeTruthy()
    expect(within(succeededRow).getByText('Итог')).toBeTruthy()
    expect(within(succeededRow).getByText(first)).toBeTruthy()
    expect(within(succeededRow).getByText('Создан')).toBeTruthy()
    expect(succeededRow.querySelector('time')?.getAttribute('datetime')).toBe(initial[1].created_at)
    expect(within(links()[0].closest('li')!).getByText(second)).toBeTruthy()
    const selected = links()[0]
    selected.focus()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(links().map(link => link.textContent)).toEqual([`Анализ ${first}`, `Анализ ${second}`, `Анализ ${third}`])
    expect(document.activeElement).toBe(selected)
    expect(within(links()[0].closest('li')!).queryByText('Проверка не запрошена')).toBeNull()
    expect(within(links()[0].closest('li')!).queryByText('Итог')).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByText('Не удалось загрузить анализы.')).toBeTruthy()
    expect(links()).toHaveLength(3)
    await act(async () => { fireEvent.click(selected) })
    vi.useRealTimers()
    expect(await screen.findByRole('heading', { name: 'Анализ завершён' })).toBeTruthy()
    expect(fetchMock.mock.calls.some(call => call[0] === `/api/runs/${first}`)).toBe(true)
  })
})

describe('Observation result', () => {
  const runId = '12345678-1234-1234-1234-123456789abc'
  const inputs = [0, 1].map(ordinal => ({ input_id: `input-${ordinal}`, ordinal, sha256: `hash-${ordinal}`, artifact_id: `image-${ordinal}` }))
  const observations = inputs.flatMap(input => ['excavator', 'dump_truck'].map(class_name => ({
    input_id: input.input_id, ordinal: input.ordinal, class_name,
    state: class_name === 'excavator' && input.ordinal === 0 ? 'detected' : 'not_detected_in_frame', reason: null as string | null,
    source_artifact_id: input.artifact_id,
  })))
  const projectionFrames = (rows: typeof observations = observations, frameInputs: typeof inputs = inputs) => rows.map(item => ({ ...item,
    input_sha256: frameInputs.find(input => input.input_id === item.input_id)?.sha256 }))
  const completed = { ...snapshot('succeeded'), context: { period: '2026-09-23T12:00:00+03:00', observation_area: 'north_gate' },
    inputs, observations, requested_classes: ['excavator', 'dump_truck'], outcome: 'observations_only',
    profile_snapshot: { adapter: { code: 'grounding_dino' } },
    result_projection: { outcome: 'observations_only', frames: projectionFrames(), series: { usable_count: 2,
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
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute('open', '')
      this.querySelector('button')?.focus()
    }
    HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
  })

  it('shows source-bound rows, series evidence, focus jump, and native provenance', async () => {
    const user = userEvent.setup()
    const projected = { ...completed, result_projection: { ...completed.result_projection,
      series: { ...completed.result_projection.series, input_order: ['input-1', 'input-0'] } } }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => projected }
      : url.endsWith('native-0') ? { ok: true, text: async () => '{"count":1,"detections":[{"confidence":0.9,"geometry":[1,2]}]}' }
        : { ok: true, blob: async () => new Blob(['jpeg']) }))
    const view = render(<App />)
    expect(await screen.findByRole('heading', { name: 'Только наблюдения' })).toBeTruthy()
    expect(screen.getByText(/Правило этапа не проверялось/)).toBeTruthy()
    expect(screen.getByText(/Самосвал не обнаружен ни в одном из 2 пригодных кадров/)).toBeTruthy()
    expect(screen.getByText(/Порядок: Кадр 2 \(input-1\) → Кадр 1 \(input-0\)/)).toBeTruthy()
    expect(screen.getByText('Кадры с экскаватором: input-0.')).toBeTruthy()
    const rows = view.container.querySelectorAll<HTMLElement>('.observation-row')
    expect(inputs[0].sha256).not.toBe(inputs[1].sha256)
    expect(within(rows[0]).getByText('Экскаватор: Обнаружен')).toBeTruthy()
    expect(within(rows[0]).getByText(/input-0/)).toBeTruthy()
    expect(within(rows[2]).getByText('Экскаватор: Не обнаружен в кадре')).toBeTruthy()
    expect(within(rows[2]).getByText(/input-1/)).toBeTruthy()
    expect(screen.getByText(/по изображениям не подтверждена/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Перейти к результату' }))
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Только наблюдения' }))
    const opener = screen.getByRole('button', { name: 'Открыть кадр 1' })
    opener.focus()
    await user.keyboard('{Enter}')
    const dialog = screen.getByRole('dialog', { name: 'Просмотр исходных кадров' })
    expect(dialog).toBeTruthy()
    expect(dialog.contains(document.activeElement)).toBe(true)
    expect(screen.getByText('Номер кадра: 1. Пригодность: пригоден.')).toBeTruthy()
    expect(screen.getByText(/Наблюдения: Экскаватор: Обнаружен\. Самосвал: Не обнаружен в кадре\./)).toBeTruthy()
    expect(dialog.textContent).toContain('Исходный артефакт ID: image-0')
    expect(dialog.textContent).toContain('SHA-256 исходного кадра: hash-0')
    const zoom = within(dialog).getByRole('button', { name: 'Увеличить' })
    zoom.focus()
    await user.keyboard('{Enter}')
    expect(within(dialog).getByRole('status').textContent).toContain('150%')
    const reset = within(dialog).getByRole('button', { name: 'Сбросить масштаб' })
    reset.focus()
    await user.keyboard('{Enter}')
    expect(within(dialog).getByRole('status').textContent).toContain('100%')
    await user.click(screen.getByText('Технические данные наблюдателя'))
    const nativeDetails = screen.getByText('Технические данные наблюдателя').closest('details')!
    expect(await within(nativeDetails).findByText('{"count":1,"detections":[{"confidence":0.9,"geometry":[1,2]}]}')).toBeTruthy()
    expect(within(nativeDetails).getByText('Данные конкретного наблюдателя. Не используются правилом этапа.')).toBeTruthy()
    expect(screen.getByText(/grounding_dino/)).toBeTruthy()
    expect(screen.getByText(/invocation-0/)).toBeTruthy()
    expect(screen.getByText(/native-hash/)).toBeTruthy()
    expect(screen.getByText(/ревизия допуска: 1/)).toBeTruthy()
    expect(dialog.textContent).toContain('Предобработка: pre-1')
    const next = within(dialog).getByRole('button', { name: 'Следующий кадр' })
    next.focus()
    await user.keyboard('{Enter}')
    expect(within(screen.getByRole('dialog')).getByRole('status').textContent).toContain('Кадр 2 из 2')
    const previous = within(dialog).getByRole('button', { name: 'Предыдущий кадр' })
    previous.focus()
    await user.keyboard('{Enter}')
    expect(within(dialog).getByRole('status').textContent).toContain('Кадр 1 из 2')
    const close = within(dialog).getByRole('button', { name: 'Закрыть' })
    close.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(document.activeElement).toBe(opener)
  })

  it('shows a single-frame result without inventing series evidence', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, inputs: inputs.slice(0, 1),
        observations: observations.slice(0, 2), result_projection: { outcome: 'observations_only', frames: projectionFrames(observations.slice(0, 2)), series: completed.result_projection.series } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Только наблюдения' })).toBeTruthy()
    expect(screen.getByText('Самосвал: Не обнаружен в кадре')).toBeTruthy()
    expect(screen.getByText('Период наблюдения: 2026-09-23T12:00:00+03:00.')).toBeTruthy()
    expect(await screen.findByRole('img', { name: /Исходное изображение: Кадр 1\. Экскаватор: Обнаружен/ })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Данные серии' })).toBeNull()
  })

  it('shows unavailable series evidence for completed multi-frame observations', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed,
        result_projection: { ...completed.result_projection, series: undefined } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Данные серии' })).toBeTruthy()
    expect(screen.getByText('Сводные данные серии недоступны для этого анализа.')).toBeTruthy()
  })

  it.each([
    ['insufficient_data', 'Недостаточно данных', 'Для проверки правила нужны минимум 3 пригодных кадра одной зоны.', observations],
    ['not_analyzed', 'Не анализировалось', 'Запрошенный класс техники не анализировался; проверка правила недоступна.',
      [...observations, ...inputs.map(input => ({ input_id: input.input_id, ordinal: input.ordinal,
        class_name: 'crane', state: 'not_analyzed', reason: 'unsupported_class', source_artifact_id: input.artifact_id }))]],
  ])('renders successful %s with source history and no check request', async (outcome, label, reason, rows) => {
    const run = { ...completed, intent: 'rule_evaluation', outcome,
      result_projection: { ...completed.result_projection, outcome, frames: projectionFrames(rows), reason,
        supporting_input_ids: [], recommendation: null } }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => run }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    const view = render(<App />)
    expect(await screen.findByRole('heading', { name: label })).toBeTruthy()
    expect(view.container.querySelector('.rule-provenance')?.textContent).toContain(reason)
    expect(screen.getByText(/Порядок: Кадр 1 \(input-0\) → Кадр 2 \(input-1\)/)).toBeTruthy()
    expect(view.container.querySelectorAll('.source-thumbnail')).toHaveLength(2)
    expect(screen.queryByRole('region', { name: 'Проверка человеком' })).toBeNull()
    if (outcome === 'not_analyzed') {
      const unsupported = [...view.container.querySelectorAll<HTMLElement>('.observation-row')]
        .filter(row => row.textContent?.includes('crane: Не анализировалось'))
      expect(unsupported).toHaveLength(2)
      expect(unsupported[0].textContent).toContain('Класс не поддерживается профилем распознавания.')
      expect(unsupported[0].textContent).toContain('input-0')
    }
  })

  it('keeps observation-only outcome when a class cannot be assessed', async () => {
    const affected = observations.map(item => item.input_id === 'input-0'
      ? { ...item, state: 'insufficient_data', reason: 'frame_unassessable' } : item)
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, result_projection: {
        ...completed.result_projection, frames: projectionFrames(affected) } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    const view = render(<App />)
    expect(await screen.findByRole('heading', { name: 'Только наблюдения' })).toBeTruthy()
    const affectedRow = view.container.querySelector('.observation-row')!
    expect(affectedRow.textContent).toContain('Недостаточно данных')
    expect(affectedRow.textContent).toContain('Кадр непригоден для распознавания.')
    expect(affectedRow.textContent).toContain('input-0')
    expect(screen.queryByRole('region', { name: 'Проверка человеком' })).toBeNull()
  })

  it('names the limiting input in a successful rule result', async () => {
    const affected = observations.map(item => item.input_id === 'input-0'
      ? { ...item, state: 'insufficient_data', reason: 'frame_unassessable' } : item)
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, intent: 'rule_evaluation',
        result_projection: { ...completed.result_projection, outcome: 'insufficient_data',
          frames: projectionFrames(affected), series: { ...completed.result_projection.series,
            usable_count: 1, usable_input_ids: ['input-1'] },
          reason: 'Наблюдатель не смог оценить обязательный класс в кадре input-0.',
          supporting_input_ids: [], recommendation: null } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    const view = render(<App />)
    expect(await screen.findByRole('heading', { name: 'Недостаточно данных' })).toBeTruthy()
    expect(view.container.querySelector('.rule-provenance')?.textContent).toContain('input-0')
    expect(view.container.querySelector('.observation-row')?.textContent).toContain('Кадр непригоден для распознавания.')
    expect(screen.getByText(/Порядок: Кадр 1 \(input-0\) → Кадр 2 \(input-1\)/)).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Проверка человеком' })).toBeNull()
  })

  it('renders successful observations, rule and outcome only from the projection', async () => {
    const projectedRule = { name: 'Проверка по проекции', revision: 'projected-v2',
      expectation: 'Ожидание из проекции', provenance: 'Источник из проекции', recommendation: null }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, intent: 'observation_only', outcome: 'check_requested',
        inputs: inputs.map(input => input.input_id === 'input-0' ? { ...input, ordinal: 7 } : input),
        rule_snapshot: { ...projectedRule, name: 'Неверный снимок' },
        observations: [{ ...observations[0], state: 'not_detected_in_frame' }],
        result_projection: { ...completed.result_projection, outcome: 'no_check', frames: projectionFrames(),
          series: { ...completed.result_projection.series, usable_input_ids: ['input-0'] },
          rule: projectedRule, reason: 'Результат из проекции', uncertainty: 'Неопределённость из проекции',
          supporting_input_ids: ['input-0'] } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    const view = render(<App />)
    const user = userEvent.setup()
    expect(await screen.findByRole('heading', { name: 'Проверка не запрошена' })).toBeTruthy()
    expect(screen.getByText('Экскаватор: Обнаружен')).toBeTruthy()
    expect(within(view.container.querySelectorAll<HTMLElement>('.observation-row')[0]).queryByText('Экскаватор: Не обнаружен в кадре')).toBeNull()
    expect(within(view.container.querySelectorAll<HTMLElement>('.observation-row')[0]).getByRole('heading', { name: 'Кадр 1' })).toBeTruthy()
    expect(screen.getByText('Пригодность: не пригоден.')).toBeTruthy()
    expect(screen.getByText(/Проверка по проекции/)).toBeTruthy()
    expect(screen.getByText('Источник правила: Источник из проекции.')).toBeTruthy()
    expect(within(view.container.querySelectorAll<HTMLElement>('.source-thumbnail')[0]).getByRole('heading', { name: 'Кадр 1' })).toBeTruthy()
    expect(view.container.querySelector('.rule-provenance')?.textContent).toContain('Результат правила: Результат из проекции')
    expect(screen.getByText('Неопределённость из проекции')).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Проверка человеком' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Открыть кадр 1' }))
    expect(screen.getByText('Номер кадра: 1. Пригодность: пригоден.')).toBeTruthy()
  })

  it('states when optional projection details are unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, intent: 'rule_evaluation',
        result_projection: { outcome: 'no_check', frames: projectionFrames(), reason: 'Причина из проекции',
          supporting_input_ids: ['input-0'] } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    const view = render(<App />)
    expect(await screen.findByText('Сводные данные серии недоступны для этого анализа.')).toBeTruthy()
    expect(screen.getByText('Данные о правиле в проекции недоступны.')).toBeTruthy()
    expect(view.container.querySelector('.rule-provenance')?.textContent).toContain('Результат правила: Причина из проекции')
    expect(view.container.querySelector('.rule-provenance')?.textContent).toContain('Подтверждающие входные ID: input-0.')
    expect(screen.getByText('Неопределённость не указана в проекции.')).toBeTruthy()
    expect(view.container.querySelectorAll('.source-thumbnail')).toHaveLength(inputs.length)
    expect(view.container.querySelector('.source-thumbnail')?.textContent).toContain('Исходный артефакт ID: image-0')
  })

  it('renders the persisted rule outcome and human-check boundary', async () => {
    const rule = { name: 'Проверка вывоза грунта', revision: 'rule-immutable-evidence-v1',
      expectation: 'Экскаватор работает постоянно, самосвалы появляются периодически.',
      provenance: 'demonstration rule', recommendation: 'Проверить вручную' }
    const checkInputs = [...inputs, { input_id: 'input-2', ordinal: 2, sha256: 'third', artifact_id: 'image-2' }]
    const checkObservations = [...observations, ...['excavator', 'dump_truck'].map(class_name => ({
      input_id: 'input-2', ordinal: 2, class_name, state: 'not_detected_in_frame',
      reason: null, source_artifact_id: 'image-2',
    }))]
    const checkFrames = projectionFrames(checkObservations, checkInputs)
    const checkSeries = { ...completed.result_projection.series, usable_count: 3,
      usable_input_ids: checkInputs.map(input => input.input_id), declared_observation_area: 'series_gate',
      input_order: checkInputs.map(input => input.input_id),
      dump_truck_persistence_input_ids: checkInputs.map(input => input.input_id) }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, intent: 'rule_evaluation', outcome: 'check_requested', rule_snapshot: rule,
        inputs: checkInputs, observations: checkObservations,
        result_projection: { ...completed.result_projection, outcome: 'check_requested', frames: checkFrames,
          series: checkSeries, context: { ...completed.context, observation_area: 'projection_gate' },
          rule, supporting_input_ids: checkInputs.map(input => input.input_id),
          reason: 'Есть повод проверить возможную задержку вывоза грунта: экскаватор обнаружен хотя бы в одном пригодном кадре, самосвал не обнаружен ни в одном пригодном кадре.',
          uncertainty: 'Необнаружение в кадре не доказывает отсутствие на площадке.',
          recommendation: rule.recommendation } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Рекомендована проверка человеком' })).toBeTruthy()
    const panel = screen.getByRole('region', { name: 'Проверка человеком' })
    expect(panel.textContent).toContain('Основание: Есть повод проверить возможную задержку вывоза грунта')
    expect(panel.textContent).toContain('Подтверждающие входные ID: input-0, input-1, input-2.')
    expect(panel.textContent).toContain('Период: 2026-09-23T12:00:00+03:00. Заявленная зона: series_gate')
    expect(panel.textContent).toContain('Рекомендуемая проверка человеком: Проверить вручную.')
    expect(within(panel).getByText('Это рекомендация для проверки, а не подтверждение нарушения.')).toBeTruthy()
    expect(screen.getByText(/ревизия rule-immutable-evidence-v1/)).toBeTruthy()
    expect(document.querySelector('.rule-provenance')?.textContent).toContain('Ожидание: Экскаватор работает постоянно, самосвалы появляются периодически.')
    expect(screen.getByText('Источник правила: demonstration rule.')).toBeTruthy()
    expect(screen.getByText('Необнаружение в кадре не доказывает отсутствие на площадке.')).toBeTruthy()
    const headings = [...document.querySelectorAll('.result h3')].map(item => item.textContent)
    expect(headings).toEqual(['Наблюдения по кадрам', 'Данные серии', 'Исходные кадры', 'Правило и его источник', 'Неопределённость', 'Проверка человеком'])
  })

  it('falls back to projected and run areas when series area is missing', async () => {
    for (const [context, expected] of [
      [{ period: completed.context.period, observation_area: 'projection_gate' }, 'projection_gate'],
      [{ period: completed.context.period }, 'run_gate'],
    ] as const) {
      const run = { ...completed, intent: 'rule_evaluation', context: { ...completed.context, observation_area: 'run_gate' },
        result_projection: { ...completed.result_projection, outcome: 'check_requested', frames: projectionFrames(),
          series: undefined, context, reason: 'Проверка нужна', supporting_input_ids: [], recommendation: null } }
      vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
        ? { ok: true, json: async () => run }
        : { ok: true, blob: async () => new Blob(['jpeg']) }))
      const view = render(<App />)
      const panel = await screen.findByRole('region', { name: 'Проверка человеком' })
      expect(panel.textContent).toContain(`Заявленная зона: ${expected}`)
      view.unmount()
    }
  })

  it('shows positive evidence as a bounded no-check result', async () => {
    const rule = { name: 'Проверка вывоза грунта', revision: 'rule-positive-v1',
      expectation: 'Экскаватор работает постоянно, самосвалы появляются периодически.',
      provenance: 'demonstration rule', recommendation: 'Проверить вручную' }
    const positiveInputs = [...inputs, { input_id: 'input-2', ordinal: 2, sha256: 'third', artifact_id: 'image-2' }]
    const positiveObservations = [
      ...observations.map(item => item.input_id === 'input-1' && item.class_name === 'dump_truck'
        ? { ...item, state: 'detected' } : item),
      ...['excavator', 'dump_truck'].map(class_name => ({ input_id: 'input-2', ordinal: 2, class_name,
        state: 'not_detected_in_frame', reason: null, source_artifact_id: 'image-2' })),
    ]
    const positiveFrames = projectionFrames(positiveObservations, positiveInputs)
    const series = { ...completed.result_projection.series, usable_count: 3,
      usable_input_ids: positiveInputs.map(item => item.input_id),
      input_order: positiveInputs.map(item => item.input_id),
      dump_truck_persistence_input_ids: [], dump_truck_persistence_text: null }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, intent: 'rule_evaluation', outcome: 'no_check',
        rule_snapshot: rule, inputs: positiveInputs, observations: positiveObservations,
        result_projection: { ...completed.result_projection, frames: positiveFrames, series, outcome: 'no_check', rule,
          reason: 'Самосвал обнаружен в пригодной серии; запрос проверки не сформирован.',
          uncertainty: 'Необнаружение в кадре не доказывает отсутствие техники на всей площадке.',
          supporting_input_ids: ['input-0', 'input-1'], recommendation: null } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Проверка не запрошена' })).toBeTruthy()
    expect(document.querySelector('.rule-provenance')?.textContent).toContain('Самосвал обнаружен в пригодной серии; запрос проверки не сформирован.')
    expect(document.querySelector('.rule-provenance')?.textContent).toContain('Подтверждающие входные ID: input-0, input-1.')
    expect(screen.getByText(/ревизия rule-positive-v1/)).toBeTruthy()
    expect(screen.getByText('Необнаружение в кадре не доказывает отсутствие техники на всей площадке.')).toBeTruthy()
    expect(screen.getByText('Экскаватор: Обнаружен')).toBeTruthy()
    expect(screen.getByText('Самосвал: Обнаружен')).toBeTruthy()
    expect(screen.getByText(/Пригодных кадров: 3\. Входные ID: input-0, input-1, input-2/)).toBeTruthy()
    expect(screen.queryByText(/Самосвал не обнаружен ни в одном/)).toBeNull()
    expect(screen.queryByText(/Проверить вручную/)).toBeNull()
    expect(screen.queryByText(/этап.*здоров|нарушени[йя] нет/i)).toBeNull()
  })

  it('keeps single-frame text and native metadata when verified bytes fail', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, inputs: inputs.slice(0, 1), observations: observations.slice(0, 2), result_projection: { outcome: 'observations_only', frames: projectionFrames(observations.slice(0, 2)), series: completed.result_projection.series } }) }
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

  it('keeps projected metadata on source failure and uses legacy observations only for partial recovery', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (url: string): Promise<unknown> => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => completed }
      : { ok: false, json: async () => ({ code: 'artifact_integrity_failed' }) })
    vi.stubGlobal('fetch', fetchMock)
    const view = render(<App />)
    expect(await screen.findAllByText('Пригодность: пригоден.')).toHaveLength(2)
    expect(view.container.querySelector('.source-thumbnail')?.textContent).toContain('Исходный артефакт ID: image-0')
    expect(view.container.querySelector('.source-thumbnail')?.textContent).toContain('SHA-256: hash-0')
    expect((await screen.findAllByText('Целостность артефакта не подтверждена')).length).toBeGreaterThan(0)
    expect(view.container.querySelectorAll('.observation-row')).toHaveLength(4)
    view.unmount()
    fetchMock.mockImplementation(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, state: 'failed', intent: 'rule_evaluation', outcome: null, result_projection: null,
        observations: [{ ...observations[0], state: 'insufficient_data', reason: 'frame_unassessable' },
          { ...observations[1], state: 'not_analyzed', reason: 'unsupported_class' }] }) }
      : { ok: false, json: async () => ({ code: 'artifact_read_unavailable' }) })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Частичные наблюдения — анализ не завершён' })).toBeTruthy()
    expect(screen.getByText(/Кадр непригоден для распознавания/)).toBeTruthy()
    expect(screen.getByText(/Класс не поддерживается профилем распознавания/)).toBeTruthy()
    expect(screen.getByText('Период наблюдения: 2026-09-23T12:00:00+03:00.')).toBeTruthy()
    expect(screen.getByText('Статус правила недоступен: анализ не завершён.')).toBeTruthy()
    expect(screen.queryByText('Правило этапа не проверялось.')).toBeNull()
    expect(screen.queryByText('Правило этапа не проверялось')).toBeNull()
    expect((await screen.findAllByText('Не удалось открыть исходное изображение')).length).toBeGreaterThan(0)
  })

  it('retries one source without disturbing the other frame', async () => {
    const user = userEvent.setup()
    let resolveRetry!: (value: unknown) => void
    let firstReads = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === `/api/runs/${runId}`) return Promise.resolve({ ok: true, json: async () => completed })
      if (url.endsWith('image-0') && ++firstReads === 1) return Promise.resolve({ ok: false, json: async () => ({ code: 'artifact_read_unavailable' }) })
      if (url.endsWith('image-0')) return new Promise(resolve => { resolveRetry = resolve })
      return Promise.resolve({ ok: true, blob: async () => new Blob(['jpeg']) })
    }))
    const view = render(<App />)
    await screen.findByRole('heading', { name: 'Только наблюдения' })
    const thumbnails = [...view.container.querySelectorAll<HTMLElement>('.source-thumbnail')]
    expect(await within(thumbnails[1]).findByRole('img', { name: /Кадр 2/ })).toBeTruthy()
    await user.click(await within(thumbnails[0]).findByRole('button', { name: 'Повторить' }))
    expect(within(thumbnails[0]).getByText('Загружаем изображение…')).toBeTruthy()
    expect(within(thumbnails[1]).getByRole('img', { name: /Кадр 2/ })).toBeTruthy()
    await act(async () => { resolveRetry({ ok: true, blob: async () => new Blob(['recovered']) }) })
    expect(await within(thumbnails[0]).findByRole('img', { name: /Кадр 1/ })).toBeTruthy()
  })

  it('shows a later native failure instead of stale successful content', async () => {
    const user = userEvent.setup()
    let firstNativeReads = 0
    const run = { ...completed, native_evidence_by_frame: [...completed.native_evidence_by_frame,
      { ...completed.native_evidence_by_frame[0], artifact_id: 'native-1', input_id: 'input-1', ordinal: 1 }] }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
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
  vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: null }, { id: 'other', label: 'Другой этап', rule: null }])
  sessionStorage.clear()
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 2, height: 2, close: vi.fn() })))
  vi.stubGlobal('crypto', { randomUUID: vi.fn().mockReturnValueOnce('frame-1').mockReturnValueOnce('frame-2').mockReturnValueOnce('frame-3').mockReturnValue('key-1'), subtle: {
    digest: vi.fn(async (_algorithm: string, bytes: ArrayBuffer) => {
      const hash = demoCases.cases.flatMap(item => item.frames)[new Uint8Array(bytes)[4]]?.sha256 ?? '00'.repeat(32)
      return Uint8Array.from(hash.match(/../g)!.map(part => parseInt(part, 16))).buffer
    }),
  } })
})
afterEach(() => { vi.useRealTimers(); cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

async function fillContext(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Сценарий'), 'Земляные работы')
  await user.type(screen.getByLabelText('Зона наблюдения'), 'Северная зона')
}

function quotaBackedRequests() {
  const records = new Map<string, unknown>()
  const stores = new Set<string>()
  let opened = false
  const setItem = Storage.prototype.setItem
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, key, value) {
    if (key === 'observation-pending') throw new DOMException('quota exceeded', 'QuotaExceededError')
    setItem.call(this, key, value)
  })
  let finishWrite: (() => void) | undefined
  let failWrite = false
  const open = vi.fn(() => {
    const database = {
      close: vi.fn(),
      createObjectStore: (name: string) => stores.add(name),
      transaction: vi.fn((name: string, mode?: string) => {
        if (!stores.has(name)) throw new DOMException('missing object store', 'NotFoundError')
        const transaction = {
          oncomplete: null as null | (() => void),
          onerror: null as null | (() => void),
          error: new Error('write failed'),
          objectStore: () => ({
            put: (value: unknown, key: string) => {
              finishWrite = () => {
                if (failWrite) transaction.onerror?.()
                else { records.set(key, value); transaction.oncomplete?.() }
              }
            },
            get: (key: string) => {
              const request = { result: undefined as unknown, onsuccess: null as null | (() => void), onerror: null as null | (() => void) }
              queueMicrotask(() => { request.result = records.get(key); request.onsuccess?.() })
              return request
            },
            delete: (key: string) => queueMicrotask(() => { records.delete(key); transaction.oncomplete?.() }),
          }),
        }
        return transaction
      }),
    }
    const request = { result: database, onupgradeneeded: null as null | (() => void), onsuccess: null as null | (() => void), onerror: null as null | (() => void) }
    queueMicrotask(() => {
      if (!opened) { opened = true; request.onupgradeneeded?.() }
      request.onsuccess?.()
    })
    return request
  })
  vi.stubGlobal('indexedDB', { open })
  return { records, open, completeWrite: () => finishWrite?.(), failNextWrite: () => { failWrite = true } }
}

describe('New Analysis', () => {
  const configuredChoices = { stages: [{ id: 'excavation', label: 'Земляные работы', rule: {
    name: 'Проверка вывоза грунта', revision: 'v1', expectation: 'Самосвалы периодически',
    provenance: 'demonstration rule', recommendation: 'Проверить вручную',
  } }, { id: 'other', label: 'Другой этап', rule: null }] }

  for (const demo of demoCases.cases) {
    it(`loads ${demo.id} as an editable ordinary series in source order`, async () => {
      const user = userEvent.setup()
      vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
        ...configuredChoices.stages[0].rule, revision: demo.ruleRevision,
      } }])
      const bytes = demo.frames.map(frame => new Uint8Array([...jpeg, demoCases.cases.flatMap(item => item.frames).findIndex(item => item.path === frame.path)]))
      const fetchMock = vi.fn(async (url: string, _options?: RequestInit) => url.startsWith('/demo/')
        ? { ok: true, blob: async () => new Blob([bytes[demo.frames.findIndex(frame => frame.path === url)]]) }
        : { status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
      vi.stubGlobal('fetch', fetchMock)
      render(<App />)
      await user.type(screen.getByLabelText('Сценарий'), 'Исходный черновик')
      await user.upload(screen.getByLabelText('Выбрать JPEG'), image('mine.jpg'))
      await user.click(screen.getByRole('button', { name: demo.label }))
      expect(await screen.findByText('Screenshot_' + demo.frames[2].sourceMember.match(/\d+/)![0] + '.jpg')).toBeTruthy()
      expect(screen.queryByText('mine.jpg')).toBeNull()
      expect((screen.getByLabelText('Сценарий') as HTMLInputElement).value).toBe(demo.scenario)
      expect((screen.getByLabelText('Зона наблюдения') as HTMLInputElement).value).toBe(demo.observationArea)
      expect((screen.getByLabelText('Дата и время наблюдения') as HTMLInputElement).value).toBe(demo.period)
      expect((screen.getByRole('radio', { name: 'Проверить правило этапа' }) as HTMLInputElement).checked).toBe(true)
      expect(screen.getByText(demo.ruleRevision)).toBeTruthy()
      expect(screen.getByText(/В исходном примере время 12:00 условное/)).toBeTruthy()
      expect(screen.getByText(/порядок кадров соответствует архиву/)).toBeTruthy()
      await user.click(screen.getByRole('button', { name: `Выше: Screenshot_${demo.frames[1].sourceMember.match(/\d+/)![0]}.jpg, кадр 2` }))
      expect(screen.queryByText(/порядок кадров соответствует архиву/)).toBeNull()
      await user.click(screen.getByRole('button', { name: `Ниже: Screenshot_${demo.frames[1].sourceMember.match(/\d+/)![0]}.jpg, кадр 1` }))
      await user.type(screen.getByLabelText('Сценарий'), ' — уточнено')
      await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      await waitFor(() => expect(fetchMock.mock.calls.some(call => call[0] === '/api/runs/series')).toBe(true))
      const request = JSON.parse(fetchMock.mock.calls.find(call => call[0] === '/api/runs/series')![1]!.body as string)
      expect(request).toMatchObject({ intent: 'rule_evaluation', stage: 'excavation', scenario: demo.scenario + ' — уточнено', observation_area: demo.observationArea })
      expect(request.images_base64).toEqual(bytes.map(item => btoa(String.fromCharCode(...item))))
    })
  }

  it('preserves an edited form if any demo asset fails', async () => {
    const user = userEvent.setup()
    const demo = demoCases.cases[0]
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      ...configuredChoices.stages[0].rule, revision: demo.ruleRevision,
    } }])
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === demo.frames[1].path ? { ok: false } : {
      ok: true, blob: async () => new Blob([new Uint8Array([...jpeg, demoCases.cases.flatMap(item => item.frames).findIndex(item => item.path === url)])]),
    }))
    render(<App />)
    await user.type(screen.getByLabelText('Сценарий'), 'Мой сценарий')
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('mine.jpg'))
    await user.click(screen.getByRole('button', { name: demo.label }))
    expect(await screen.findByText(/Текущая форма сохранена/)).toBeTruthy()
    expect((screen.getByLabelText('Сценарий') as HTMLInputElement).value).toBe('Мой сценарий')
    expect(screen.getByText('mine.jpg')).toBeTruthy()
  })

  it('releases a stalled demo load without replacing the draft', async () => {
    const user = userEvent.setup()
    const demo = demoCases.cases[0]
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      ...configuredChoices.stages[0].rule, revision: demo.ruleRevision,
    } }])
    const fetchMock = vi.fn((_url: string, _options?: RequestInit) => new Promise<Response>(() => {}))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await user.type(screen.getByLabelText('Сценарий'), 'Мой сценарий')
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('mine.jpg'))
    vi.useFakeTimers()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: demo.label })); await Promise.resolve() })
    expect(screen.getByRole('button', { name: demo.label })).toHaveProperty('disabled', true)
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(screen.getByText(/Текущая форма сохранена/)).toBeTruthy()
    expect(screen.getByRole('button', { name: demo.label })).toHaveProperty('disabled', false)
    expect((screen.getByLabelText('Сценарий') as HTMLInputElement).value).toBe('Мой сценарий')
    expect(screen.getByText('mine.jpg')).toBeTruthy()
    expect(fetchMock.mock.calls.every(call => call[1]?.signal?.aborted)).toBe(true)
  })

  it('ignores a camera capture callback started before a demo selection', async () => {
    const user = userEvent.setup()
    const demo = demoCases.cases[0]
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      ...configuredChoices.stages[0].rule, revision: demo.ruleRevision,
    } }])
    const stop = vi.fn()
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true,
      value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop }] })) } })
    let finishCapture!: (blob: Blob | null) => void
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage: vi.fn() } as unknown as CanvasRenderingContext2D)
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(callback => { finishCapture = callback })
    const bytes = demo.frames.map(frame => new Uint8Array([...jpeg, demoCases.cases.flatMap(item => item.frames).findIndex(item => item.path === frame.path)]))
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true,
      blob: async () => new Blob([bytes[demo.frames.findIndex(frame => frame.path === url)]]),
    })))
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Снять камерой' }))
    const video = await screen.findByLabelText('Изображение с камеры')
    Object.defineProperty(video, 'videoWidth', { configurable: true, value: 2 })
    Object.defineProperty(video, 'videoHeight', { configurable: true, value: 2 })
    await user.click(screen.getByRole('button', { name: 'Сделать снимок' }))
    await user.click(screen.getByRole('button', { name: demo.label }))
    expect(await screen.findByText('Screenshot_90.jpg')).toBeTruthy()
    await act(async () => finishCapture(new Blob([jpeg], { type: 'image/jpeg' })))
    expect(screen.queryByText(/camera-\d+\.jpg/)).toBeNull()
    expect(screen.getAllByRole('listitem').filter(row => row.classList.contains('frame'))).toHaveLength(3)
    expect(stop).toHaveBeenCalled()
  })

  it('refuses a changed rule and leaves an uncertain pending body untouched', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', configuredChoices.stages)
    render(<App />)
    await user.type(screen.getByLabelText('Сценарий'), 'Мой сценарий')
    await user.click(screen.getByRole('button', { name: demoCases.cases[0].label }))
    expect(screen.getByRole('alert').textContent).toContain('текущая ревизия правила изменилась')
    expect((screen.getByLabelText('Сценарий') as HTMLInputElement).value).toBe('Мой сценарий')
    cleanup()
    const saved = { endpoint: '/api/runs/series', body: '{"original":true}', key: 'original-key' }
    sessionStorage.setItem('observation-pending', JSON.stringify(saved))
    render(<App />)
    await screen.findByText(/загрузка примера недоступна/)
    expect(screen.getByRole('button', { name: demoCases.cases[0].label })).toHaveProperty('disabled', true)
    expect(sessionStorage.getItem('observation-pending')).toBe(JSON.stringify(saved))
  })

  it('loads live choices and defaults to an enabled rule submission', async () => {
    vi.stubGlobal('__ANALYSIS_CHOICES__', undefined)
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => configuredChoices })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByText('Проверка вывоза грунта')).toBeTruthy()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/analysis-choices')
    expect((screen.getByRole('radio', { name: 'Проверить правило этапа' }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole('button', { name: 'Запустить анализ' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('retries failed live choices without losing prepared form context', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', undefined)
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ok: true, json: async () => configuredChoices })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByRole('button', { name: 'Повторить загрузку настроек' })
    await user.type(screen.getByLabelText('Зона наблюдения'), 'Северная зона')
    await user.click(screen.getByRole('button', { name: 'Повторить загрузку настроек' }))
    expect(await screen.findByText('Проверка вывоза грунта')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect((screen.getByLabelText('Зона наблюдения') as HTMLInputElement).value).toBe('Северная зона')
    expect((screen.getByRole('button', { name: 'Запустить анализ' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps an explicit observation preference across stage changes', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', configuredChoices.stages)
    render(<App />)
    await user.click(screen.getByRole('radio', { name: 'Только распознать технику' }))
    await user.selectOptions(screen.getByLabelText('Этап'), 'other')
    await user.selectOptions(screen.getByLabelText('Этап'), 'excavation')
    expect((screen.getByRole('radio', { name: 'Только распознать технику' }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole('radio', { name: 'Проверить правило этапа' }) as HTMLInputElement).disabled).toBe(false)
  })

  it('defaults to the server-provided excavation rule and explains an unconfigured stage', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      name: 'Проверка вывоза грунта на этапе земляных работ',
      revision: 'rule-34a0c9535d378f7482cac065e0d474e7b33a4fb545beee1922b962a837b9d97d',
      expectation: 'Экскаватор работает постоянно, самосвалы появляются периодически.',
      provenance: 'demonstration rule', recommendation: 'Проверить организацию вывоза грунта на участке вручную.',
    } }, { id: 'other', label: 'Другой этап', rule: null }])
    render(<App />)
    expect((screen.getByRole('radio', { name: 'Проверить правило этапа' }) as HTMLInputElement).checked).toBe(true)
    expect(screen.getByText('Проверка вывоза грунта на этапе земляных работ')).toBeTruthy()
    expect(screen.getByText('rule-34a0c9535d378f7482cac065e0d474e7b33a4fb545beee1922b962a837b9d97d')).toBeTruthy()
    expect(screen.getByText('Экскаватор работает постоянно, самосвалы появляются периодически.')).toBeTruthy()
    expect(screen.getByText('demonstration rule')).toBeTruthy()
    expect(screen.getByText(/Зона: не указана/)).toBeTruthy()
    await user.selectOptions(screen.getByLabelText('Этап'), 'other')
    expect((screen.getByRole('radio', { name: 'Только распознать технику' }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole('radio', { name: 'Проверить правило этапа' }) as HTMLInputElement).disabled).toBe(true)
    expect(screen.getByText('Для этого этапа правило не настроено в прототипе')).toBeTruthy()
  })

  it('allows a short rule series and sends its exact selected intent', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      name: 'Проверка вывоза грунта', revision: 'v1', expectation: 'Техника', provenance: 'demonstration rule', recommendation: 'Проверить',
    } }])
    const post = vi.fn().mockResolvedValue({ status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
    expect(screen.getByText(/нужны минимум три пригодных кадра/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(JSON.parse(post.mock.calls[0][1].body)).toMatchObject({ intent: 'rule_evaluation', stage: 'excavation' })
  })

  it('submits reordered distinct bytes and retains duplicate frames', async () => {
    const user = userEvent.setup()
    const post = vi.fn().mockImplementation(async (url: string) => /^\/api\/runs\/[0-9a-f-]{36}$/i.test(url)
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
    expect(sessionStorage.getItem('observation-pending')).toBeNull()
    const [url, options] = post.mock.calls[0]
    expect(url).toBe('/api/runs/series')
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
    expect(requests.map(call => call[0])).toEqual(['/api/runs/single-image', '/api/runs/single-image', '/api/runs/single-image'])
    expect(requests[0][1].body).toBe(requests[1][1].body)
    expect(requests[1][1].body).toBe(requests[2][1].body)
    expect(requests[0][1].headers['Idempotency-Key']).toBe(requests[1][1].headers['Idempotency-Key'])
    expect(requests[1][1].headers['Idempotency-Key']).toBe(requests[2][1].headers['Idempotency-Key'])
  })

  for (const filenames of [['one.jpg'], ['one.jpg', 'two.jpg']]) {
    it(`bounds stalled ${filenames.length === 1 ? 'single' : 'series'} sends and ignores late responses`, async () => {
      const user = userEvent.setup()
      const late: Array<(value: unknown) => void> = []
      const post = vi.fn()
        .mockImplementationOnce(() => new Promise(resolve => { late.push(resolve) }))
        .mockImplementationOnce(() => new Promise(resolve => { late.push(resolve) }))
        .mockResolvedValueOnce({ status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
        .mockResolvedValue({ ok: true, json: async () => snapshot('queued') })
      vi.stubGlobal('fetch', post)
      render(<App />)
      await fillContext(user)
      await user.upload(screen.getByLabelText('Выбрать JPEG'), filenames.map(name => image(name)))
      await screen.findByText(`Кадр ${filenames.length}`)
      const deadlines: Array<() => void> = []
      const realSetTimeout = globalThis.setTimeout
      vi.spyOn(globalThis, 'setTimeout').mockImplementation((callback, delay) => {
        if (delay === 10000) { deadlines.push(callback as () => void); return 0 as ReturnType<typeof setTimeout> }
        return realSetTimeout(callback, delay)
      })
      fireEvent.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
      const saved = sessionStorage.getItem('observation-pending')
      expect(saved).toBeTruthy()
      expect(screen.getByRole('button', { name: 'Создаём анализ…' })).toHaveProperty('disabled', true)
      await act(async () => { deadlines.shift()?.(); await Promise.resolve() })
      expect(post.mock.calls[0][1].signal.aborted).toBe(true)
      expect(screen.getByRole('button', { name: 'Повторить отправку' })).toHaveProperty('disabled', false)
      expect(screen.getByText(/Ответ сервера не получен/)).toBeTruthy()
      expect(sessionStorage.getItem('observation-pending')).toBe(saved)

      fireEvent.click(screen.getByRole('button', { name: 'Повторить отправку' }))
      await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
      await act(async () => { deadlines.shift()?.(); await Promise.resolve() })
      expect(post.mock.calls[1][1].signal.aborted).toBe(true)
      expect(screen.getByRole('button', { name: 'Повторить отправку' })).toHaveProperty('disabled', false)
      await act(async () => {
        for (const resolve of late) resolve({ status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
        await Promise.resolve()
      })
      expect(location.pathname).toBe('/')
      expect(sessionStorage.getItem('observation-pending')).toBe(saved)
      expect(screen.getByRole('button', { name: 'Повторить отправку' })).toBeTruthy()

      fireEvent.click(screen.getByRole('button', { name: 'Повторить отправку' }))
      await screen.findByRole('heading', { name: 'Анализ поставлен в очередь' })
      expect(post.mock.calls.slice(0, 3).map(call => call[0])).toEqual(Array(3).fill(filenames.length === 1 ? '/api/runs/single-image' : '/api/runs/series'))
      expect(post.mock.calls.slice(0, 3).every(([, options]) => options.body === post.mock.calls[0][1].body
        && options.headers['Idempotency-Key'] === post.mock.calls[0][1].headers['Idempotency-Key'])).toBe(true)
      expect(screen.getByRole('heading', { name: 'Анализ поставлен в очередь' })).toBeTruthy()
      expect(sessionStorage.getItem('observation-pending')).toBeNull()
    })
  }

  it('bounds a stalled response body and retries the exact saved request', async () => {
    const request = { endpoint: '/api/runs/single-image', body: '{"image_base64":"saved"}', key: 'saved-key' }
    sessionStorage.setItem('observation-pending', JSON.stringify(request))
    let resolveLateBody!: (value: unknown) => void
    const post = vi.fn()
      .mockResolvedValueOnce({ status: 202, json: () => new Promise(resolve => { resolveLateBody = resolve }) })
      .mockResolvedValueOnce({ status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
      .mockResolvedValue({ ok: true, json: async () => snapshot('queued') })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await screen.findByRole('button', { name: 'Повторить отправку' })
    const deadlines: Array<() => void> = []
    const realSetTimeout = globalThis.setTimeout
    vi.spyOn(globalThis, 'setTimeout').mockImplementation((callback, delay) => {
      if (delay === 10000) { deadlines.push(callback as () => void); return 0 as ReturnType<typeof setTimeout> }
      return realSetTimeout(callback, delay)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Повторить отправку' }))
    await waitFor(() => expect(resolveLateBody).toBeTypeOf('function'))
    expect(deadlines).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Создаём анализ…' })).toHaveProperty('disabled', true)
    await act(async () => { deadlines.shift()?.(); await Promise.resolve() })
    expect(post.mock.calls[0][1].signal.aborted).toBe(true)
    expect(screen.getByText(/Ответ сервера не получен/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Повторить отправку' })).toHaveProperty('disabled', false)
    expect(sessionStorage.getItem('observation-pending')).toBe(JSON.stringify(request))
    await act(async () => { resolveLateBody({ run_id: '12345678-1234-1234-1234-123456789abc' }); await Promise.resolve() })
    expect(location.pathname).toBe('/')
    expect(sessionStorage.getItem('observation-pending')).toBe(JSON.stringify(request))
    fireEvent.click(screen.getByRole('button', { name: 'Повторить отправку' }))
    await screen.findByRole('heading', { name: 'Анализ поставлен в очередь' })
    expect(post.mock.calls.slice(0, 2).map(call => call[0])).toEqual([request.endpoint, request.endpoint])
    expect(post.mock.calls.slice(0, 2).every(([, options]) => options.body === request.body
      && options.headers['Idempotency-Key'] === request.key)).toBe(true)
    expect(sessionStorage.getItem('observation-pending')).toBeNull()
  })

  it('recovers a quota-backed request after reload and removes it after a definitive response', async () => {
    const user = userEvent.setup()
    const storage = quotaBackedRequests()
    let sequence = 0
    vi.stubGlobal('crypto', { randomUUID: vi.fn(() => `id-${++sequence}`) })
    const post = vi.fn().mockRejectedValueOnce(new Error('connection lost'))
      .mockResolvedValueOnce({ status: 400, json: async () => ({ code: 'invalid_request' }) })
      .mockResolvedValueOnce({ status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
      .mockResolvedValue({ ok: true, json: async () => snapshot('queued') })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(storage.open).toHaveBeenCalledTimes(1))
    expect(post).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('observation-pending-id')).toBeNull()
    storage.completeWrite()
    expect(await screen.findByText(/Ответ сервера не получен/)).toBeTruthy()
    const [endpoint, options] = post.mock.calls[0]
    const key = options.headers['Idempotency-Key']
    expect(sessionStorage.getItem('observation-pending')).toBeNull()
    expect(sessionStorage.getItem('observation-pending-id')).toBe(key)
    expect(storage.records.get(key)).toEqual({ endpoint, body: options.body, key })
    cleanup()
    render(<App />)
    const retry = await screen.findByRole('button', { name: 'Повторить отправку' })
    expect(screen.getByLabelText('Сценарий').closest('fieldset')).toHaveProperty('disabled', true)
    await user.click(retry)
    expect(await screen.findByText(/Сервер отклонил запрос/)).toBeTruthy()
    expect(post.mock.calls[1][0]).toBe(endpoint)
    expect(post.mock.calls[1][1].body).toBe(options.body)
    expect(post.mock.calls[1][1].headers['Idempotency-Key']).toBe(key)
    expect(storage.records.has(key)).toBe(false)
    expect(sessionStorage.getItem('observation-pending-id')).toBeNull()
    expect(screen.getByLabelText('Сценарий').closest('fieldset')).toHaveProperty('disabled', false)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('two.jpg'))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(storage.open).toHaveBeenCalledTimes(4))
    storage.completeWrite()
    await screen.findByRole('heading', { name: 'Анализ поставлен в очередь' })
    const freshKey = post.mock.calls[2][1].headers['Idempotency-Key']
    expect(freshKey).not.toBe(key)
    expect(storage.records.has(freshKey)).toBe(false)
    expect(sessionStorage.getItem('observation-pending-id')).toBeNull()
  })

  it('does not send when quota fallback cannot persist the request', async () => {
    const user = userEvent.setup()
    const storage = quotaBackedRequests()
    storage.failNextWrite()
    const post = vi.fn()
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(storage.open).toHaveBeenCalledTimes(1))
    storage.completeWrite()
    expect(await screen.findByText(/Не удалось безопасно подготовить или сохранить запрос/)).toBeTruthy()
    expect(post).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('observation-pending-id')).toBeNull()
    expect(storage.records.size).toBe(0)
  })

  for (const [code, filenames] of [
    ['submission_publication_failed', ['one.jpg']],
    ['submission_interrupted', ['one.jpg', 'two.jpg']],
  ] as const) {
    it(`unlocks ${filenames.length === 1 ? 'single' : 'series'} form after terminal ${code} and sends a fresh key only on user action`, async () => {
      const user = userEvent.setup()
      let sequence = 0
      vi.stubGlobal('crypto', { randomUUID: vi.fn(() => `id-${++sequence}`) })
      const post = vi.fn()
        .mockResolvedValueOnce({ status: 503, json: async () => ({ code }) })
        .mockResolvedValueOnce({ status: 202, json: async () => ({ code: 'submission_in_progress' }) })
      vi.stubGlobal('fetch', post)
      render(<App />)
      await fillContext(user)
      await user.upload(screen.getByLabelText('Выбрать JPEG'), filenames.map(name => image(name)))
      await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      expect(await screen.findByText(/Отправка завершилась ошибкой.*новый ключ отправки/)).toBeTruthy()
      expect(post).toHaveBeenCalledTimes(1)
      expect(sessionStorage.getItem('observation-pending')).toBeNull()
      expect(screen.queryByRole('button', { name: 'Повторить отправку' })).toBeNull()
      expect(screen.getByLabelText('Сценарий')).toHaveProperty('disabled', false)
      for (const filename of filenames) expect(screen.getByText(filename)).toBeTruthy()
      await user.clear(screen.getByLabelText('Сценарий'))
      await user.type(screen.getByLabelText('Сценарий'), 'Новый сценарий')
      await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      expect(await screen.findByText(/Результат отправки пока неизвестен/)).toBeTruthy()
      expect(post).toHaveBeenCalledTimes(2)
      expect(post.mock.calls.map(call => call[0])).toEqual(Array(2).fill(filenames.length === 1 ? '/api/runs/single-image' : '/api/runs/series'))
      expect(post.mock.calls[1][1].headers['Idempotency-Key']).not.toBe(post.mock.calls[0][1].headers['Idempotency-Key'])
      expect(JSON.parse(post.mock.calls[1][1].body).scenario).toBe('Новый сценарий')
      expect(JSON.parse(post.mock.calls[1][1].body)[filenames.length === 1 ? 'image_base64' : 'images_base64'])
        .toEqual(JSON.parse(post.mock.calls[0][1].body)[filenames.length === 1 ? 'image_base64' : 'images_base64'])
    })
  }

  it('retains the exact saved request across unreadable and in-progress responses', async () => {
    const user = userEvent.setup()
    const post = vi.fn()
      .mockResolvedValueOnce({ status: 503, json: async () => { throw new Error('bad JSON') } })
      .mockResolvedValueOnce({ status: 202, json: async () => ({ code: 'submission_in_progress' }) })
      .mockResolvedValueOnce({ status: 503, json: async () => ({ code: 'service_not_ready' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать JPEG'), image('one.jpg'))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText(/Ответ сервера не получен/)).toBeTruthy()
    const saved = sessionStorage.getItem('observation-pending')
    expect(saved).toBeTruthy()
    cleanup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Повторить отправку' }))
    expect(await screen.findByText(/Результат отправки пока неизвестен/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Повторить отправку' }))
    expect(await screen.findByText(/Результат отправки пока неизвестен/)).toBeTruthy()
    expect(post).toHaveBeenCalledTimes(3)
    expect(sessionStorage.getItem('observation-pending')).toBe(saved)
    expect(post.mock.calls.slice(1).every(([, options]) => options.body === post.mock.calls[0][1].body
      && options.headers['Idempotency-Key'] === post.mock.calls[0][1].headers['Idempotency-Key'])).toBe(true)
  })

  it('retries a saved request through the API route without changing its body or key', async () => {
    const request = { endpoint: '/runs/single-image', body: '{"image_base64":"saved"}', key: 'saved-key' }
    sessionStorage.setItem('observation-pending', JSON.stringify(request))
    const post = vi.fn().mockResolvedValue({ status: 202, json: async () => ({ code: 'submission_in_progress' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Повторить отправку' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post.mock.calls[0][0]).toBe('/api/runs/single-image')
    expect(post.mock.calls[0][1].body).toBe(request.body)
    expect(post.mock.calls[0][1].headers['Idempotency-Key']).toBe(request.key)
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
    expect(fetchMock.mock.calls[2][0]).toBe(`/api/runs/${runId}`)
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
