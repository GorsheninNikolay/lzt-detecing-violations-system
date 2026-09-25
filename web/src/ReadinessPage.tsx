import { useEffect, useState, type RefObject } from 'react'

type Evidence = {
  run_id?: string | null
  run_ids?: string[]
  input_id?: string | null
  input_artifact_id?: string | null
  inputs?: { input_id: string; artifact_id: string | null }[]
  state?: string
  error_code?: string | null
  outcome?: string | null
  observation?: { state: string } | null
  fixture_ordinal?: number
  frame_ordinal?: number
  candidate_ordinal?: number
  repeat_ordinal?: number
  class_name?: string
}
type Criterion = { key: string; status: 'pass' | 'fail' | 'not_evaluated'; reason: string; numerator: number; denominator: number; evidence: Evidence[]; misses: Evidence[] }
type Measure = { numerator?: number; denominator?: number; availability?: string; reason?: string; measured_count?: number; evidence?: Evidence[]; values?: { run_id: string; milliseconds: number }[] }
type Report = { id: string; campaign_id: string; campaign_manifest_hash: string; evaluation_revision_id: string; evaluation_manifest_hash: string; policy_revision: string; evidence_digest: string; status: 'pass' | 'fail' | 'incomplete'; criteria: Criterion[]; measures: Record<string, Measure> }
type Frame = { id: string; ordinal: number; scenario: string; image_sha256: string; manual_labels: Record<string, string>; sufficiency_notes: string }
type Readiness = {
  created_at: string
  report: Report
  evaluation_set: { id: string; revision_number: number; manifest_hash: string; frames: Frame[] }
  fixtures: { ordinal: number; scenario: string; expected_outcome: string }[]
  rule: { name: string; revision: string; policy_revision: string }
}

const CRITERION_NAMES: Record<string, string> = {
  campaign_coverage: 'Покрытие кампании', mandatory_detections: 'Обязательные обнаружения',
  mandatory_outcomes: 'Обязательные итоги', zero_false_warnings: 'Отсутствие ложных запросов проверки',
}
const MEASURE_NAMES: Record<string, string> = {
  planned_cells: 'Ячейки кампании', technical_errors: 'Технические ошибки',
  detection_misses: 'Пропуски обнаружения', false_detections: 'Ложные обнаружения',
  outcome_misses: 'Ошибки итога', false_check_requests: 'Ложные запросы проверки',
  repeat_disagreement: 'Расхождения повторов', latency_ms: 'Задержка, мс',
  cost: 'Стоимость', check_request_comprehension: 'Понимание запроса проверки',
}
const UNAVAILABLE_REASONS: Record<string, string> = {
  cost_not_recorded: 'стоимость не сохранена',
  comprehension_not_recorded: 'понимание запроса проверки не измерялось',
}
const STATUS_NAMES = { pass: 'Пройдено', fail: 'Не пройдено', not_evaluated: 'Нет данных' }
const REPORT_NAMES = { pass: 'Пройдено', fail: 'Не пройдено', incomplete: 'Отчёт неполный' }
const REASON_NAMES: Record<string, string> = {
  observed_failure: 'Есть зафиксированные отклонения', pending_evidence: 'Доказательства ещё не полные',
  all_applicable_passed: 'Все применимые проверки пройдены',
}
const SCENARIO_NAMES: Record<string, string> = {
  single_both: 'Один кадр: оба класса', single_excavator: 'Один кадр: экскаватор',
  positive_series: 'Серия с двумя классами', check_request_series: 'Серия с запросом проверки',
  insufficient_series: 'Недостаточная серия', out_of_scope: 'Вне области правила',
}
const OUTCOME_NAMES: Record<string, string> = {
  observations_only: 'Только наблюдения', no_check: 'Проверка не запрошена',
  check_requested: 'Запрошена проверка человеком', insufficient_data: 'Недостаточно данных',
  not_analyzed: 'Не анализировалось',
}
const STATE_NAMES: Record<string, string> = {
  planned: 'Запланирован', queued: 'В очереди', running: 'Выполняется', succeeded: 'Завершён',
  failed: 'Ошибка', missing: 'Отсутствует',
}
const OBSERVATION_NAMES: Record<string, string> = {
  detected: 'Обнаружен', not_detected_in_frame: 'Не обнаружен в кадре',
  insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировался',
}
const LABEL_NAMES: Record<string, string> = { yes: 'Да', no: 'Нет', unknown: 'Неизвестно' }
const CLASS_NAMES: Record<string, string> = { excavator: 'Экскаватор', dump_truck: 'Самосвал', crane: 'Кран' }

