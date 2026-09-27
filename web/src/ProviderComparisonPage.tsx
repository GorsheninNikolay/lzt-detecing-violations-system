import { equipmentLabel } from './displayLabels'
import { useEffect, useState, type RefObject } from 'react'

type Cell = { repeat_ordinal: number; fixture_ordinal: number; candidate_ordinal: number; run_id: string | null; state: string; error_code: string | null; latency_ms: number | null; observed_outcome: string | null; observations: { frame_ordinal: number; class_name: string; state: string }[] }
type Candidate = {
  ordinal: number; kind: string; profile_revision: string | null; model_revision: string | null; requested_identity: string | null
  returned_identity: string | null; authorization_revision: number | null; identity_gap: string | null
  admission: { status: string; authorization_state: string | null; current_revision: number | null; evidence: string; cloud_data_gate: string; data_decision_revision: string | null; data_checked_at: string | null; commercial_gate: string }
  accounting: { planned: number; terminal: number; succeeded: number; failed: number; timed_out: number; pending: number; missing: number }
  repeat_disagreement: { numerator: number; denominator: number; evidence: { fixture_ordinal: number; run_ids: string[] }[] }
  latency_ms: { availability: string; succeeded_count: number; failed_count: number }
  cost: { availability: string; reason: string }
}
type Comparison = { campaign: { id: string; revision_number: number; evaluation_revision_id: string }; repeats: number; fixtures: { ordinal: number; scenario: string; expected_outcome: string; frames: { ordinal: number; manual_labels: Record<string, 'yes' | 'no' | 'unknown'> }[] }[]; candidates: Candidate[]; cells: Cell[]; complete: boolean }
type Fixture = Comparison['fixtures'][number]

