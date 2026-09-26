vi.mock('./engagement', () => ({ startActivity: () => () => {}, track: async () => {}, attributionHeaders: () => ({}) }))
beforeEach(() => localStorage.setItem('construction-onboarding', 'completed'))
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import demoCases from './demoCases.json'

const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xd9])
const png = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10])
const runLink = (id: string) => screen.getAllByRole('link', { name: 'Открыть анализ' }).find(link => link.getAttribute('href')?.endsWith(`/runs/${id}`))!
const image = (name: string, marker = 0) => new File([jpeg, new Uint8Array([marker])], name, { type: 'image/jpeg' })
const stageNames = ['input_registration', 'frame_usability', 'equipment_observation', 'series_aggregation', 'rule_evaluation', 'result_projection']
const snapshot = (state: string, states = Array(6).fill('pending'), reasons: Record<number, string> = {}) => ({
  state, stages: stageNames.map((name, index) => ({ name, state: states[index], ...(reasons[index] ? { reason: reasons[index] } : {}) })),
})

describe('Provider comparison', () => {
  const runId = '11111111-1111-1111-1111-111111111111'
  const successRunId = '33333333-3333-3333-3333-333333333333'
  const comparison = {
    campaign: { id: 'campaign', revision_number: 2, evaluation_revision_id: 'evaluation' }, repeats: 3,
    fixtures: [{ ordinal: 0, scenario: 'single_both', expected_outcome: 'observations_only',
      frames: [{ ordinal: 0, manual_labels: { excavator: 'yes', dump_truck: 'unknown' } }] }], complete: false,
    candidates: [{ ordinal: 0, kind: 'grounding_dino', profile_revision: 'model-v1',
      requested_identity: 'Grounding DINO', returned_identity: 'checkpoint-sha256:model',
      authorization_revision: 1, identity_gap: null,
      admission: { status: 'admitted', authorization_state: 'enabled', current_revision: 1,
        evidence: 'present', cloud_data_gate: 'not_applicable', data_decision_revision: null, data_checked_at: null, commercial_gate: 'not_applicable' },
      accounting: { planned: 3, terminal: 2, succeeded: 1, failed: 0, timed_out: 1, pending: 0, missing: 1 },
      repeat_disagreement: { numerator: 0, denominator: 0, evidence: [] },
      latency_ms: { availability: 'observed', succeeded_count: 1, failed_count: 1 },
      cost: { availability: 'unavailable', reason: 'cost_not_recorded' } }],
    cells: [{ fixture_ordinal: 0, repeat_ordinal: 0, candidate_ordinal: 0, run_id: runId,
      state: 'failed', error_code: 'observer_timeout', latency_ms: 42, observed_outcome: null, observations: [] },
      { fixture_ordinal: 0, repeat_ordinal: 1, candidate_ordinal: 0, run_id: null,
        state: 'missing', error_code: null, latency_ms: null, observed_outcome: null, observations: [] },
      { fixture_ordinal: 0, repeat_ordinal: 2, candidate_ordinal: 0, run_id: successRunId,
        state: 'succeeded', error_code: null, latency_ms: 25, observed_outcome: 'observations_only',
        observations: [{ frame_ordinal: 0, class_name: 'excavator', state: 'detected' }] }],
  }

  beforeEach(() => history.replaceState({}, '', '/provider-comparison'))

  it('shows absence, then candidate detail, incomplete matrix, and run navigation', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ status: 404 })
      .mockResolvedValueOnce({ ok: true, json: async () => comparison })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...snapshot('failed'), purpose: 'comparison_campaign' }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByText('Нет данных: сравнительная кампания пока не сохранена.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    expect(await screen.findByText('Сравнение не завершено')).toBeTruthy()
    expect(screen.getByText(/тайм-аутов 1; ожидают 0; отсутствуют 1/)).toBeTruthy()
    expect(screen.getByText(/Расхождения повторов: не оценено: нет полных групп повторов/)).toBeTruthy()
    expect(screen.getByText(/Задержка измерена: успешные запуски — 1; запуски с ошибкой — 1.*Значения и ссылки на запуски — в матрице ниже/)).toBeTruthy()
    expect(screen.getAllByText('Только наблюдения').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Кадр 1: Экскаватор — Да; Самосвал — Неизвестно')).toHaveLength(3)
    expect(screen.getByText(/Кадр 1: Экскаватор — Обнаружен; ручная метка Да/)).toBeTruthy()
    expect(screen.getAllByText(/Сравнение не измерено/).length).toBeGreaterThan(0)
    expect(screen.getByText('Наблюдения запуска с ошибкой — частичные доказательства.')).toBeTruthy()
    expect(screen.getByText('42 мс (запуск с ошибкой)')).toBeTruthy()
    expect(screen.queryByText('Итог не совпадает с ожидаемым.')).toBeNull()
    fireEvent.click(screen.getByText('Технические сведения и ограничения'))
    expect(screen.getByText('checkpoint-sha256:model')).toBeTruthy()
    expect(screen.getByText('Возвращённая модель по замороженному профилю допуска')).toBeTruthy()
    expect(screen.getByText('Запуск недоступен')).toBeTruthy()
    expect(screen.getByRole('table').querySelector('caption')?.textContent).toContain('Все запланированные ячейки')
    fireEvent.click(screen.getByRole('link', { name: `Открыть запуск ${runId}` }))
    expect(await screen.findByText(`Номер анализа:`)).toBeTruthy()
    expect(location.pathname).toBe(`/runs/${runId}`)
  })

  it('retains the last successful read and its time after refresh failure and later 404', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => comparison })
      .mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ status: 404 })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByText('Сравнение не завершено')
    const savedTime = screen.getByText(/Время успешной загрузки:/).querySelector('time')?.dateTime
    fireEvent.click(screen.getByRole('button', { name: 'Обновить сравнение' }))
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('устаревшими'))
    expect(screen.getByRole('alert').querySelector('time')?.dateTime).toBe(savedTime)
    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(screen.getByText('Сравнение не завершено')).toBeTruthy()
    expect(screen.getByRole('alert').querySelector('time')?.dateTime).toBe(savedTime)
  })

  it('renders a terminal campaign without an incomplete banner and exposes missing admission', async () => {
    const terminal = { ...comparison, complete: true,
      candidates: [{ ...comparison.candidates[0], admission: { status: 'missing', authorization_state: null,
        current_revision: null, evidence: 'missing', cloud_data_gate: 'missing', data_decision_revision: null, data_checked_at: null, commercial_gate: 'unresolved' },
      accounting: { planned: 3, terminal: 3, succeeded: 3, failed: 0, timed_out: 0, pending: 0, missing: 0 } }] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => terminal }))
    render(<App />)
    await screen.findByText('Кампания № 2')
    expect(screen.queryByText('Сравнение не завершено')).toBeNull()
    fireEvent.click(screen.getByText('Технические сведения и ограничения'))
    expect(screen.getByText(/отсутствует; состояние неизвестно/)).toBeTruthy()
    expect(screen.getByText('Решение о данных отсутствует. Коммерческие условия не подтверждены')).toBeTruthy()
  })

  it('shows recorded cloud data and commercial gates apart from current authorization', async () => {
    const cloud = { ...comparison.candidates[0], ordinal: 1, kind: 'qwen3.6',
      requested_identity: 'qwen3.6', returned_identity: 'qwen3.6/latest',
      admission: { status: 'admitted', authorization_state: 'revoked', current_revision: 2,
        evidence: 'present', cloud_data_gate: 'recorded', data_decision_revision: 'owner-v1',
        data_checked_at: '2026-09-25T10:00:00Z', commercial_gate: 'paid_recorded' } }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      ...comparison, candidates: [comparison.candidates[0], cloud],
    }) }))
    render(<App />)
    await screen.findByText('Qwen 3.6 (облако)')
    const cloudCard = screen.getByText('Qwen 3.6 (облако)').closest('article')!
    fireEvent.click(within(cloudCard).getByText('Технические сведения и ограничения'))
    expect(within(cloudCard).getByText('Замороженное доказательство допуска')).toBeTruthy()
    expect(within(cloudCard).getByText('Текущее записанное состояние профиля и авторизации')).toBeTruthy()
    expect(within(cloudCard).getByText(/допущен; отозван; записанная ревизия 2/)).toBeTruthy()
    expect(within(cloudCard).getByText(/Решение о данных сохранено \(owner-v1\); проверено 2026-09-25T10:00:00Z/)).toBeTruthy()
    expect(within(cloudCard).getByText(/Оплаченный аккаунт подтверждён в сохранённом решении/)).toBeTruthy()
  })

  it('marks a completed cell whose observed outcome differs from its frozen expectation', async () => {
    const changed = { ...comparison, cells: comparison.cells.map(cell => cell.run_id === successRunId
      ? { ...cell, observed_outcome: 'check_requested' } : cell) }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => changed }))
    render(<App />)
    await screen.findByText('Кампания № 2')
    const rows = screen.getByRole('table').querySelectorAll('tbody tr')
    expect(rows[2].textContent).toContain('Только наблюдения')
    expect(rows[2].textContent).toContain('Запрошена проверка человеком')
    expect(rows[2].textContent).toContain('Итог не совпадает с ожидаемым.')
  })

  it('marks missed and false detections only for measured yes/no classes', async () => {
    const fixture = { ...comparison.fixtures[0], frames: [{ ordinal: 0,
      manual_labels: { excavator: 'yes', dump_truck: 'no' } }] }
    const changed = { ...comparison, fixtures: [fixture], cells: comparison.cells.map(cell => cell.run_id === successRunId
      ? { ...cell, observations: [
        { frame_ordinal: 0, class_name: 'excavator', state: 'not_detected_in_frame' },
        { frame_ordinal: 0, class_name: 'dump_truck', state: 'detected' },
      ] } : cell) }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => changed }))
    render(<App />)
    await screen.findByText('Кампания № 2')
    const rows = screen.getByRole('table').querySelectorAll('tbody tr')
    expect(rows[2].textContent).toContain('Пропуск обнаружения')
    expect(rows[2].textContent).toContain('Ложное обнаружение')
    expect(rows[0].textContent).toContain('Сравнение не измерено')
  })

  it('marks a terminal campaign with failures as completed with failures', async () => {
    const terminal = { ...comparison, complete: true, candidates: [{ ...comparison.candidates[0],
      accounting: { planned: 3, terminal: 3, succeeded: 1, failed: 1, timed_out: 1, pending: 0, missing: 0 } }] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => terminal }))
    render(<App />)
    expect(await screen.findByText(/Кампания завершена с ошибками/)).toBeTruthy()
    expect(screen.queryByText('Сравнение не завершено')).toBeNull()
  })

  it('maps distinct local and cloud cells to their own outcomes, observations and runs', async () => {
    const cloudRunId = '44444444-4444-4444-4444-444444444444'
    const cloud = { ...comparison.candidates[0], ordinal: 1, kind: 'qwen3.6' }
    const cloudCell = { fixture_ordinal: 0, repeat_ordinal: 2, candidate_ordinal: 1,
      run_id: cloudRunId, state: 'succeeded', error_code: null, latency_ms: 58,
      observed_outcome: 'check_requested', observations: [
        { frame_ordinal: 0, class_name: 'excavator', state: 'not_detected_in_frame' },
      ] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      ...comparison, candidates: [comparison.candidates[0], cloud], cells: [...comparison.cells, cloudCell],
    }) }))
    render(<App />)
    await screen.findByText('Кампания № 2')
    const rows = screen.getByRole('table').querySelectorAll('tbody tr')
    expect(rows[2].textContent).toContain('Grounding DINO (локально)')
    expect(rows[2].textContent).toContain('Кадр 1: Экскаватор — Обнаружен')
    expect(rows[3].textContent).toContain('Qwen 3.6 (облако)')
    expect(rows[3].textContent).toContain('Запрошена проверка человеком')
    expect(rows[3].textContent).toContain('Кадр 1: Экскаватор — Не обнаружен в кадре')
    expect(within(rows[3] as HTMLElement).getByRole('link', { name: `Открыть запуск ${cloudRunId}` })).toBeTruthy()
    expect(rows[3].textContent).not.toContain(successRunId)
  })
})