function named(code: string | null | undefined, names: Record<string, string>) {
  return code ? `${names[code] ?? code} (${code})` : 'отсутствует'
}

function expectedObserved(item: Evidence, key: string, snapshot: Readiness) {
  if (key === 'campaign_coverage') return `Ожидалось: завершённая ячейка; получено: ${named(item.state, STATE_NAMES)}.`
  if (['mandatory_outcomes', 'zero_false_warnings', 'outcome_misses', 'false_check_requests'].includes(key)) {
    const expected = snapshot.fixtures.find(fixture => fixture.ordinal === item.fixture_ordinal)?.expected_outcome
    return `Ожидалось: ${named(expected, OUTCOME_NAMES)}; получено: ${named(item.outcome, OUTCOME_NAMES)}.`
  }
  if (['mandatory_detections', 'detection_misses', 'false_detections'].includes(key)) {
    const label = snapshot.evaluation_set.frames.find(frame => frame.ordinal === item.frame_ordinal)?.manual_labels[item.class_name ?? '']
    return `Ручная метка: ${named(label, LABEL_NAMES)}; наблюдение: ${named(item.observation?.state, OBSERVATION_NAMES)}.`
  }
  if (key === 'repeat_disagreement') return 'Ожидались одинаковые результаты повторов; зафиксировано расхождение.'
  return null
}

function EvidenceRows({ evidence, caption, kind, snapshot, onOpen }: {
  evidence: Evidence[]; caption: string; kind: string; snapshot: Readiness; onOpen: (path: string) => void
}) {
  if (!evidence.length) return <p>Сохранённых записей нет.</p>
  return <div className="readiness-table-wrap"><table className="readiness-table"><caption>{caption}</caption><thead><tr><th scope="col">Ячейка</th><th scope="col">Ожидание и факт</th><th scope="col">Запуск и исходные данные</th><th scope="col">Состояние</th></tr></thead><tbody>
    {evidence.map((item, index) => {
      const fixture = snapshot.fixtures.find(value => value.ordinal === item.fixture_ordinal)
      const inputArtifacts = item.inputs?.map(input => input.artifact_id).filter((id): id is string => Boolean(id)) ?? (item.input_artifact_id ? [item.input_artifact_id] : [])
      const runs = item.run_ids ?? (item.run_id ? [item.run_id] : [])
      return <tr key={`${item.run_id ?? item.run_ids?.join('-') ?? 'missing'}-${item.input_id ?? item.frame_ordinal ?? index}-${index}`}>
        <td>{item.repeat_ordinal !== undefined && <>Повтор {item.repeat_ordinal + 1}; </>}{item.fixture_ordinal !== undefined && <>сценарий {item.fixture_ordinal + 1}: {named(fixture?.scenario, SCENARIO_NAMES)}; </>}{item.candidate_ordinal !== undefined && <>кандидат {item.candidate_ordinal + 1}; </>}{item.frame_ordinal !== undefined && <>кадр {item.frame_ordinal + 1}; </>}{item.class_name && (CLASS_NAMES[item.class_name] ?? item.class_name)}</td>
        <td>{expectedObserved(item, kind, snapshot) ?? 'Подробности сохранены в связанном запуске.'}</td>
        <td>{runs.length ? <>{runs.map(id => <div key={id}><a href={`/runs/${id}`} onClick={event => { event.preventDefault(); onOpen(`/runs/${id}`) }}>Открыть запуск {id}</a></div>)}{item.run_id && inputArtifacts.length > 0 && <><ul>{inputArtifacts.map(id => <li key={id}>Исходный артефакт <code>{id}</code></li>)}</ul><p>Исходный кадр и ошибки чтения доступны в запуске.</p></>}{item.run_id && !inputArtifacts.length && <p>Исходный артефакт недоступен.</p>}</> : 'Запуск недоступен'}</td>
        <td>{named(item.state, STATE_NAMES)}{item.error_code && <>: <code>{item.error_code}</code></>}</td>
      </tr>
    })}
  </tbody></table></div>
}