const STATE_NAMES: Record<string, string> = { planned: 'Запланирована', queued: 'В очереди', running: 'Выполняется', succeeded: 'Завершена', failed: 'Ошибка', missing: 'Отсутствует' }
const CANDIDATE_NAMES: Record<string, string> = { grounding_dino: 'Grounding DINO (локально)', 'qwen3.6': 'Qwen 3.6 (облако)' }
const SCENARIO_NAMES: Record<string, string> = { single_both: 'Один кадр: оба класса', single_excavator: 'Один кадр: экскаватор', positive_series: 'Серия с двумя классами', check_request_series: 'Серия с запросом проверки', insufficient_series: 'Недостаточная серия', out_of_scope: 'Вне области правила' }
const OUTCOME_NAMES: Record<string, string> = { observations_only: 'Только наблюдения', no_check: 'Проверка не запрошена', check_requested: 'Запрошена проверка человеком', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось' }
const OBSERVATION_NAMES: Record<string, string> = { detected: 'Обнаружен', not_detected_in_frame: 'Не обнаружен в кадре', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировался' }
const LABEL_NAMES = { yes: 'Да', no: 'Нет', unknown: 'Неизвестно' }
const ADMISSION_NAMES: Record<string, string> = { admitted: 'допущен', draft: 'черновик', enabled: 'действует', revoked: 'отозван', missing: 'отсутствует' }
const GAP_NAMES: Record<string, string> = {
  hosted_model_revision_unpinnable: 'Ревизию облачной модели нельзя закрепить',
  awaiting_offline_load: 'Ожидается локальная загрузка модели',
  'local checkpoint digest identifies loaded bytes; no remote model identity was returned': 'Локальная контрольная сумма определяет загруженную модель; удалённый идентификатор не возвращался',
}

function ClassObservations({ fixture, cell }: { fixture: Fixture; cell: Cell }) {
  return <>{cell.state === 'failed' && <p>Наблюдения запуска с ошибкой содержат лишь часть доказательств.</p>}<ul>{fixture.frames.flatMap(frame => Object.entries(frame.manual_labels).map(([name, label]) => {
    const observation = cell.observations.find(item => item.frame_ordinal === frame.ordinal && item.class_name === name)
    const comparison = label === 'unknown' || !observation || !['detected', 'not_detected_in_frame'].includes(observation.state)
      ? 'Сравнение не измерено'
      : label === 'yes' && observation.state === 'not_detected_in_frame' ? 'Пропуск обнаружения'
      : label === 'no' && observation.state === 'detected' ? 'Ложное обнаружение' : null
    return <li key={`${frame.ordinal}-${name}`}>Кадр {frame.ordinal + 1}: {equipmentLabel(name)}: {observation ? OBSERVATION_NAMES[observation.state] ?? observation.state : 'наблюдение отсутствует'}; ручная метка {LABEL_NAMES[label]}{comparison && <>; <strong>{comparison}</strong></>}</li>
  }))}</ul></>
}

export default function ProviderComparisonPage({ heading, onOpen }: { heading: RefObject<HTMLHeadingElement | null>; onOpen: (path: string) => void }) {
  const [snapshot, setSnapshot] = useState<{ data: Comparison; readAt: string } | null>(null)
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const timeout = setTimeout(() => { controller.abort(); if (!cancelled) setError('Не удалось обновить сравнение.') }, 10000)
    setLoading(true)
    void fetch('/api/provider-comparison', { signal: controller.signal, cache: 'no-store' }).then(async response => {
      if (response.status === 404) {
        if (snapshot) throw new Error('stale')
        setError('')
        return
      }
      if (!response.ok) throw new Error('unavailable')
      const data = await response.json() as Comparison
      if (!controller.signal.aborted && !cancelled) { setSnapshot({ data, readAt: new Date().toISOString() }); setError('') }
    }).catch(() => { if (!cancelled && !controller.signal.aborted) setError('Не удалось обновить сравнение.') })
      .finally(() => { clearTimeout(timeout); if (!cancelled) { setLoading(false); setLoaded(true) } })
    return () => { cancelled = true; clearTimeout(timeout); controller.abort() }
  }, [attempt])

  const data = snapshot?.data
  return <section className="provider-comparison" aria-labelledby="provider-comparison-heading" aria-busy={loading}>
    <div className="page-intro"><p className="eyebrow">Исследование прототипа</p><h1 ref={heading} tabIndex={-1} id="provider-comparison-heading">Сравнение моделей ИИ</h1><p>Замороженная кампания: измерения и ограничения каждого кандидата отдельно.</p></div>
    {loading && <p role="status">Загружаем сравнение…</p>}
    {error && <div className="attention" role="alert"><p>{error} {snapshot && 'Показан последний загруженный снимок; данные могут быть устаревшими.'}</p>{snapshot && <p>Время успешной загрузки: <time dateTime={snapshot.readAt}>{snapshot.readAt}</time>.</p>}<button type="button" className="secondary" disabled={loading} onClick={() => setAttempt(value => value + 1)}>Повторить загрузку</button></div>}
    {loaded && !data && !error && <div className="panel" role="status"><p>Нет данных: сравнительная кампания пока не сохранена.</p><button type="button" className="secondary" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку</button></div>}
    {data && <>
      <section className="panel"><h2>Кампания № {data.campaign.revision_number}</h2><p>Идентификатор кампании: <code>{data.campaign.id}</code></p><p>Ревизия набора оценки: <code>{data.campaign.evaluation_revision_id}</code></p><p>Время успешной загрузки: <time dateTime={snapshot!.readAt}>{snapshot!.readAt}</time></p><button type="button" className="secondary" disabled={loading} onClick={() => setAttempt(value => value + 1)}>Обновить сравнение</button>{!data.complete ? <p className="attention">Сравнение не завершено</p> : data.candidates.some(candidate => candidate.accounting.failed + candidate.accounting.timed_out > 0) && <p className="attention">Кампания завершена с ошибками; сведения по кандидатам и ячейкам приведены ниже.</p>}</section>
      <section aria-labelledby="candidates-heading"><h2 id="candidates-heading">Кандидаты</h2><div className="provider-candidates">{data.candidates.map(candidate => <article className="panel" key={candidate.ordinal}><h3>{CANDIDATE_NAMES[candidate.kind] ?? candidate.kind}</h3><p>Ячейки: запланировано {candidate.accounting.planned}; завершено {candidate.accounting.terminal}; успешно {candidate.accounting.succeeded}; ошибок {candidate.accounting.failed}; тайм-аутов {candidate.accounting.timed_out}; ожидают {candidate.accounting.pending}; отсутствуют {candidate.accounting.missing}.</p><p>Расхождения повторов: {candidate.repeat_disagreement.denominator ? `${candidate.repeat_disagreement.numerator} / ${candidate.repeat_disagreement.denominator} полных групп` : 'не оценено: нет полных групп повторов'}.</p><p>Задержка измерена: успешные запуски: {candidate.latency_ms.succeeded_count}; запуски с ошибкой: {candidate.latency_ms.failed_count}. Значения и ссылки на запуски приведены в матрице ниже.</p><p>Стоимость недоступна: она не сохранена.</p><details><summary>Технические сведения и ограничения</summary><dl className="readiness-identity"><div><dt>Ревизия профиля</dt><dd><code>{candidate.profile_revision ?? 'не закреплена'}</code></dd></div><div><dt>Ревизия модели</dt><dd>{candidate.model_revision ?? 'не закреплена'}</dd></div><div><dt>Запрошенная модель</dt><dd>{candidate.requested_identity ?? 'не указана'}</dd></div><div><dt>Возвращённая модель по замороженному профилю допуска</dt><dd>{candidate.returned_identity ?? 'не зафиксирована'}</dd></div><div><dt>Ревизия допуска при заморозке</dt><dd>{candidate.authorization_revision ?? 'отсутствует'}</dd></div><div><dt>Текущее записанное состояние профиля и авторизации</dt><dd>{ADMISSION_NAMES[candidate.admission.status] ?? candidate.admission.status}; {candidate.admission.authorization_state ? ADMISSION_NAMES[candidate.admission.authorization_state] ?? candidate.admission.authorization_state : 'состояние неизвестно'}; записанная ревизия {candidate.admission.current_revision ?? 'неизвестна'}</dd></div><div><dt>Замороженное доказательство допуска</dt><dd>{candidate.admission.evidence === 'present' ? 'сохранено' : 'отсутствует'}</dd></div><div><dt>Коммерческие и данные</dt><dd>{candidate.admission.cloud_data_gate === 'recorded' ? `Решение о данных сохранено (${candidate.admission.data_decision_revision ?? 'ревизия неизвестна'}); проверено ${candidate.admission.data_checked_at ?? 'время неизвестно'}` : candidate.admission.cloud_data_gate === 'missing' ? 'Решение о данных отсутствует' : 'Не применимо к локальному профилю'}. {candidate.admission.commercial_gate === 'paid_recorded' ? 'Оплаченный аккаунт подтверждён в сохранённом решении' : candidate.admission.commercial_gate === 'unresolved' ? 'Коммерческие условия не подтверждены' : ''}</dd></div><div><dt>Открытый пробел идентичности</dt><dd>{candidate.identity_gap ? GAP_NAMES[candidate.identity_gap] ?? candidate.identity_gap : 'не указан'}</dd></div></dl>{candidate.repeat_disagreement.evidence.length > 0 && <ul>{candidate.repeat_disagreement.evidence.map(item => <li key={item.fixture_ordinal}>Сценарий {item.fixture_ordinal + 1}: {item.run_ids.map(id => <a key={id} href={`/runs/${id}`} onClick={event => { event.preventDefault(); onOpen(`/runs/${id}`) }}>Запуск {id} </a>)}</li>)}</ul>}</details></article>)}</div></section>
      <section className="panel"><h2>Матрица запусков</h2><div className="readiness-table-wrap"><table className="readiness-table"><caption>Все запланированные ячейки по сценариям, повторам и кандидатам</caption><thead><tr><th scope="col">Сценарий</th><th scope="col">Повтор</th><th scope="col">Кандидат</th><th scope="col">Состояние</th><th scope="col">Ожидаемый итог</th><th scope="col">Ручные метки</th><th scope="col">Наблюдаемый итог и классы</th><th scope="col">Задержка</th><th scope="col">Запуск</th></tr></thead><tbody>{data.cells.map(cell => <tr key={`${cell.fixture_ordinal}-${cell.repeat_ordinal}-${cell.candidate_ordinal}`}><th scope="row">{cell.fixture_ordinal + 1}. {(() => { const scenario = data.fixtures.find(item => item.ordinal === cell.fixture_ordinal)?.scenario; return scenario ? SCENARIO_NAMES[scenario] ?? scenario : 'неизвестен' })()}</th><td>{cell.repeat_ordinal + 1}</td><td>{CANDIDATE_NAMES[data.candidates.find(item => item.ordinal === cell.candidate_ordinal)?.kind ?? ''] ?? `Кандидат ${cell.candidate_ordinal + 1}`}</td><td>{STATE_NAMES[cell.state] ?? cell.state}{cell.error_code && <>: <code>{cell.error_code}</code></>}</td><td>{(() => { const expected = data.fixtures.find(item => item.ordinal === cell.fixture_ordinal)?.expected_outcome; return expected ? OUTCOME_NAMES[expected] ?? expected : 'не указан' })()}</td><td>{data.fixtures.find(item => item.ordinal === cell.fixture_ordinal)?.frames.map(frame => <div key={frame.ordinal}>Кадр {frame.ordinal + 1}: {Object.entries(frame.manual_labels).map(([name, label]) => `${equipmentLabel(name)}: ${LABEL_NAMES[label]}`).join('; ')}</div>)}</td><td>{cell.observed_outcome ? OUTCOME_NAMES[cell.observed_outcome] ?? cell.observed_outcome : 'нет результата'}{['succeeded', 'failed'].includes(cell.state) && cell.observed_outcome && cell.observed_outcome !== data.fixtures.find(item => item.ordinal === cell.fixture_ordinal)?.expected_outcome && <strong className="comparison-mismatch">Итог не совпадает с ожидаемым.</strong>}{(() => { const fixture = data.fixtures.find(item => item.ordinal === cell.fixture_ordinal); return fixture ? <ClassObservations fixture={fixture} cell={cell} /> : 'Наблюдения недоступны' })()}</td><td>{cell.latency_ms === null ? 'не измерена' : `${cell.latency_ms} мс${cell.state === 'failed' ? ' (запуск с ошибкой)' : ''}`}</td><td>{cell.run_id ? <a href={`/runs/${cell.run_id}`} onClick={event => { event.preventDefault(); onOpen(`/runs/${cell.run_id}`) }}>Открыть запуск {cell.run_id}</a> : 'Запуск недоступен'}</td></tr>)}</tbody></table></div></section>
    </>}
  </section>
}