describe('Prototype readiness', () => {
  const runId = '11111111-1111-1111-1111-111111111111'
  const artifactId = '22222222-2222-2222-2222-222222222222'
  const createdAt = '2026-09-25T10:00:00+00:00'
  const report = {
    created_at: createdAt,
    rule: { name: 'Проверка вывоза грунта', revision: 'rule-v1', policy_revision: 'rule-policy-v1' },
    fixtures: [{ ordinal: 0, scenario: 'single_both', expected_outcome: 'observations_only' },
      { ordinal: 1, scenario: 'positive_series', expected_outcome: 'no_check' }],
    evaluation_set: { id: 'evaluation-revision', revision_number: 2, manifest_hash: 'e'.repeat(64),
      frames: Array.from({ length: 11 }, (_, ordinal) => ({ id: `frame-${ordinal}`, ordinal, scenario: 'single_both',
        image_sha256: String(ordinal).repeat(64), manual_labels: { excavator: 'yes', dump_truck: 'no' },
        sufficiency_notes: `Note ${ordinal}` })) },
    report: { id: 'report-id', campaign_id: 'campaign-id', campaign_manifest_hash: 'c'.repeat(64),
      evaluation_revision_id: 'evaluation-revision', evaluation_manifest_hash: 'e'.repeat(64),
      policy_revision: 'criterion-readiness-v1', evidence_digest: 'd'.repeat(64), status: 'incomplete',
      criteria: [
        { key: 'campaign_coverage', status: 'pass', reason: 'all_applicable_passed', numerator: 0, denominator: 36,
          evidence: [{ run_id: runId, fixture_ordinal: 0, repeat_ordinal: 0, candidate_ordinal: 0,
            state: 'succeeded', inputs: [{ input_id: 'input', artifact_id: artifactId }] }], misses: [] },
        { key: 'mandatory_outcomes', status: 'fail', reason: 'observed_failure', numerator: 2, denominator: 36,
          evidence: [{ run_id: null, fixture_ordinal: 1, repeat_ordinal: 0, candidate_ordinal: 0, state: 'missing' },
            { run_id: runId, fixture_ordinal: 1, repeat_ordinal: 1, candidate_ordinal: 0, state: 'succeeded', outcome: 'check_requested' }],
          misses: [{ run_id: null, fixture_ordinal: 1, repeat_ordinal: 0, candidate_ordinal: 0, state: 'missing' },
            { run_id: runId, fixture_ordinal: 1, repeat_ordinal: 1, candidate_ordinal: 0, state: 'succeeded', outcome: 'check_requested' }] },
        { key: 'mandatory_detections', status: 'not_evaluated', reason: 'pending_evidence', numerator: 0, denominator: 72,
          evidence: [{ run_id: runId, fixture_ordinal: 0, frame_ordinal: 0, class_name: 'excavator',
            state: 'planned', observation: null }], misses: [] },
        { key: 'zero_false_warnings', status: 'fail', reason: 'observed_failure', numerator: 1, denominator: 30,
          evidence: [{ run_id: runId, fixture_ordinal: 1, repeat_ordinal: 2, candidate_ordinal: 0,
            state: 'succeeded', outcome: 'check_requested' }],
          misses: [{ run_id: runId, fixture_ordinal: 1, repeat_ordinal: 2, candidate_ordinal: 0,
            state: 'succeeded', outcome: 'check_requested' }] },
      ], measures: { planned_cells: { numerator: 35, denominator: 36 }, technical_errors: { numerator: 1, denominator: 36 },
        outcome_misses: { numerator: 1, denominator: 36, evidence: [{ run_id: runId, fixture_ordinal: 1,
          outcome: 'check_requested', state: 'succeeded' }] },
        repeat_disagreement: { numerator: 1, denominator: 12, evidence: [{ fixture_ordinal: 1, candidate_ordinal: 0,
          run_ids: [runId] }] },
        latency_ms: { availability: 'observed', measured_count: 1, denominator: 36, values: [{ run_id: runId, milliseconds: 42 }] },
        cost: { availability: 'unavailable', reason: 'cost_not_recorded' },
        check_request_comprehension: { availability: 'unavailable', reason: 'comprehension_not_recorded' } } },
  }

  beforeEach(() => history.replaceState({}, '', '/readiness'))

  it('shows absent and failed reads with nearby retry', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ status: 404 })
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ok: true, json: async () => report })
    vi.stubGlobal('fetch', (url: string, options: RequestInit) => url === '/api/hybrid-readiness'
      ? Promise.resolve({ok:true,json:async()=>({status:'blocked',code:'missing_current_report'})})
      : fetchMock(url, options))
    render(<App />)
    expect(screen.getByRole('status', { name: '' }).textContent).toContain('Загружаем сохранённый отчёт')
    expect(await screen.findByText('Нет данных: сохранённого отчёта пока нет.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('Не удалось обновить'))
    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    expect(await screen.findByRole('heading', { name: 'Сохранённый отчёт' })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('shows failed criterion first, all frozen frames, linked evidence, and retains stale report', async () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() })
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute('open', '')
      this.querySelector('button')?.focus()
    }
    HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
    const observation = { input_id: 'input', ordinal: 0, class_name: 'excavator', state: 'detected',
      source_artifact_id: artifactId }
    const campaignRun = { ...snapshot('succeeded'), purpose: 'comparison_campaign',
      inputs: [{ input_id: 'input', ordinal: 0, sha256: 'source-hash', artifact_id: artifactId }],
      observations: [observation], result_projection: { outcome: 'observations_only', frames: [observation] } }
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => report })
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ok: true, json: async () => campaignRun })
      .mockResolvedValue({ ok: true, blob: async () => new Blob(['jpeg']) })
    vi.stubGlobal('fetch', (url: string, options: RequestInit) => url === '/api/hybrid-readiness'
      ? Promise.resolve({ok:true,json:async()=>({status:'blocked',code:'missing_current_report'})})
      : fetchMock(url, options))
    render(<App />)
    await screen.findByRole('heading', { name: 'Сохранённый отчёт' })
    const criteria = screen.getByRole('heading', { name: 'Критерии' }).nextElementSibling!
    expect(within(criteria as HTMLElement).getAllByRole('article').map(item => item.querySelector('h3')?.textContent))
      .toEqual(['Обязательные итоги', 'Отсутствие ложных запросов проверки', 'Обязательные обнаружения', 'Покрытие кампании'])
    expect(screen.getByText('Отчёт неполный: часть доказательств ещё отсутствует.')).toBeTruthy()
    expect(screen.getByText('35 / 36')).toBeTruthy()
    expect(screen.getByText('Недоступно: стоимость не сохранена')).toBeTruthy()
    expect(screen.getByText('Недоступно: понимание запроса проверки не измерялось')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Замороженный набор: 11 кадров' })).toBeTruthy()
    expect(screen.getByText('Note 10')).toBeTruthy()
    expect(screen.getByText(String(10).repeat(64))).toBeTruthy()
    const frameTable = screen.getByRole('heading', { name: 'Замороженный набор: 11 кадров' }).closest('section')!
    const frameRows = within(frameTable).getAllByRole('row').slice(1)
    expect(frameRows).toHaveLength(11)
    report.evaluation_set.frames.forEach((frame, index) => {
      const rendered = frameRows[index].textContent ?? ''
      expect(rendered).toContain(frame.id)
      expect(rendered).toContain(frame.image_sha256)
      expect(rendered).toContain('Экскаватор: Да (yes)')
      expect(rendered).toContain('Самосвал: Нет (no)')
      expect(rendered).toContain(frame.sufficiency_notes)
    })
    expect(screen.getAllByText('Запуск недоступен')).toHaveLength(3)
    expect(screen.getByText(/Состояние отчёта:/).textContent).toContain('Отчёт неполный')
    expect(screen.getAllByText(/Ожидалось: Проверка не запрошена.*получено: Запрошена проверка человеком/).length)
      .toBeGreaterThan(0)
    const warning = screen.getByRole('heading', { name: 'Отсутствие ложных запросов проверки' }).closest('article')!
    expect(warning.textContent).toContain('Не пройдено')
    expect(within(warning).getAllByText(/Ожидалось: Проверка не запрошена.*получено: Запрошена проверка человеком/).length).toBeGreaterThan(0)
    expect(within(warning).getAllByRole('link', { name: `Открыть запуск ${runId}` }).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Ручная метка: Да.*наблюдение: отсутствует/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Ожидающие и отсутствующие доказательства').length).toBeGreaterThan(0)
    expect(screen.getByText('Ручные метки: положительные 11, отрицательные 11, неизвестные 0; всего 22.')).toBeTruthy()
    expect(screen.getAllByRole('table').every(table => Boolean(table.querySelector('caption')))).toBe(true)
    const disagreement = screen.getByRole('rowheader', { name: 'Расхождения повторов' }).closest('tr')!
    fireEvent.click(within(disagreement).getByText('Доказательства: 1'))
    expect(within(disagreement).getByRole('link', { name: `Открыть запуск ${runId}` })).toBeTruthy()
    const runLinks = screen.getAllByRole('link', { name: `Открыть запуск ${runId}` })
    expect(runLinks[0].getAttribute('href')).toBe(`/runs/${runId}`)
    expect(screen.getByText((_, element) => element?.tagName === 'LI' && element.textContent?.includes('Исходный артефакт') === true).textContent).toContain(artifactId)
    expect(screen.queryByRole('link', { name: `Исходный артефакт ${artifactId}` })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Обновить отчёт' }))
    const stale = await screen.findByRole('alert')
    expect(stale.textContent).toContain('устаревшей')
    expect(stale.querySelector('time')?.getAttribute('datetime')).toBe(createdAt)
    expect(screen.getByText('Note 10')).toBeTruthy()
    fireEvent.click(runLinks[0])
    expect(await screen.findByRole('heading', { name: 'Анализ завершён' })).toBeTruthy()
    expect(screen.getByText('Доказательство сравнительной кампании')).toBeTruthy()
    expect(fetchMock.mock.calls.some(call => call[0] === `/api/runs/${runId}`)).toBe(true)
    expect(await screen.findByRole('img', { name: /Исходное изображение: Кадр 1/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Открыть кадр 1' }))
    expect(screen.getByRole('dialog', { name: 'Просмотр исходных кадров' }).textContent)
      .toContain(`Исходный артефакт ID: ${artifactId}`)
    expect(fetchMock.mock.calls.some(call => call[0] === `/api/runs/${runId}/artifacts/${artifactId}`)).toBe(true)
  })

  it.each([['pass', 'Пройдено'], ['fail', 'Не пройдено']])('shows persisted overall %s in Russian', async (status, label) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true,
      json: async () => ({ ...report, report: { ...report.report, status } }) }))
    render(<App />)
    expect((await screen.findByText(/Состояние отчёта:/)).textContent).toContain(label)
  })

  it('keeps an unknown unavailable-measure reason visible', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...report,
      report: { ...report.report, measures: { ...report.report.measures,
        cost: { availability: 'unavailable', reason: 'unmapped_code' } } } }) }))
    render(<App />)
    expect(await screen.findByText('Недоступно: unmapped_code')).toBeTruthy()
  })

  it('retains the persisted report and timestamp after a later 404', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => report })
      .mockResolvedValueOnce({ status: 404 })
    vi.stubGlobal('fetch', (url: string, options: RequestInit) => url === '/api/hybrid-readiness'
      ? Promise.resolve({ok:true,json:async()=>({status:'blocked',code:'missing_current_report'})})
      : fetchMock(url, options))
    render(<App />)
    await screen.findByRole('heading', { name: 'Сохранённый отчёт' })
    fireEvent.click(screen.getByRole('button', { name: 'Обновить отчёт' }))
    const stale = await screen.findByRole('alert')
    expect(stale.textContent).toContain('устаревшей')
    expect(stale.querySelector('time')?.getAttribute('datetime')).toBe(createdAt)
    expect(screen.getByText('Note 10')).toBeTruthy()
  })

  it('stops an unresponsive readiness fetch after ten seconds and offers retry', async () => {
    const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>(() => {}))
      .mockResolvedValueOnce({ status: 404 })
    vi.stubGlobal('fetch', (url: string, options: RequestInit) => url === '/api/hybrid-readiness'
      ? Promise.resolve({ok:true,json:async()=>({status:'blocked',code:'missing_current_report'})})
      : fetchMock(url, options))
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(screen.getByRole('alert').textContent).toContain('Не удалось обновить')
    expect(screen.getByRole('button', { name: 'Повторить загрузку' })).toBeTruthy()
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' })) })
    expect(screen.getByText('Нет данных: сохранённого отчёта пока нет.')).toBeTruthy()
  })

  it('opens retained source images on a failed campaign run without observations', async () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() })
    const failedRun = { ...snapshot('failed'), purpose: 'comparison_campaign',
      inputs: [{ input_id: 'input', ordinal: 0, sha256: 'source-hash', artifact_id: artifactId }],
      observations: [], result_projection: null }
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => report })
      .mockResolvedValueOnce({ ok: true, json: async () => failedRun })
      .mockResolvedValue({ ok: true, blob: async () => new Blob(['jpeg']) })
    vi.stubGlobal('fetch', (url: string, options: RequestInit) => url === '/api/hybrid-readiness'
      ? Promise.resolve({ok:true,json:async()=>({status:'blocked',code:'missing_current_report'})})
      : fetchMock(url, options))
    render(<App />)
    await screen.findByRole('heading', { name: 'Сохранённый отчёт' })
    fireEvent.click(screen.getAllByRole('link', { name: `Открыть запуск ${runId}` })[0])
    expect(await screen.findByRole('heading', { name: 'Исходные кадры — анализ не завершён' })).toBeTruthy()
    expect(await screen.findByRole('img', { name: /Исходное изображение: Кадр 1/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Повторить анализ' })).toBeNull()
    expect(fetchMock.mock.calls.some(call => call[0] === `/api/runs/${runId}/artifacts/${artifactId}`)).toBe(true)
  })
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
    expect(screen.getByText('Загружаем историю…')).toBeTruthy()
    expect(await screen.findByText('Не удалось загрузить историю анализов.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    expect(await screen.findByText('Анализов пока нет.')).toBeTruthy()
    expect(screen.getAllByRole('link', { name: 'Новый анализ' })).toHaveLength(1)
  })

  it('times out a stalled history read and recovers on retry', async () => {
    const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>(() => {}))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ runs: [] }) })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    expect(screen.getByText('Загружаем историю…')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(screen.getByText('Не удалось загрузить историю анализов.')).toBeTruthy()
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' })) })
    expect(screen.getByText('Анализов пока нет.')).toBeTruthy()
  })

  it('loads fresh server order when returning to history', async () => {
    let reads = 0
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/runs?unassigned=true'
      ? { ok: true, json: async () => ({ runs: ++reads === 1 ? [row(first, 'queued'), row(second, 'queued')] : [row(second, 'queued'), row(first, 'queued')] }) }
      : { ok: true, json: async () => snapshot('succeeded') }))
    render(<App />)
    await waitFor(() => { expect(runLink(first)).toBeTruthy(); return runLink(first) })
    fireEvent.click(runLink(first))
    await screen.findByRole('heading', { name: 'Анализ завершён' })
    fireEvent.click(screen.getByRole('link', { name: 'Анализы' }))
    await waitFor(() => expect(screen.getAllByRole('link', { name: 'Открыть анализ' }).map(link => link.getAttribute('href')?.split('/').pop()))
      .toEqual([second, first]))
  })

  it.each(['/history', '/analyses'])('retains order and focus on polling at %s, guards unfinished outcomes, and reopens a workspace', async path => {
    history.replaceState({}, '', path)
    const initial = [
      { ...row(first, 'queued'), retry_successor_id: second },
      { ...row(second, 'succeeded', 'no_check'), retry_predecessor_id: first, stage: 'other', intent: 'rule_evaluation' },
    ]
    const third = '33333333-3333-3333-3333-333333333333'
    const changed = [row(third, 'queued'), initial[1], { ...initial[0], state: 'running', outcome: 'no_check' }]
    const fetchMock = vi.fn(async (url: string) => {
      if (url !== '/api/runs?unassigned=true') return { ok: true, json: async () => snapshot('succeeded') }
      const count = fetchMock.mock.calls.filter(call => call[0] === '/api/runs?unassigned=true').length
      if (count > 2) throw new Error('offline')
      return { ok: true, json: async () => ({ runs: count === 1 ? initial : changed }) }
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    const links = () => screen.getAllByRole('link', { name: 'Открыть анализ' })
    expect(links().map(link => link.getAttribute('href')?.split('/').pop())).toEqual([first, second])
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
    expect(links().map(link => link.getAttribute('href')?.split('/').pop())).toEqual([first, second, third])
    expect(document.activeElement).toBe(selected)
    expect(within(links()[0].closest('li')!).getByText('Выполняется')).toBeTruthy()
    expect(within(links()[0].closest('li')!).queryByText('Проверка не запрошена')).toBeNull()
    expect(within(links()[0].closest('li')!).queryByText('Итог')).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByText('Не удалось загрузить историю анализов.')).toBeTruthy()
    expect(links()).toHaveLength(3)
    await act(async () => { fireEvent.click(selected) })
    vi.useRealTimers()
    expect(await screen.findByRole('heading', { name: 'Анализ завершён' })).toBeTruthy()
    expect(fetchMock.mock.calls.some(call => call[0] === `/api/runs/${first}`)).toBe(true)
  })

  it.each(['/history', '/analyses'])('shows persisted fields and pages past 50 runs at %s', async path => {
    history.replaceState({}, '', path)
    const older = '33333333-3333-3333-3333-333333333333'
    const firstPage = [
      { ...row(first, 'succeeded', 'no_check'), id: first, stage: 'other', intent: 'rule_evaluation', retry_successor_id: older },
      ...Array.from({ length: 49 }, (_, index) => ({ ...row(`44444444-4444-4444-4444-${String(index).padStart(12, '0')}`, 'queued') })),
    ]
    const fetchMock = vi.fn(async (url: string) => ({ ok: true, json: async () => url === '/api/runs?offset=50&unassigned=true'
      ? { runs: [{ ...row(older, 'failed'), id: older, created_at: null, retry_predecessor_id: first }], next_offset: null }
      : { runs: firstPage, next_offset: 50 } }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const firstLink = await waitFor(() => { expect(runLink(first)).toBeTruthy(); return runLink(first) })
    const firstRow = firstLink.closest('li')!
    expect(within(firstRow).getByText('Другой этап')).toBeTruthy()
    expect(within(firstRow).getByText('Проверить правило этапа')).toBeTruthy()
    expect(within(firstRow).getByText('Проверка не запрошена')).toBeTruthy()
    expect(within(firstRow).getByText(older)).toBeTruthy()
    expect(screen.getAllByRole('listitem')).toHaveLength(50)
    fireEvent.click(screen.getByRole('button', { name: 'Показать ещё' }))
    const olderRow = (await waitFor(() => { expect(runLink(older)).toBeTruthy(); return runLink(older) })).closest('li')!
    expect(within(olderRow).getByText('Время создания неизвестно')).toBeTruthy()
    expect(within(olderRow).getByText(first)).toBeTruthy()
    expect(screen.getAllByRole('listitem')).toHaveLength(51)
    expect(fetchMock.mock.calls.some(call => call[0] === '/api/runs?offset=50&unassigned=true')).toBe(true)
  })

  it.each(['/history', '/analyses'])('keeps polling the first page after loading older runs at %s', async path => {
    history.replaceState({}, '', path)
    const older = '33333333-3333-3333-3333-333333333333'
    const firstPage = [row(first, 'queued'),
      ...Array.from({ length: 49 }, (_, index) => row(`44444444-4444-4444-4444-${String(index).padStart(12, '0')}`, 'succeeded'))]
    let firstPageReads = 0
    const fetchMock = vi.fn(async (url: string) => ({ ok: true, json: async () => url === '/api/runs?offset=50&unassigned=true'
      ? { runs: [{ ...row(older, 'failed'), created_at: null }], next_offset: null }
      : { runs: ++firstPageReads === 1 ? firstPage : [{ ...firstPage[0], state: 'running', retry_successor_id: older }, ...firstPage.slice(1)], next_offset: 50 } }))
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    await act(async () => { render(<App />) })
    const firstLink = runLink(first)
    firstLink.focus()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Показать ещё' })); await Promise.resolve() })
    expect(runLink(older)).toBeTruthy()
    expect(screen.getAllByRole('listitem')).toHaveLength(51)
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(fetchMock.mock.calls.filter(call => call[0] === '/api/runs?unassigned=true')).toHaveLength(2)
    expect(within(firstLink.closest('li')!).getByText('Выполняется')).toBeTruthy()
    expect(within(firstLink.closest('li')!).getByText(older)).toBeTruthy()
    expect(runLink(older)).toBeTruthy()
    expect(screen.getAllByRole('listitem')).toHaveLength(51)
    expect(document.activeElement).toBe(firstLink)
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

  it('retries a failed run and keeps predecessor and history navigation', async () => {
    const user = userEvent.setup()
    const nextId = '22345678-1234-1234-1234-123456789abc'
    vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
      if (url === `/api/runs/${runId}/retry` && options?.method === 'POST')
        return { ok: true, json: async () => ({ run_id: nextId }) }
      if (url === `/api/runs/${nextId}`)
        return { ok: true, json: async () => ({ ...snapshot('queued'), retry_of_run_id: runId, retry_eligible: false }) }
      if (url === '/api/runs?unassigned=true')
        return { ok: true, json: async () => ({ runs: [{ id: runId, state: 'failed', created_at: '2026-09-24T10:00:00Z', retry_of_run_id: null, successor_run_id: nextId }] }) }
      return { ok: true, json: async () => ({ ...snapshot('failed'), retry_eligible: true, successor_run_id: null,
        profile_id: 'old-profile', retry_profile_id: 'current-profile', retry_authorization_revision: 2 }) }
    }))
    render(<App />)
    expect(await screen.findByText(/Повтор использует текущий профиль/)).toBeTruthy()
    expect(screen.getByText(/Исходный анализ использовал профиль/)).toBeTruthy()
    await user.click(await screen.findByRole('button', { name: 'Повторить анализ' }))
    expect(await screen.findByText('Повтор анализа', { exact: false })).toBeTruthy()
    expect(location.pathname).toBe(`/runs/${nextId}`)
    expect(screen.queryByRole('button', { name: 'Повторить анализ' })).toBeNull()
    await user.click(screen.getByRole('link', { name: 'Анализы' }))
    expect(await screen.findByRole('heading', { name: 'Архив без проекта' })).toBeTruthy()
    expect(runLink(runId)).toBeTruthy()
  })

  it.each(['queued', 'running', 'succeeded'])('does not offer retry for %s', async state => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ ...snapshot(state), retry_eligible: false }) })))
    render(<App />)
    expect(await screen.findByRole('heading', { name: state === 'queued' ? 'Анализ поставлен в очередь' : state === 'running' ? 'Анализ выполняется' : 'Анализ завершён' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Повторить анализ' })).toBeNull()
  })

  it('shows history loading, recovers a failed fetch, and pages into unknown legacy dates', async () => {
    const user = userEvent.setup()
    history.replaceState({}, '', '/history')
    let release: (response: unknown) => void = () => {}
    const first = new Promise(resolve => { release = resolve })
    let calls = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      calls++
      if (calls === 1) return first
      if (url === '/api/runs?offset=50&unassigned=true') return Promise.resolve({ ok: true, json: async () => ({
        runs: [{ id: runId, state: 'failed', created_at: null, retry_of_run_id: null, successor_run_id: null }], next_offset: null,
      }) })
      return Promise.resolve({ ok: true, json: async () => ({
        runs: [{ id: '22345678-1234-1234-1234-123456789abc', state: 'queued', created_at: '2026-09-24T10:00:00Z', retry_of_run_id: null, successor_run_id: null }], next_offset: 50,
      }) })
    }))
    render(<App />)
    expect(await screen.findByText('Загружаем историю…')).toBeTruthy()
    expect(screen.queryByText('Анализов пока нет.')).toBeNull()
    await act(async () => { release({ ok: false }) })
    await user.click(await screen.findByRole('button', { name: 'Повторить загрузку' }))
    await user.click(await screen.findByRole('button', { name: 'Показать ещё' }))
    expect(await screen.findByText('Время создания неизвестно')).toBeTruthy()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('ignores a retry response after leaving the failed run', async () => {
    const user = userEvent.setup()
    let release: (response: unknown) => void = () => {}
    const delayed = new Promise(resolve => { release = resolve })
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === `/api/runs/${runId}/retry`) return delayed
      if (url === '/api/runs?unassigned=true') return Promise.resolve({ ok: true, json: async () => ({ runs: [], next_offset: null }) })
      return Promise.resolve({ ok: true, json: async () => ({ ...snapshot('failed'), retry_eligible: true }) })
    }))
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Повторить анализ' }))
    await user.click(screen.getByRole('link', { name: 'Анализы' }))
    await act(async () => { release({ ok: true, json: async () => ({ run_id: '22345678-1234-1234-1234-123456789abc' }) }) })
    expect(location.pathname).toBe('/archive')
    expect(await screen.findByText('Анализов пока нет.')).toBeTruthy()
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
    expect(screen.getByText(/Порядок: Кадр 2 → Кадр 1/)).toBeTruthy()
    expect(screen.getByText('Кадры с экскаватором: Кадр 1.')).toBeTruthy()
    const rows = view.container.querySelectorAll<HTMLElement>('.observation-row')
    expect(inputs[0].sha256).not.toBe(inputs[1].sha256)
    expect(within(rows[0]).getByText('Экскаватор: Обнаружен')).toBeTruthy()
    expect(view.container.querySelector('.result-details')?.textContent).toContain('Входной ID: input-0')
    expect(within(rows[2]).getByText('Экскаватор: Не обнаружен в кадре')).toBeTruthy()
    expect(view.container.querySelector('.result-details')?.textContent).toContain('Входной ID: input-1')
    expect(screen.getByText(/по изображениям не подтверждена/)).toBeTruthy()
    expect(view.container.querySelector('.run-workspace')?.firstElementChild?.classList.contains('result')).toBe(true)
    expect(screen.getByRole('heading', { name: 'Только наблюдения' }).tagName).toBe('H1')
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

  it('shows separate normalized boxes for multiple objects and hides them without hiding the list', async () => {
    const user = userEvent.setup()
    const objects = [
      { input_id: 'input-0', class_name: 'excavator', score: .91, box: [.1, .2, .4, .6], image_size: [1000, 500], invocation_id: 'call-1' },
      { input_id: 'input-0', class_name: 'excavator', score: .83, box: [.5, .1, .9, .7], image_size: [1000, 500], invocation_id: 'call-1' },
    ]
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, objects }) }
      : { ok: true, blob: async () => new Blob(['image']) }))
    const view = render(<App />)
    await screen.findByRole('heading', { name: 'Только наблюдения' })
    await waitFor(() => expect(view.container.querySelectorAll('.result-feature-image .object-box')).toHaveLength(2))
    expect((view.container.querySelector('.object-box') as HTMLElement).style.left).toBe('10%')
    expect(parseFloat((view.container.querySelector('.object-box') as HTMLElement).style.width)).toBeCloseTo(30)
    expect(screen.getByText(/91% — оценка модели/)).toBeTruthy()
    expect(screen.getByText(/83% — оценка модели/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Открыть кадр 1' }))
    expect(screen.getByRole('dialog').querySelectorAll('.object-box')).toHaveLength(2)
    expect(within(screen.getByRole('dialog')).queryAllByRole('button', { name: /Объект [12]: Экскаватор/ })).toHaveLength(0)
    await user.click(screen.getByLabelText('Показывать рамки объектов'))
    expect(view.container.querySelectorAll('.object-box')).toHaveLength(0)
    expect(screen.getByText(/91% — оценка модели/)).toBeTruthy()
  })

  it.each(['unknown', 'ambiguous', 'unsupported-stage'])('requires a supported human selection for the %s stage hypothesis', async proposedStage => {
    const user = userEvent.setup()
    const run = {...completed, result_projection:{...completed.result_projection, stage_hypotheses:[{stage:proposedStage,reason:'Недостаточно данных'}]}}
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
      if (url === `/api/runs/${runId}/confirm-stage`) return {ok:true,json:async()=>JSON.parse(String(options?.body))}
      return url === `/api/runs/${runId}` ? {ok:true,json:async()=>run} : {ok:true,blob:async()=>new Blob(['image'])}
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const select = await screen.findByLabelText('Этап') as HTMLSelectElement
    const confirm = screen.getByRole('button', {name:'Подтвердить этап'})
    expect(select.value).toBe('')
    expect(select.selectedOptions[0].textContent).toBe('Выберите этап')
    expect(confirm).toHaveProperty('disabled', true)
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false)
    await user.selectOptions(select, 'excavation')
    expect(confirm).toHaveProperty('disabled', false)
    await user.click(confirm)
    await screen.findByText(/Человек подтвердил этап/)
    const post = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({stage:'excavation',comment:''})
    expect(run.result_projection.stage_hypotheses[0].stage).toBe(proposedStage)
  })

  it('keeps a known stage proposal separate from explicit human confirmation', async () => {
    const user = userEvent.setup()
    const run = {...completed, result_projection:{...completed.result_projection, stage_hypotheses:[{stage:'excavation',reason:'Виден котлован'}]}}
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
      if (url === `/api/runs/${runId}/confirm-stage`) return {ok:true,json:async()=>JSON.parse(String(options?.body))}
      return url === `/api/runs/${runId}` ? {ok:true,json:async()=>run} : {ok:true,blob:async()=>new Blob(['image'])}
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByLabelText('Этап')).toHaveProperty('value', 'excavation')
    expect(screen.getByRole('button', {name:'Подтвердить этап'})).toHaveProperty('disabled', false)
    expect(screen.queryByText(/Человек подтвердил этап/)).toBeNull()
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false)
    await user.click(screen.getByRole('button', {name:'Подтвердить этап'}))
    await screen.findByText(/Человек подтвердил этап/)
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
  })

  it('switches reconciled and raw detector layers without mixing frames or losing unsupported classes', async () => {
    const user = userEvent.setup()
    const reconciled = [{input_id:'input-0',class_name:'excavator',score:null,box:[.1,.2,.4,.6],image_size:[1000,500],invocation_id:'call'}]
    const models = [{model_id:'apoce',image_size:[1000,500],detections:[{id:'a',input_id:'input-0',raw_class:'lifting-equipment',catalog_class:null,score:.67,box:[.2,.2,.5,.6]}]},
      {model_id:'kaggle',image_size:[1000,500],detections:[{id:'k',input_id:'input-0',raw_class:'Truck',catalog_class:'truck',score:.89,box:[.4,.2,.7,.6]}]}]
    const run = {...completed,objects:reconciled,result_projection:{...completed.result_projection,
      hybrid_frames:[{input_id:'input-0',detectors:{models}},{input_id:'input-1',detectors:{models:[{model_id:'apoce',image_size:[1000,500],detections:[{id:'other',input_id:'input-1',raw_class:'tower-crane',catalog_class:null,score:.99,box:[.7,.1,.9,.9]}]}]}}]}}
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}` ? {ok:true,json:async()=>run} : {ok:true,blob:async()=>new Blob(['image'])}))
    const view = render(<App />)
    const layer = await screen.findByLabelText('Источник рамок')
    const box = () => view.container.querySelector('.result-feature-image .object-box') as HTMLElement
    await waitFor(() => expect(box()?.style.left).toBe('10%'))
    expect(screen.getByText('Числовая уверенность не предоставлена.')).toBeTruthy()
    await user.selectOptions(layer, 'apoce')
    expect(box().style.left).toBe('20%')
    expect(screen.getByRole('button',{name:'1. lifting-equipment'})).toBeTruthy()
    expect(screen.getByText(/67% — оценка модели/)).toBeTruthy()
    expect(screen.queryByText(/99% — оценка модели/)).toBeNull()
    expect(view.container.querySelectorAll('.result-feature-image .object-box')).toHaveLength(1)
    await user.selectOptions(layer, 'kaggle')
    expect(box().style.left).toBe('40%')
    expect(screen.getByRole('button',{name:'1. Грузовик'})).toBeTruthy()
    expect(screen.getByText(/89% — оценка модели/)).toBeTruthy()
    expect(screen.queryByText(/67% — оценка модели/)).toBeNull()
    await user.selectOptions(layer, 'reconciled')
    expect(box().style.left).toBe('10%')
    expect(screen.getByRole('button',{name:'1. Экскаватор'})).toBeTruthy()
    expect(screen.queryByText(/89% — оценка модели/)).toBeNull()
  })

  it('selects the saved supporting frame and keeps technical IDs in details', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/runs/' + runId
      ? { ok: true, json: async () => ({ ...completed, result_projection: {
        ...completed.result_projection, outcome: 'no_check', supporting_input_ids: ['input-1'],
      } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    const view = render(<App />)
    await screen.findByRole('heading', { name: 'Проверка не запрошена' })
    const feature = view.container.querySelector<HTMLElement>('.result-feature-image')!
    expect(await within(feature).findByRole('img', { name: /Кадр 2/ })).toBeTruthy()
    const thumbnails = [...view.container.querySelectorAll<HTMLElement>('.source-thumbnail')]
    expect(thumbnails[0].textContent).not.toContain('Поддерживает вывод')
    expect(thumbnails[1].textContent).toContain('Поддерживает вывод')
    expect(view.container.querySelector('.result-basis')?.textContent).not.toContain('input-1')
    expect(view.container.querySelector('.result-details')?.textContent).toContain('Входной ID: input-1')
    expect(screen.getByText('Этапы анализа').closest('details')?.open).toBe(false)
    await user.click(within(thumbnails[0]).getByRole('button', { name: 'Выбрать кадр 1' }))
    expect(await within(feature).findByRole('img', { name: /Кадр 1/ })).toBeTruthy()
    expect(within(thumbnails[0]).getByRole('button', { name: 'Выбрать кадр 1' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('focuses a completed result after loading without taking focus from later interaction', async () => {
    history.replaceState({}, '', '/new')
    const nextId = '22345678-1234-1234-1234-123456789abc'
    let resolveFirst!: (value: unknown) => void
    let resolveSecond!: (value: unknown) => void
    const first = new Promise(resolve => { resolveFirst = resolve })
    const second = new Promise(resolve => { resolveSecond = resolve })
    vi.stubGlobal('fetch', vi.fn((url: string) => url === '/api/runs/' + runId ? first
      : url === '/api/runs/' + nextId ? second
        : Promise.resolve({ ok: true, blob: async () => new Blob(['jpeg']) })))
    render(<App />)
    act(() => {
      history.pushState({}, '', '/runs/' + runId)
      dispatchEvent(new PopStateEvent('popstate'))
    })
    await screen.findByRole('heading', { name: 'Проверяем анализ…' })
    await act(async () => { resolveFirst({ ok: true, json: async () => completed }) })
    const outcome = await screen.findByRole('heading', { name: 'Только наблюдения' })
    expect(document.activeElement).toBe(outcome)

    act(() => {
      history.pushState({}, '', '/runs/' + nextId)
      dispatchEvent(new PopStateEvent('popstate'))
    })
    await screen.findByRole('heading', { name: 'Проверяем анализ…' })
    const navigation = screen.getByRole('link', { name: 'Проекты' })
    navigation.focus()
    await act(async () => { resolveSecond({ ok: true, json: async () => completed }) })
    expect(document.activeElement).toBe(navigation)
  })

  it('withholds a result whose saved run ID differs from the requested route', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
      ...completed, run_id: '22345678-1234-1234-1234-123456789abc',
    }) })))
    render(<App />)
    expect(await screen.findByText('Получены данные другого анализа. Повторите проверку.', { selector: '.attention p' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Только наблюдения' })).toBeNull()
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

  it('shows persisted stage binding in a source workspace', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === `/api/runs/${runId}`
      ? { ok: true, json: async () => ({ ...completed, context: { ...completed.context, stage_id: 'excavation' } }) }
      : { ok: true, blob: async () => new Blob(['jpeg']) }))
    render(<App />)
    expect(await screen.findByText('Этап строительства:', { exact: false })).toHaveProperty('textContent',
      'Этап строительства: Земляные работы котлована')
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
    ['insufficient_data', 'Недостаточно данных', 'Для проверки правила нужны минимум 3 пригодных кадра одного участка.', observations],
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
    expect(screen.getByText(/Порядок: Кадр 1 → Кадр 2/)).toBeTruthy()
    expect(view.container.querySelectorAll('.source-thumbnail')).toHaveLength(2)
    expect(screen.queryByRole('region', { name: 'Проверка человеком' })).toBeNull()
    if (outcome === 'not_analyzed') {
      const unsupported = [...view.container.querySelectorAll<HTMLElement>('.observation-row')]
        .filter(row => row.textContent?.includes('crane: Не анализировалось'))
      expect(unsupported).toHaveLength(2)
      expect(unsupported[0].textContent).toContain('Класс не поддерживается профилем распознавания.')
      expect(view.container.querySelector('.result-details')?.textContent).toContain('Входной ID: input-0')
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
    expect(view.container.querySelector('.result-details')?.textContent).toContain('Входной ID: input-0')
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
    expect(screen.getByText(/Порядок: Кадр 1 → Кадр 2/)).toBeTruthy()
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
    expect(screen.getByText('Пригодность: пригоден.')).toBeTruthy()
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
    expect(view.container.querySelector('.rule-provenance')?.textContent).toContain('Подтверждающие кадры: Кадр 1.')
    expect(screen.getByText('Неопределённость не указана в проекции.')).toBeTruthy()
    expect(view.container.querySelectorAll('.source-thumbnail')).toHaveLength(inputs.length)
    expect(view.container.querySelector('.result-details')?.textContent).toContain('Исходный артефакт ID: image-0')
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
    expect(panel.textContent).toContain('Подтверждающие кадры: Кадр 1, Кадр 2, Кадр 3.')
    expect(panel.textContent).toContain('Период: 2026-09-23T12:00:00+03:00. Заявленный участок: series_gate')
    expect(panel.textContent).toContain('Рекомендуемая проверка человеком: Проверить вручную.')
    expect(within(panel).getByText('Это рекомендация для проверки, а не подтверждение нарушения.')).toBeTruthy()
    expect(screen.getByText(/ревизия rule-immutable-evidence-v1/)).toBeTruthy()
    expect(document.querySelector('.rule-provenance')?.textContent).toContain('Ожидание: Экскаватор работает постоянно, самосвалы появляются периодически.')
    expect(screen.getByText('Источник правила: demonstration rule.')).toBeTruthy()
    expect(screen.getByText('Необнаружение в кадре не доказывает отсутствие на площадке.')).toBeTruthy()
    const headings = [...document.querySelectorAll('.result h3')].map(item => item.textContent)
    expect(headings).toEqual(['Исходные кадры', 'Основание вывода'])
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
      expect(panel.textContent).toContain(`Заявленный участок: ${expected}`)
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
    expect(document.querySelector('.rule-provenance')?.textContent).toContain('Подтверждающие кадры: Кадр 1, Кадр 2.')
    expect(screen.getByText(/ревизия rule-positive-v1/)).toBeTruthy()
    expect(screen.getByText('Необнаружение в кадре не доказывает отсутствие техники на всей площадке.')).toBeTruthy()
    expect(screen.getByText('Экскаватор: Обнаружен')).toBeTruthy()
    expect(screen.getByText('Самосвал: Обнаружен')).toBeTruthy()
    expect(screen.getByText(/Пригодных кадров: 3\. Кадр 1, Кадр 2, Кадр 3/)).toBeTruthy()
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
    expect(await screen.findAllByText('Пригодность: пригоден.')).toHaveLength(1)
    expect(view.container.querySelector('.result-details')?.textContent).toContain('Исходный артефакт ID: image-0')
    expect(view.container.querySelector('.result-details')?.textContent).toContain('SHA-256: hash-0')
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
    const feature = view.container.querySelector<HTMLElement>('.result-feature-image')!
    await user.click(await within(feature).findByRole('button', { name: 'Повторить' }))
    expect(within(feature).getByText('Загружаем изображение…')).toBeTruthy()
    expect(within(thumbnails[1]).getByRole('img', { name: /Кадр 2/ })).toBeTruthy()
    await act(async () => { resolveRetry({ ok: true, blob: async () => new Blob(['recovered']) }) })
    expect(await within(feature).findByRole('img', { name: /Кадр 1/ })).toBeTruthy()
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
  history.replaceState({}, '', '/new')
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

describe('Zone plan and signals', () => {
  const projectId = '11111111-1111-1111-1111-111111111111'
  const zoneId = '22222222-2222-2222-2222-222222222222'
  const workId = '33333333-3333-3333-3333-333333333333'

  it('saves an editable work as the next zone plan revision', async () => {
    history.replaceState({}, '', `/projects/${projectId}/plan`)
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => ({ ok: true, json: async () =>
      url === '/api/projects' ? { projects: [{ id: projectId, name: 'Объект А', timezone: 'Europe/Moscow' }] } :
      url === '/api/catalog/works' ? { works: [{ id: workId, source_row: 4, code: '10.', title: 'Подготовка' }] } :
      url === `/api/projects/${projectId}/zones` ? { zones: [{ id: zoneId, name: 'Север' }] } :
      url === `/api/zones/${zoneId}/plan` && options?.method === 'PUT' ? { revision_number: 1 } :
      url === `/api/zones/${zoneId}/plan` ? { revision_number: 0, entries: [] } : {} }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByText('Подготовка')
    await user.selectOptions(await screen.findByLabelText('Участок'), zoneId)
    await user.click(await screen.findByRole('button', { name: 'Добавить работу' }))
    await user.selectOptions(screen.getByLabelText('Состояние'), 'active')
    await user.selectOptions(screen.getByLabelText('Сценарий анализа'), 'excavation')
    await user.click(within(screen.getByRole('group', { name: 'Ожидаемая техника · работа 1' })).getByRole('checkbox', { name: 'Экскаватор' }))
    await user.click(screen.getByRole('button', { name: 'Сохранить новую ревизию' }))
    await screen.findByText('Сохранена ревизия 1.')
    const request = fetchMock.mock.calls.find(([url, options]) => url === `/api/zones/${zoneId}/plan` && options?.method === 'PUT')
    const body = JSON.parse(String(request?.[1]?.body))
    expect(body.expected_revision).toBe(0)
    expect(body.entries[0]).toMatchObject({ catalog_work_id: workId, state: 'active', stage_key: 'excavation', expected_equipment: ['excavator'] })
    expect(body.entries[0].start_at).toMatch(/[+-]\d\d:\d\d$/)
  })

  it('filters signals and saves human state with comment', async () => {
    history.replaceState({}, '', '/signals')
    const user = userEvent.setup()
    const signal = { id: 'signal-1', run_id: null, zone_id: zoneId, revision_id: 'revision-1', work_entry_id: null,
      kind: 'completion_unconfirmed', state: 'new', basis: { due_at: '2026-09-25T10:00:00Z' }, comment: '', created_at: '2026-09-25T11:00:00Z' }
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => ({ ok: true, json: async () =>
      options?.method === 'PATCH' ? { id: signal.id, state: 'in_progress', comment: 'Проверяем' }
        : { new_count: 1, signals: url.includes('state=closed') ? [] : [signal] } }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect((await screen.findAllByText('Завершение не подтверждено')).length).toBeGreaterThan(0)
    await user.selectOptions(screen.getByLabelText('Состояние'), 'in_progress')
    await user.type(screen.getByLabelText('Комментарий'), 'Проверяем')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'PATCH')).toBe(true))
    const request = fetchMock.mock.calls.find(([, options]) => options?.method === 'PATCH')
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ state: 'in_progress', comment: 'Проверяем' })
    await user.selectOptions(screen.getByLabelText('Показать'), 'closed')
    expect(await screen.findByText('Сигналов по выбранному фильтру нет.')).toBeTruthy()
  })

  it('binds an analysis to the selected plan revision and each frame time', async () => {
    history.replaceState({}, '', '/new')
    const user = userEvent.setup()
    const revisionId = '44444444-4444-4444-4444-444444444444'
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => ({ ok: true, status: 202, json: async () =>
      url === '/api/projects' ? { projects: [{ id: projectId, name: 'Объект А', timezone: 'Europe/Moscow' }] } :
      url === `/api/projects/${projectId}/zones` ? { zones: [{ id: zoneId, name: 'Север' }] } :
      url === `/api/zones/${zoneId}/plan` ? { revision_id: revisionId, revision_number: 2, entries: [] } :
      url === '/api/runs/single-image' ? { run_id: '12345678-1234-1234-1234-123456789abc' } : snapshot('queued') }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await fillContext(user)
    await user.click(screen.getByRole('button', { name: 'Привязать к плану' }))
    await user.selectOptions(await screen.findByLabelText('Проект плана'), projectId)
    await user.selectOptions(await screen.findByLabelText('Участок плана'), zoneId)
    expect(await screen.findByText('Ревизия плана: 2.')).toBeTruthy()
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('frame.jpg'))
    const time = screen.getByLabelText('Время съёмки') as HTMLInputElement
    fireEvent.change(time, { target: { value: '2026-09-25T12:30' } })
    expect(screen.getByLabelText('Участок наблюдения')).toHaveProperty('readOnly', true)
    await consentToCloud()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, options]) => url === '/api/runs/single-image' && options?.method === 'POST')).toBe(true))
    const request = fetchMock.mock.calls.find(([url, options]) => url === '/api/runs/single-image' && options?.method === 'POST')
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({ project_id: projectId, zone_id: zoneId, plan_revision_id: revisionId,
      observation_area: 'Север', requested_classes: expect.arrayContaining(['road_roller', 'mobile_crane']),
      capture_times: [expect.stringMatching(/^2026-09-25T12:30:00[+-]\d\d:\d\d$/)] })
  })

  it('keeps the submission unbound only after explicit cancellation', async () => {
    history.replaceState({}, '', '/new')
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (_url: string, _options?: RequestInit) => ({ ok: true, json: async () => ({ projects: [] }) }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('frame.jpg'))
    await user.click(screen.getByRole('button', { name: 'Привязать к плану' }))
    await consentToCloud()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText(/Выберите проект и участок с сохранённой ревизией плана/)).toBeTruthy()
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Без привязки к плану' }))
    expect(screen.queryByLabelText('Проект плана')).toBeNull()
  })

  it('submits PNG as observation-only despite historical rule metadata', async () => {
    history.replaceState({}, '', '/new')
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      name: 'Вывоз грунта', revision: 'v1', expectation: 'Самосвал', provenance: 'demo', recommendation: 'Проверить',
    } }])
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)
    await fillContext(user)
    expect(screen.queryByRole('radio', { name: 'Проверить правило этапа' })).toBeNull()
    await user.upload(screen.getByLabelText('Выбрать изображение'), new File([png], 'frame.png', { type: 'image/png' }))
    await consentToCloud()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true))
    expect(JSON.parse(fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')![1].body).intent).toBe('observation_only')
    expect(screen.queryByText(/Текущее правило принимает JPEG/)).toBeNull()
  })
})

describe('About project', () => {
  it('opens directly without API reads and explains the bounded outcomes and source', async () => {
    history.replaceState({}, '', '/about')
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<App />)
    expect(screen.getByRole('heading', { name: 'Контроль строительства' })).toBeTruthy()
    expect(document.title).toBe('О проекте — Контроль строительства')
    expect(screen.getByText(/пригодных кадров должно быть минимум три/)).toBeTruthy()
    expect(screen.getByText(/все наблюдения обязательных классов/)).toBeTruthy()
    expect(screen.getByText(/Это не доказательство нарушения/)).toBeTruthy()
    expect(screen.getByText(/не доказывает отсутствие техники на всей площадке/)).toBeTruthy()
    expect(screen.getByText(/Только распознать технику/)).toBeTruthy()
    expect(screen.getByText(/organizer-archive-site-85-94/)).toBeTruthy()
    expect(screen.getByText(/PNG-файлы преобразованы в JPEG-копии/)).toBeTruthy()
    expect(screen.getByText(/при одном лишь распознавании или недостатке данных такие кадры не выбираются/)).toBeTruthy()
    expect(screen.getByText(/потокам камер/)).toBeTruthy()
    expect(screen.getByText('Команда:', { exact: false })).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
    const logo = container.querySelector('.about-team img') as HTMLImageElement
    fireEvent.error(logo)
    expect(logo.hidden).toBe(true)
    expect(screen.getByText('Команда:', { exact: false })).toBeTruthy()
    await userEvent.setup().click(screen.getByRole('link', { name: 'Вернуться назад' }))
    expect(location.pathname).toBe('/')
    expect(history.state?.aboutFromApp).toBeUndefined()
  })

  it('opens from secondary navigation and team attribution with heading focus and a return path', async () => {
    history.replaceState({}, '', '/')
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ stages: [] }) })))
    const user = userEvent.setup()
    render(<App />)
    const secondary = screen.getByRole('navigation', { name: 'Дополнительная навигация' })
    expect(within(screen.getByRole('navigation', { name: 'Основная навигация' })).queryByRole('link', { name: 'О системе' })).toBeNull()
    await user.click(within(secondary).getByRole('link', { name: 'О системе' }))
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Контроль строительства' }))
    expect(screen.getByRole('link', { name: 'О системе' }).getAttribute('aria-current')).toBe('page')
    await user.click(screen.getByRole('link', { name: 'Вернуться назад' }))
    await waitFor(() => expect(location.pathname).toBe('/'))
    history.forward()
    await waitFor(() => expect(location.pathname).toBe('/about'))
    history.back()
    await waitFor(() => expect(location.pathname).toBe('/'))
    await user.click(screen.getByRole('link', { name: '17 мгновений ИИ' }))
    expect(location.pathname).toBe('/about')
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Контроль строительства' }))
  })
})

async function fillContext(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Сценарий'), 'Земляные работы')
  await user.type(screen.getByLabelText('Участок наблюдения'), 'Северный участок')
}

async function consentToCloud() {
  const consent = screen.getByLabelText(/Разрешаю отправить эти фотографии/) as HTMLInputElement
  await waitFor(() => expect(consent.disabled).toBe(false))
  if (!consent.checked) fireEvent.click(consent)
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

  it('validates dropped files, previews accepted frames, and releases removed previews', async () => {
    const user = userEvent.setup()
    const create = vi.fn().mockReturnValueOnce('blob:first').mockReturnValueOnce('blob:second').mockReturnValueOnce('blob:restored')
    const revoke = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL: create, revokeObjectURL: revoke })
    render(<App />)
    expect(screen.getByText('Включённые примеры').closest('details')?.open).toBe(false)
    const dropzone = screen.getByRole('group', { name: 'Загрузка кадров' })
    fireEvent.drop(dropzone, { dataTransfer: { files: [image('first.jpg'), image('second.jpg')] } })
    expect(await screen.findByText('second.jpg')).toBeTruthy()
    expect(await screen.findAllByRole('img', { name: /Предпросмотр: кадр/ })).toHaveLength(2)
    expect(create).toHaveBeenCalledTimes(2)
    await user.click(screen.getByRole('button', { name: 'Удалить: first.jpg, кадр 1' }))
    expect(revoke).toHaveBeenCalledWith('blob:first')
    await user.click(screen.getByRole('button', { name: 'Вернуть' }))
    expect(await screen.findByRole('img', { name: 'Предпросмотр: кадр 1, first.jpg' })).toBeTruthy()
    expect(create).toHaveBeenCalledTimes(3)
    fireEvent.drop(dropzone, { dataTransfer: { files: [new File(['bad'], 'bad.gif', { type: 'image/gif' })] } })
    await waitFor(() => expect(document.getElementById('images-error')?.textContent).toContain('bad.gif: Поддерживаются файлы JPEG'))
  })

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
      await user.upload(screen.getByLabelText('Выбрать изображение'), image('mine.jpg'))
      await user.click(screen.getByText('Включённые примеры'))
      await user.click(screen.getByRole('button', { name: demo.label }))
      expect(await screen.findByText('Screenshot_' + demo.frames[2].sourceMember.match(/\d+/)![0] + '.jpg')).toBeTruthy()
      expect(screen.queryByText('mine.jpg')).toBeNull()
      expect((screen.getByLabelText('Сценарий') as HTMLInputElement).value).toBe(demo.scenario)
      expect((screen.getByLabelText('Участок наблюдения') as HTMLInputElement).value).toBe(demo.observationArea)
      expect((screen.getByLabelText('Дата и время наблюдения') as HTMLInputElement).value).toBe(demo.period)
      expect(screen.queryByRole('radio', { name: 'Проверить правило этапа' })).toBeNull()
      expect(screen.queryByText(demo.ruleRevision)).toBeNull()
      expect(screen.getByText(/В исходном примере время 12:00 условное/)).toBeTruthy()
      expect(screen.getByText(/порядок кадров соответствует архиву/)).toBeTruthy()
      await user.click(screen.getByRole('button', { name: `Выше: Screenshot_${demo.frames[1].sourceMember.match(/\d+/)![0]}.jpg, кадр 2` }))
      expect(screen.queryByText(/порядок кадров соответствует архиву/)).toBeNull()
      await user.click(screen.getByRole('button', { name: `Ниже: Screenshot_${demo.frames[1].sourceMember.match(/\d+/)![0]}.jpg, кадр 1` }))
      await user.type(screen.getByLabelText('Сценарий'), ' — уточнено')
      await consentToCloud()
      await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      await waitFor(() => expect(fetchMock.mock.calls.some(call => call[0] === '/api/runs/series')).toBe(true))
      const request = JSON.parse(fetchMock.mock.calls.find(call => call[0] === '/api/runs/series')![1]!.body as string)
      expect(request).toMatchObject({ intent: 'observation_only', stage: 'excavation', scenario: demo.scenario + ' — уточнено', observation_area: demo.observationArea })
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('mine.jpg'))
    await user.click(screen.getByText('Включённые примеры'))
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('mine.jpg'))
    await user.click(screen.getByText('Включённые примеры'))
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
    await user.click(screen.getByText('Включённые примеры'))
    await user.click(screen.getByRole('button', { name: demo.label }))
    expect(await screen.findByText('Screenshot_90.jpg')).toBeTruthy()
    await act(async () => finishCapture(new Blob([jpeg], { type: 'image/jpeg' })))
    expect(screen.queryByText(/camera-\d+\.jpg/)).toBeNull()
    expect(screen.getAllByRole('listitem').filter(row => row.classList.contains('frame'))).toHaveLength(3)
    expect(stop).toHaveBeenCalled()
  })

  it('preserves an edited draft on unavailable demo and leaves an uncertain pending body untouched', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', configuredChoices.stages)
    render(<App />)
    await user.type(screen.getByLabelText('Сценарий'), 'Мой сценарий')
    await user.click(screen.getByText('Включённые примеры'))
    await user.click(screen.getByRole('button', { name: demoCases.cases[0].label }))
    expect(await screen.findByText(/Не удалось загрузить и проверить все кадры примера/)).toBeTruthy()
    expect((screen.getByLabelText('Сценарий') as HTMLInputElement).value).toBe('Мой сценарий')
    cleanup()
    const saved = { endpoint: '/api/runs/series', body: '{"original":true}', key: 'original-key' }
    sessionStorage.setItem('observation-pending', JSON.stringify(saved))
    render(<App />)
    await user.click(screen.getByText('Включённые примеры'))
    await screen.findByText(/загрузка примера недоступна/)
    expect(screen.getByRole('button', { name: demoCases.cases[0].label })).toHaveProperty('disabled', true)
    expect(sessionStorage.getItem('observation-pending')).toBe(JSON.stringify(saved))
  })

  it('loads live choices and defaults to observation-only submission', async () => {
    vi.stubGlobal('__ANALYSIS_CHOICES__', undefined)
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => configuredChoices })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await waitFor(() => expect((screen.getByRole('button', { name: 'Запустить анализ' }) as HTMLButtonElement).disabled).toBe(false))
    expect(fetchMock.mock.calls[0][0]).toBe('/api/analysis-choices')
    expect(screen.queryByRole('radio', { name: 'Только распознать технику' })).toBeNull()
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
    await user.type(screen.getByLabelText('Участок наблюдения'), 'Северный участок')
    await user.click(screen.getByRole('button', { name: 'Повторить загрузку настроек' }))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Запустить анализ' }) as HTMLButtonElement).disabled).toBe(false))
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect((screen.getByLabelText('Участок наблюдения') as HTMLInputElement).value).toBe('Северный участок')
    expect((screen.getByRole('button', { name: 'Запустить анализ' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps an explicit observation preference across stage changes', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', configuredChoices.stages)
    render(<App />)
    expect(screen.queryByRole('radio', { name: 'Только распознать технику' })).toBeNull()
    await user.selectOptions(screen.getByLabelText('Этап'), 'other')
    await user.selectOptions(screen.getByLabelText('Этап'), 'excavation')
    expect(screen.queryByRole('radio', { name: 'Только распознать технику' })).toBeNull()
    expect(screen.queryByRole('radio', { name: 'Проверить правило этапа' })).toBeNull()
  })

  it('offers observation-only for every declared stage despite historical choice metadata', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      name: 'Проверка вывоза грунта на этапе земляных работ',
      revision: 'rule-34a0c9535d378f7482cac065e0d474e7b33a4fb545beee1922b962a837b9d97d',
      expectation: 'Экскаватор работает постоянно, самосвалы появляются периодически.',
      provenance: 'demonstration rule', recommendation: 'Проверить организацию вывоза грунта на участке вручную.',
    } }, { id: 'other', label: 'Другой этап', rule: null }])
    render(<App />)
    expect(screen.queryByRole('radio', { name: 'Только распознать технику' })).toBeNull()
    expect(screen.queryByText('Проверка вывоза грунта на этапе земляных работ')).toBeNull()
    expect(screen.queryByText('rule-34a0c9535d378f7482cac065e0d474e7b33a4fb545beee1922b962a837b9d97d')).toBeNull()
    expect(screen.queryByText('Экскаватор работает постоянно, самосвалы появляются периодически.')).toBeNull()
    expect(screen.queryByText('demonstration rule')).toBeNull()
    expect(screen.getByText(/Участок: не указана/)).toBeTruthy()
    await user.selectOptions(screen.getByLabelText('Этап'), 'other')
    expect(screen.queryByRole('radio', { name: 'Только распознать технику' })).toBeNull()
    expect(screen.queryByRole('radio', { name: 'Проверить правило этапа' })).toBeNull()
    expect(screen.getByText(/DeepSeek распознаёт технику и анализирует контекст/)).toBeTruthy()
  })

  it('uses observation-only for short uploads even when old choices contain a rule', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('__ANALYSIS_CHOICES__', [{ id: 'excavation', label: 'Земляные работы', rule: {
      name: 'Проверка вывоза грунта', revision: 'v1', expectation: 'Техника', provenance: 'demonstration rule', recommendation: 'Проверить',
    } }])
    const post = vi.fn().mockResolvedValue({ status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
    await screen.findByText('one.jpg')
    expect(screen.queryByRole('radio', { name: 'Проверить правило этапа' })).toBeNull()
    expect(screen.queryByText(/нужны минимум три пригодных кадра/)).toBeNull()
    await consentToCloud()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(JSON.parse(post.mock.calls[0][1].body)).toMatchObject({ intent: 'observation_only', stage: 'excavation' })
  })

  it('requires explicit cloud consent before a valid upload can be submitted', async () => {
    const user = userEvent.setup()
    const post = vi.fn()
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
    expect((screen.getByLabelText(/Разрешаю отправить эти фотографии/) as HTMLInputElement).checked).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText(/Для анализа требуется согласие/)).toBeTruthy()
    expect(post.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0)
  })

  it('submits reordered distinct bytes and retains duplicate frames', async () => {
    const user = userEvent.setup()
    const post = vi.fn().mockImplementation(async (url: string) => /^\/api\/runs\/[0-9a-f-]{36}$/i.test(url)
      ? { ok: true, json: async () => snapshot('queued') }
      : { status: 202, json: async () => ({ run_id: '12345678-1234-1234-1234-123456789abc' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), [image('first.jpg', 1), image('second.jpg', 2), image('duplicate.jpg', 1)])
    await screen.findByText('Кадр 3')
    await user.click(screen.getByRole('button', { name: /Выше: second.jpg/ }))
    const rows = screen.getAllByRole('listitem').filter(row => row.classList.contains('frame'))
    expect(within(rows[0]).getByText('second.jpg')).toBeTruthy()
    expect(within(rows[1]).getByText('first.jpg')).toBeTruthy()
    await consentToCloud()
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
    expect(body.stage_id).toBe('excavation')
    expect(body.images_base64).toHaveLength(3)
    expect(body.images_base64).toEqual([btoa(String.fromCharCode(...jpeg, 2)), btoa(String.fromCharCode(...jpeg, 1)), btoa(String.fromCharCode(...jpeg, 1))])
    expect(body.period).toMatch(/[+-]\d\d:\d\d$/)
  })

  it('rejects only invalid file and restores a removed frame in its prior position', async () => {
    const user = userEvent.setup({ applyAccept: false })
    render(<App />)
    expect(screen.getByRole('link', { name: 'К основному содержимому' })).toHaveProperty('hash', '#main')
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), [image('first.jpg'), new File(['bad'], 'bad.png', { type: 'image/png' }), image('third.jpg')])
    expect((await screen.findAllByText(/bad.png: Файл не удалось прочитать как изображение/)).length).toBeGreaterThan(0)
    expect(screen.getByText('third.jpg')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Удалить: first.jpg/ }))
    await user.click(screen.getByRole('button', { name: 'Вернуть' }))
    const rows = screen.getAllByRole('listitem').filter(row => row.classList.contains('frame'))
    expect(within(rows[0]).getByText('first.jpg')).toBeTruthy()
    expect(within(rows[1]).getByText('third.jpg')).toBeTruthy()
    expect(screen.getByLabelText('Сценарий')).toHaveProperty('value', 'Земляные работы')
  })

  it('accepts PNG with matching signature and preserves its original bytes in the request', async () => {
    const user = userEvent.setup()
    const post = vi.fn(async (url: string, _options?: RequestInit) => ({ status: 202, ok: true,
      json: async () => url === '/api/runs/single-image'
        ? { run_id: '12345678-1234-1234-1234-123456789abc' }
        : snapshot('queued') }))
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), new File([png], 'frame.png', { type: 'image/png' }))
    expect(await screen.findByText('frame.png')).toBeTruthy()
    await consentToCloud()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(post.mock.calls.some(([url, options]) => url === '/api/runs/single-image' && options?.method === 'POST')).toBe(true))
    const request = post.mock.calls.find(([url, options]) => url === '/api/runs/single-image' && options?.method === 'POST')
    expect(JSON.parse(String(request?.[1]?.body)).image_base64).toBe(btoa(String.fromCharCode(...png)))
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
    await consentToCloud()
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
      await user.upload(screen.getByLabelText('Выбрать изображение'), filenames.map(name => image(name)))
      await screen.findByText(`Кадр ${filenames.length}`)
      const deadlines: Array<() => void> = []
      const realSetTimeout = globalThis.setTimeout
      vi.spyOn(globalThis, 'setTimeout').mockImplementation((callback, delay) => {
        if (delay === 10000) { deadlines.push(callback as () => void); return 0 as ReturnType<typeof setTimeout> }
        return realSetTimeout(callback, delay)
      })
      await consentToCloud()
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
      expect(location.pathname).toBe('/new')
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
    expect(location.pathname).toBe('/new')
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    await consentToCloud()
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('two.jpg'))
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    await consentToCloud()
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    await consentToCloud()
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
      await user.upload(screen.getByLabelText('Выбрать изображение'), filenames.map(name => image(name)))
      await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
      await consentToCloud()
      await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      expect(await screen.findByText(/Отправка завершилась ошибкой.*новый ключ отправки/)).toBeTruthy()
      expect(post).toHaveBeenCalledTimes(1)
      expect(sessionStorage.getItem('observation-pending')).toBeNull()
      expect(screen.queryByRole('button', { name: 'Повторить отправку' })).toBeNull()
      expect(screen.getByLabelText('Сценарий')).toHaveProperty('disabled', false)
      for (const filename of filenames) expect(screen.getByText(filename)).toBeTruthy()
      await user.clear(screen.getByLabelText('Сценарий'))
      await user.type(screen.getByLabelText('Сценарий'), 'Новый сценарий')
      await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
      await consentToCloud()
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
    await consentToCloud()
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
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
    await user.upload(screen.getByLabelText('Выбрать изображение'), [image('good.jpg'), image('broken.jpg'), image('large.jpg')])
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
    fireEvent.change(screen.getByLabelText('Выбрать изображение'), { target: { files: [image('slow.jpg')] } })
    await waitFor(() => expect(finishDecode).toBeTypeOf('function'))
    expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', true)
    fireEvent.submit(screen.getByRole('button', { name: 'Запустить анализ' }).closest('form')!)
    expect(post).not.toHaveBeenCalled()
    await act(async () => finishDecode({ width: 2, height: 2, close: vi.fn() }))
    await screen.findByText('slow.jpg')
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('checked', false)
    expect(post).not.toHaveBeenCalled()
    await user.click(screen.getByLabelText(/Разрешаю отправить эти фотографии/))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(JSON.parse(post.mock.calls[0][1].body).image_base64).toBe(btoa(String.fromCharCode(...jpeg, 0)))
  })

  it('does not let consent for the old batch authorize a frame validated during submit', async () => {
    const user = userEvent.setup()
    let finishDecode!: (value: { width: number; height: number; close: () => void }) => void
    vi.stubGlobal('createImageBitmap', vi.fn()
      .mockResolvedValueOnce({ width: 2, height: 2, close: vi.fn() })
      .mockImplementationOnce(() => new Promise(resolve => { finishDecode = resolve })))
    const post = vi.fn().mockResolvedValue({ status: 202, json: async () => ({ code: 'submission_in_progress' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('approved.jpg', 1))
    await screen.findByText('approved.jpg')
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    await user.click(screen.getByLabelText(/Разрешаю отправить эти фотографии/))
    expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('checked', true)
    fireEvent.change(screen.getByLabelText('Выбрать изображение'), { target: { files: [image('new.jpg', 2)] } })
    await waitFor(() => expect(finishDecode).toBeTypeOf('function'))
    expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', true)
    fireEvent.submit(screen.getByRole('button', { name: 'Запустить анализ' }).closest('form')!)
    await act(async () => finishDecode({ width: 2, height: 2, close: vi.fn() }))
    await screen.findByText('new.jpg')
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    expect(post).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('observation-pending')).toBeNull()
    expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('checked', false)
    await user.click(screen.getByLabelText(/Разрешаю отправить эти фотографии/))
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(JSON.parse(post.mock.calls[0][1].body)).toMatchObject({ cloud_processing_consent: true,
      images_base64: [btoa(String.fromCharCode(...jpeg, 1)), btoa(String.fromCharCode(...jpeg, 2))] })
  })

  it('treats a malformed definitive rejection as resolved and permits a new key', async () => {
    const user = userEvent.setup()
    const post = vi.fn().mockResolvedValueOnce({ status: 400, json: async () => { throw new Error('bad JSON') } })
      .mockResolvedValueOnce({ status: 202, json: async () => ({ code: 'submission_in_progress' }) })
    vi.stubGlobal('fetch', post)
    render(<App />)
    await fillContext(user)
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    await consentToCloud()
    await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText(/Сервер отклонил запрос/)).toBeTruthy()
    expect(sessionStorage.getItem('observation-pending')).toBeNull()
    await waitFor(() => expect(screen.getByLabelText(/Разрешаю отправить эти фотографии/)).toHaveProperty('disabled', false))
    await consentToCloud()
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
    const navigationButton = screen.getByRole('link', { name: 'Создать проект' })
    navigationButton.focus()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(within(list).getAllByRole('listitem')[0].textContent).toContain('Завершено')
    expect(list.querySelector('time')?.getAttribute('datetime')).toBe('2026-09-23T08:00:00Z')
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
    expect(screen.getAllByText('Проверка пригодности кадров').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Проверить статус' }))
    await act(async () => { await Promise.resolve() })
    expect(screen.getByRole('button', { name: 'Проверяем статус…' })).toHaveProperty('disabled', true)
    expect(screen.getByRole('heading', { name: 'Анализ выполняется' }).closest('.run-workspace')?.getAttribute('aria-busy')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: 'Проверяем статус…' }))
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[2][0]).toBe(`/api/runs/${runId}`)
    fireEvent.click(screen.getByRole('link', { name: 'Создать проект' }))
    await act(async () => { resolveLate({ ok: true, json: async () => snapshot('failed') }); await Promise.resolve() })
    expect(fetchMock.mock.calls[2][1].signal.aborted).toBe(true)
    expect(screen.getByRole('heading', { name: 'Проекты' })).toBeTruthy()
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
    expect(screen.getAllByText('Проверка пригодности кадров').length).toBeGreaterThan(0)
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
    expect(screen.getAllByText('Проверка пригодности кадров').length).toBeGreaterThan(0)
  })

  it('keeps undo disabled when a restored frame would exceed eight', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.upload(screen.getByLabelText('Выбрать изображение'), Array.from({ length: 8 }, (_, index) => image(`${index}.jpg`, index)))
    await screen.findByText('Кадр 8')
    await user.click(screen.getByRole('button', { name: /Удалить: 0.jpg/ }))
    await user.upload(screen.getByLabelText('Выбрать изображение'), image('replacement.jpg'))
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
      await user.upload(screen.getByLabelText('Выбрать изображение'), image('one.jpg'))
      fireEvent.change(screen.getByLabelText('Дата и время наблюдения'), { target: { value: '2026-03-08T02:30' } })
      await consentToCloud()
      await user.click(screen.getByRole('button', { name: 'Запустить анализ' }))
      expect((await screen.findAllByText(/Укажите существующие местные дату и время/)).length).toBeGreaterThan(0)
    } finally { vi.unstubAllEnvs() }
  })
})

it('jumps straight to received pipeline stages and removes processing immediately on completion',async()=>{
 history.replaceState({},'', '/runs/12345678-1234-1234-1234-123456789abc')
 localStorage.removeItem('analysis-motion')
 let index=0
 const snapshots=[snapshot('running',['succeeded','succeeded','running','pending','pending','pending']),snapshot('running',['succeeded','succeeded','succeeded','skipped','skipped','running'],{3:'not_applicable',4:'not_applicable'}),snapshot('succeeded',['succeeded','succeeded','succeeded','skipped','skipped','succeeded'])]
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>snapshots[Math.min(index++,2)]})))
 vi.useFakeTimers()
 try{
  await act(async()=>{render(<App/>)})
  expect(document.querySelector('.analysis-scene.is-recognizing')).toBeTruthy()
  expect(within(screen.getByRole('list',{name:'Краткие этапы'})).getAllByRole('listitem')).toHaveLength(6)
  await act(async()=>{await vi.advanceTimersByTimeAsync(3000)})
  expect(within(screen.getByRole('region',{name:'Ход анализа'})).getByRole('heading').textContent).toBe('Формирование результата')
  expect(document.querySelector('.analysis-scene.is-recognizing')).toBeNull()
  expect(document.querySelectorAll('.analysis-route .route-skipped')).toHaveLength(2)
  await act(async()=>{await vi.advanceTimersByTimeAsync(3000)})
  expect(document.querySelector('.analysis-scene')).toBeNull()
 }finally{vi.useRealTimers();cleanup();vi.unstubAllGlobals()}
})

it('retries a failed processing thumbnail without nesting buttons or changing selected frame',async()=>{
 history.replaceState({},'', '/runs/12345678-1234-1234-1234-123456789abc')
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:photo')})
 Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
 let attempts=0
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.endsWith('/thumbnail')?(++attempts===1?{ok:false,json:async()=>({})}:{ok:true,blob:async()=>new Blob(['image'])}):url.includes('/artifacts/')?{ok:true,blob:async()=>new Blob(['image'])}:{ok:true,json:async()=>({...snapshot('running',['succeeded','succeeded','running','pending','pending','pending']),inputs:[{input_id:'f1',ordinal:0,artifact_id:'a1',sha256:'s1'},{input_id:'f2',ordinal:1,artifact_id:'a2',sha256:'s2'}]})}))
 try{
  render(<App/>);const thumbnails=await screen.findByLabelText('Кадры обработки')
  const retry=await within(thumbnails).findByRole('button',{name:'Повторить'})
  expect(thumbnails.querySelector('button button')).toBeNull()
  const first=within(thumbnails).getByRole('button',{name:'Кадр 1'})
  expect(first.getAttribute('aria-pressed')).toBe('true')
  await userEvent.setup().click(retry)
  await waitFor(()=>expect(attempts).toBe(3))
  expect(first.getAttribute('aria-pressed')).toBe('true')
  expect(within(thumbnails).queryByRole('button',{name:'Повторить'})).toBeNull()
 }finally{cleanup();vi.unstubAllGlobals()}
})