export default function ReadinessPage({ heading, onOpen }: { heading: RefObject<HTMLHeadingElement | null>; onOpen: (path: string) => void }) {
  const [snapshot, setSnapshot] = useState<Readiness | null>(null)
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    let timedOut = false
    let timeout: ReturnType<typeof setTimeout>
    const deadline = new Promise<never>((_, reject) => {
      timeout = setTimeout(() => { timedOut = true; controller.abort(); reject(new Error('timeout')) }, 10000)
    })
    setLoading(true)
    const read = fetch('/api/readiness', { signal: controller.signal, cache: 'no-store' }).then(async response => {
      if (cancelled || controller.signal.aborted) return
      if (response.status === 404) {
        if (snapshot) throw new Error('unavailable')
        setSnapshot(null)
        setError('')
        return
      }
      if (!response.ok) throw new Error('unavailable')
      const next = await response.json() as Readiness
      if (cancelled || controller.signal.aborted) return
      setSnapshot(next)
      setError('')
    })
    void Promise.race([read, deadline]).catch(() => {
      if (!cancelled && (timedOut || !controller.signal.aborted)) setError('Не удалось обновить сохранённый отчёт.')
    }).finally(() => { clearTimeout(timeout); if (!cancelled) { setLoading(false); setLoaded(true) } })
    return () => { cancelled = true; clearTimeout(timeout); controller.abort() }
  }, [attempt])

  const report = snapshot?.report
  const order = { fail: 0, not_evaluated: 1, pass: 2 }
  const criteria = [...(report?.criteria ?? [])].sort((a, b) => order[a.status] - order[b.status])
  const labels = snapshot?.evaluation_set.frames.flatMap(frame => Object.values(frame.manual_labels)) ?? []
  const labelCount = { positive: labels.filter(label => label === 'yes').length,
    negative: labels.filter(label => label === 'no').length,
    unknown: labels.filter(label => label !== 'yes' && label !== 'no').length }
  return <section className="readiness" aria-labelledby="readiness-heading" aria-busy={loading}>
    <div className="page-intro"><p className="eyebrow">Проверка прототипа</p><h1 ref={heading} tabIndex={-1} id="readiness-heading">Готовность</h1><p>Сохранённый отчёт по критериям и исходным доказательствам.</p></div>
    {loading && <p role="status">Загружаем сохранённый отчёт…</p>}
    {error && <div className="attention" role="alert"><p>{error} {snapshot && 'Показана последняя загруженная версия; она может быть устаревшей.'}</p>{snapshot && <p>Время сохранения: <time dateTime={snapshot.created_at}>{snapshot.created_at}</time>.</p>}<button type="button" className="secondary" disabled={loading} onClick={() => setAttempt(value => value + 1)}>Повторить загрузку</button></div>}
    {loaded && !snapshot && !error && <div className="panel" role="status"><p>Нет данных: сохранённого отчёта пока нет.</p><button type="button" className="secondary" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку</button></div>}
    {snapshot && <>
      <section className="panel" aria-labelledby="readiness-report-heading"><h2 id="readiness-report-heading">Сохранённый отчёт</h2><p>Состояние отчёта: <strong>{REPORT_NAMES[snapshot.report.status]}</strong>.</p><p>Время создания: <time dateTime={snapshot.created_at}>{snapshot.created_at}</time></p>{report?.status === 'incomplete' && <p className="attention">Отчёт неполный: часть доказательств ещё отсутствует.</p>}<dl className="readiness-identity"><div><dt>Отчёт</dt><dd><code>{report?.id}</code></dd></div><div><dt>Кампания</dt><dd><code>{report?.campaign_id}</code></dd></div><div><dt>Хеш кампании</dt><dd><code>{report?.campaign_manifest_hash}</code></dd></div><div><dt>Ревизия набора</dt><dd><code>{snapshot.evaluation_set.id}</code> (№ {snapshot.evaluation_set.revision_number})</dd></div><div><dt>Хеш набора</dt><dd><code>{snapshot.evaluation_set.manifest_hash}</code></dd></div><div><dt>Политика готовности</dt><dd><code>{report?.policy_revision}</code></dd></div><div><dt>Правило</dt><dd>{snapshot.rule.name}, <code>{snapshot.rule.revision}</code></dd></div><div><dt>Политика правила</dt><dd><code>{snapshot.rule.policy_revision}</code></dd></div><div><dt>Дайджест доказательств</dt><dd><code>{report?.evidence_digest}</code></dd></div></dl><button type="button" className="secondary" disabled={loading} onClick={() => setAttempt(value => value + 1)}>Обновить отчёт</button></section>
      <section aria-labelledby="criteria-heading"><h2 id="criteria-heading">Критерии</h2><div className="readiness-criteria">{criteria.map(item => {
        const pending = item.evidence.filter(ref => !['succeeded', 'failed'].includes(ref.state ?? ''))
        return <article className={`panel criterion criterion-${item.status}`} key={item.key}><h3>{CRITERION_NAMES[item.key] ?? item.key}</h3><p><strong>{STATUS_NAMES[item.status]}</strong> · {REASON_NAMES[item.reason] ?? item.reason}</p><p>Отклонения: {item.numerator} / {item.denominator}</p><details><summary>Доказательства: {item.evidence.length}; отклонения: {item.misses.length}; ожидают или отсутствуют: {pending.length}</summary>{item.misses.length > 0 && <><h4>Отклонения</h4><EvidenceRows evidence={item.misses} caption="Отклонения критерия" kind={item.key} snapshot={snapshot} onOpen={onOpen} /></>}{pending.length > 0 && <><h4>Ожидающие и отсутствующие доказательства</h4><EvidenceRows evidence={pending} caption="Ожидающие и отсутствующие доказательства критерия" kind={item.key} snapshot={snapshot} onOpen={onOpen} /></>}<h4>Вся совокупность</h4><EvidenceRows evidence={item.evidence} caption="Вся совокупность критерия" kind={item.key} snapshot={snapshot} onOpen={onOpen} /></details></article>
      })}</div></section>
      <section className="panel" aria-labelledby="measures-heading"><h2 id="measures-heading">Буквальные измерения</h2><div className="readiness-table-wrap"><table className="readiness-table"><caption>Значения сохранённых измерений</caption><thead><tr><th scope="col">Измерение</th><th scope="col">Значение и доказательства</th></tr></thead><tbody>{Object.entries(report?.measures ?? {}).map(([key, value]) => <tr key={key}><th scope="row">{MEASURE_NAMES[key] ?? key}</th><td>{value.availability === 'unavailable' ? `Недоступно: ${value.reason ? UNAVAILABLE_REASONS[value.reason] ?? value.reason : 'причина не указана'}` : value.numerator !== undefined ? `${value.numerator} / ${value.denominator}` : value.measured_count !== undefined ? `${value.measured_count} / ${value.denominator} измерений` : 'Нет данных'}{value.evidence && value.evidence.length > 0 && <details><summary>Доказательства: {value.evidence.length}</summary><EvidenceRows evidence={value.evidence} caption={`Доказательства: ${MEASURE_NAMES[key] ?? key}`} kind={key} snapshot={snapshot} onOpen={onOpen} /></details>}{value.values && value.values.length > 0 && <details><summary>Значения задержки: {value.values.length}</summary><ul>{value.values.map((item, index) => <li key={`${item.run_id}-${index}`}><a href={`/runs/${item.run_id}`} onClick={event => { event.preventDefault(); onOpen(`/runs/${item.run_id}`) }}>{item.run_id}</a>: {item.milliseconds} мс</li>)}</ul></details>}</td></tr>)}</tbody></table></div></section>
      <section className="panel" aria-labelledby="evaluation-frames-heading"><h2 id="evaluation-frames-heading">Замороженный набор: {snapshot.evaluation_set.frames.length} кадров</h2><p>Ручные метки: положительные {labelCount.positive}, отрицательные {labelCount.negative}, неизвестные {labelCount.unknown}; всего {labels.length}.</p><div className="readiness-table-wrap"><table className="readiness-table"><caption>Кадры замороженной ревизии и ручная разметка</caption><thead><tr><th scope="col">Кадр и сценарий</th><th scope="col">SHA-256 изображения</th><th scope="col">Ручные метки</th><th scope="col">Достаточность</th></tr></thead><tbody>{snapshot.evaluation_set.frames.map(frame => <tr key={frame.id}><th scope="row">{frame.ordinal + 1}. {frame.id}<br /><small>{named(frame.scenario, SCENARIO_NAMES)}</small></th><td><code>{frame.image_sha256}</code></td><td>{Object.entries(frame.manual_labels).map(([name, label]) => <div key={name}>{CLASS_NAMES[name] ?? name}: {named(label, LABEL_NAMES)}</div>)}</td><td>{frame.sufficiency_notes}</td></tr>)}</tbody></table></div></section>
    </>}
  </section>
}
