import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type RefObject } from 'react'
import demoCases from './demoCases.json'

type Frame = { id: string; file: File }
type DemoCase = (typeof demoCases.cases)[number]
type Pending = { endpoint: string; body: string; key: string }
type Errors = Partial<Record<'scenario' | 'observation_area' | 'period' | 'images' | 'submit', string>>
type Stage = { name: string; state: string; reason?: string | null; timestamp?: string | null }
type Input = { input_id: string; ordinal: number; sha256: string; artifact_id: string | null }
type Observation = { input_id: string; ordinal: number; class_name: string; state: string; reason?: string | null; source_artifact_id: string | null; input_sha256?: string; invocation_id?: string | null }
type NativeEvidence = { artifact_id: string; input_id: string; ordinal: number; sha256: string; invocation_id: string; profile_id: string; profile_revision: number; preprocessing_revision?: string | null }
type Series = { usable_count: number; usable_input_ids: string[]; declared_observation_area: string | null; input_order: string[]; excavator_supporting_input_ids: string[]; dump_truck_persistence_input_ids: string[]; dump_truck_persistence_text: string | null }
type Rule = { name: string; revision: string; expectation: string; provenance: string; recommendation: string | null }
type Choice = { id: string; label: string; rule: Rule | null }
type ResultProjection = { outcome: string; frames?: Observation[]; context?: { period?: string; observation_area?: string; stage_id?: string }; series?: Series; reason?: string | null; uncertainty?: string | null; recommendation?: string | null; rule?: Rule | null; supporting_input_ids?: string[] | null }
type ProfileSnapshot = { adapter?: { code?: string } }
type ResultFrame = { input_id: string; ordinal: number; artifact_id: string | null; sha256: string | null; usable: boolean | null; observations: Observation[] }
type RunSnapshot = { run_id?: string; state: string; stages: Stage[]; context?: { period?: string; observation_area?: string; stage_id?: string }; intent?: string; stage?: string | null; profile_snapshot?: ProfileSnapshot; rule_snapshot?: Rule | null; requested_classes?: string[]; inputs?: Input[]; observations?: Observation[]; native_evidence_by_frame?: NativeEvidence[]; outcome?: string | null; result_projection?: ResultProjection | null; retry_predecessor_id?: string | null; retry_successor_id?: string | null; retry_of_run_id?: string | null; successor_run_id?: string | null; retry_eligible?: boolean; retry_profile_id?: string; retry_authorization_revision?: number; profile_id?: string; authorization_revision?: number; created_at?: string }
type StageSummary = { stage_id: string; name: string; supported: boolean; latest_result: { run_id: string; created_at: string | null; projection: { outcome: string } } | null; latest_lifecycle: { run_id: string; created_at: string | null; state: string } | null }
type HistoryRun = { id: string; run_id: string; created_at: string | null; stage: string | null; intent: string; state: string; outcome: string | null; retry_predecessor_id: string | null; retry_successor_id: string | null; retry_of_run_id?: string | null; successor_run_id?: string | null }
const OUTCOME_LABELS: Record<string, string> = { observations_only: 'Только наблюдения', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось', no_check: 'Проверка не запрошена', check_requested: 'Рекомендована проверка человеком' }

const CLASS_LABELS: Record<string, string> = { excavator: 'Экскаватор', dump_truck: 'Самосвал' }
const OBSERVATION_STATES: Record<string, string> = { detected: 'Обнаружен', not_detected_in_frame: 'Не обнаружен в кадре', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось' }
const OBSERVATION_REASONS: Record<string, string> = { frame_unassessable: 'Кадр непригоден для распознавания.', unsupported_class: 'Класс не поддерживается профилем распознавания.', observer_unavailable: 'Распознавание недоступно.' }

function artifactUrl(runId: string, artifactId: string) { return `/api/runs/${runId}/artifacts/${artifactId}` }

function useArtifact(runId: string, artifactId: string | null) {
  const [attempt, retry] = useState(0)
  const [loaded, setLoaded] = useState<{ id: string; url: string } | null>(null)
  const [failure, setFailure] = useState<{ id: string; code: string } | null>(null)
  useEffect(() => {
    if (!artifactId) return
    const controller = new AbortController()
    let url: string | null = null
    void fetch(artifactUrl(runId, artifactId), { signal: controller.signal }).then(async response => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { code?: string }
        throw new Error(body.code === 'artifact_integrity_failed' ? 'integrity' : 'unavailable')
      }
      url = URL.createObjectURL(await response.blob())
      if (!controller.signal.aborted) { setLoaded({ id: artifactId, url }); setFailure(null) }
      else URL.revokeObjectURL(url)
    }).catch(error => { if (!controller.signal.aborted) setFailure({ id: artifactId, code: error.message === 'integrity' ? 'integrity' : 'unavailable' }) })
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [runId, artifactId, attempt])
  return { url: loaded?.id === artifactId && failure?.id !== artifactId ? loaded.url : null,
    error: failure?.id === artifactId ? failure.code : null,
    retry: () => { setLoaded(null); setFailure(null); retry(value => value + 1) } }
}

function SourceImage({ runId, artifactId, label, description }: { runId: string; artifactId: string | null; label: string; description: string }) {
  const artifact = useArtifact(runId, artifactId)
  return <div className="source-image">{!artifactId ? <p className="error">Исходное изображение недоступно для этого кадра.</p> : artifact.url ? <img src={artifact.url} alt={`Исходное изображение: ${label}. ${description}`} /> :
    artifact.error ? <p className="error">{artifact.error === 'integrity' ? 'Целостность артефакта не подтверждена' : 'Не удалось открыть исходное изображение'} <button type="button" className="secondary" onClick={artifact.retry}>Повторить</button></p> :
      <p className="muted">Загружаем изображение…</p>}</div>
}

function frameDescription(observations: Observation[]): string {
  return observations.map(item =>
    `${CLASS_LABELS[item.class_name] ?? item.class_name}: ${OBSERVATION_STATES[item.state] ?? item.state}${item.reason ? `; ${OBSERVATION_REASONS[item.reason] ?? item.reason}` : ''}`).join('. ')
}

function makeResultFrames(observations: Observation[], inputs: Input[], usableInputIds?: string[], projected = false): ResultFrame[] {
  const inputsById = new Map(inputs.map(input => [input.input_id, input]))
  const frames = new Map<string, ResultFrame>(inputs.map(input => [input.input_id, {
    input_id: input.input_id, ordinal: input.ordinal, artifact_id: input.artifact_id, sha256: input.sha256,
    usable: usableInputIds ? usableInputIds.includes(input.input_id) : null, observations: [],
  }]))
  for (const observation of observations) {
    let frame = frames.get(observation.input_id)
    if (!frame) {
      const input = inputsById.get(observation.input_id)
      frame = { input_id: observation.input_id, ordinal: observation.ordinal,
        artifact_id: observation.source_artifact_id ?? input?.artifact_id ?? null,
        sha256: input?.sha256 ?? observation.input_sha256 ?? null,
        usable: usableInputIds ? usableInputIds.includes(observation.input_id) : null, observations: [] }
      frames.set(observation.input_id, frame)
    }
    if (projected) {
      frame.ordinal = observation.ordinal
      frame.artifact_id = observation.source_artifact_id ?? frame.artifact_id
    }
    frame.observations.push(observation)
  }
  return [...frames.values()].sort((left, right) => left.ordinal - right.ordinal)
}

function EvidenceViewer({ runId, frames, native, profile, context, selected, onClose, onSelect }: {
  runId: string; frames: ResultFrame[]; native: NativeEvidence[]; profile?: ProfileSnapshot; context?: RunSnapshot['context']; selected: number;
  onClose: () => void; onSelect: (index: number) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const handledClose = useRef(false)
  const [zoom, setZoom] = useState(1)
  const [nativeResult, setNativeResult] = useState<{ id: string; text: string } | null>(null)
  const [nativeError, setNativeError] = useState<{ id: string; code: string } | null>(null)
  const [nativeAttempt, retryNative] = useState(0)
  const frame = frames[selected]
  const evidence = native.find(item => item.input_id === frame.input_id)
  const handleClose = () => {
    if (handledClose.current) return
    handledClose.current = true
    onClose()
  }
  useEffect(() => {
    handledClose.current = false
    dialog.current?.showModal()
    return () => { if (dialog.current?.open) dialog.current.close() }
  }, [])
  useEffect(() => {
    if (!evidence) return
    const controller = new AbortController()
    void fetch(artifactUrl(runId, evidence.artifact_id), { signal: controller.signal }).then(async response => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { code?: string }
        throw new Error(body.code === 'artifact_integrity_failed' ? 'integrity' : 'unavailable')
      }
      const text = await response.text()
      if (!controller.signal.aborted) { setNativeResult({ id: evidence.artifact_id, text }); setNativeError(null) }
    }).catch(error => { if (!controller.signal.aborted) setNativeError({ id: evidence.artifact_id, code: error.message === 'integrity' ? 'integrity' : 'unavailable' }) })
    return () => controller.abort()
  }, [runId, evidence?.artifact_id, nativeAttempt])
  return <dialog ref={dialog} aria-label="Просмотр исходных кадров" onClose={handleClose} onKeyDown={event => {
    if (event.key !== 'Tab' || !dialog.current) return
    const focusable = [...dialog.current.querySelectorAll<HTMLElement>('a[href],button:not(:disabled),input:not(:disabled):not([type="hidden"]),select:not(:disabled),textarea:not(:disabled),summary,[tabindex]:not([tabindex="-1"]),[contenteditable="true"]')]
      .filter(element => element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden')
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }} className="evidence-dialog">
    <div className="viewer-toolbar"><button type="button" className="secondary" onClick={() => dialog.current?.close()}>Закрыть</button><button type="button" className="secondary" disabled={selected === 0} onClick={() => { onSelect(selected - 1); setZoom(1) }}>Предыдущий кадр</button><button type="button" className="secondary" disabled={selected === frames.length - 1} onClick={() => { onSelect(selected + 1); setZoom(1) }}>Следующий кадр</button><button type="button" className="secondary" onClick={() => setZoom(value => Math.min(4, value + .5))}>Увеличить</button><button type="button" className="secondary" onClick={() => setZoom(value => Math.max(1, value - .5))}>Уменьшить</button><button type="button" className="secondary" onClick={() => setZoom(1)}>Сбросить масштаб</button></div>
    <p role="status">Кадр {selected + 1} из {frames.length}. Масштаб {Math.round(zoom * 100)}%.</p>
    <p>Номер кадра: {frame.ordinal + 1}. Пригодность: {frame.usable === null ? 'не указана' : frame.usable ? 'пригоден' : 'не пригоден'}.</p>
    <p>Наблюдения: {frameDescription(frame.observations) || 'не указаны'}.</p>
    <p>Входной ID: <code>{frame.input_id}</code>. Период: {context?.period ?? 'не указан'}.</p>
    <p>Исходный артефакт ID: <code>{frame.artifact_id ?? 'не указан'}</code>. SHA-256 исходного кадра: <code>{frame.sha256 ?? 'не указан'}</code>.</p>
    <div className="viewer-image"><div style={{ width: `${zoom * 100}%` }}><SourceImage key={frame.input_id} runId={runId} artifactId={frame.artifact_id} label={`Кадр ${frame.ordinal + 1}`} description={frameDescription(frame.observations)} /></div></div>
    {evidence && <details><summary>Технические данные наблюдателя</summary><p>Данные конкретного наблюдателя. Не используются правилом этапа.</p><p>Адаптер: <code>{profile?.adapter?.code ?? 'не указан'}</code>. Профиль <code>{evidence.profile_id}</code>, ревизия допуска: {evidence.profile_revision}. Вызов <code>{evidence.invocation_id}</code>. Входной ID <code>{evidence.input_id}</code>. Предобработка: {evidence.preprocessing_revision ? <code>{evidence.preprocessing_revision}</code> : 'не указана'}. Артефакт <code>{evidence.artifact_id}</code>, SHA-256 <code>{evidence.sha256}</code>.</p>{nativeError?.id === evidence.artifact_id ? <p className="error">{nativeError.code === 'integrity' ? 'Целостность артефакта не подтверждена' : 'Не удалось открыть технические данные'} <button type="button" className="secondary" onClick={() => { setNativeResult(null); setNativeError(null); retryNative(value => value + 1) }}>Повторить</button></p> : nativeResult?.id === evidence.artifact_id ? <pre>{nativeResult.text}</pre> : <p>Загружаем технические данные…</p>}</details>}
  </dialog>
}

function ObservationResult({ run, runId }: { run: RunSnapshot; runId: string }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const projection = run.result_projection
  const inputs = run.inputs ?? []
  const complete = run.state === 'succeeded' && !!projection?.outcome
  const observations = complete ? projection.frames ?? [] : run.observations ?? []
  const frames = makeResultFrames(observations, inputs, complete ? projection.series?.usable_input_ids : undefined, complete)
  const outcome = complete ? projection.outcome : null
  if (!complete && !observations.length) return null
  const series = projection?.series
  const projectionContext = projection?.context
  const ruleRun = complete && outcome !== 'observations_only'
  const showSeries = complete && (ruleRun || frames.length > 1)
  return <>
    <button type="button" className="secondary" onClick={() => heading.current?.focus()}>{complete ? 'Перейти к результату' : 'Перейти к частичным наблюдениям'}</button>
    <section className="panel result" aria-labelledby="result-heading">
      <h2 ref={heading} tabIndex={-1} id="result-heading">{complete ? OUTCOME_LABELS[outcome ?? ''] ?? 'Результат анализа' : 'Частичные наблюдения — анализ не завершён'}</h2>
      <section className="observation-rows" aria-labelledby="observations-heading">
        <h3 id="observations-heading">Наблюдения по кадрам</h3>
        {observations.length ? observations.map((item, index) => {
          const input = inputs.find(value => value.input_id === item.input_id)
          const ordinal = complete ? item.ordinal : input?.ordinal ?? item.ordinal
          return <article className="observation-row" key={`${item.input_id}-${item.class_name}-${index}`}>
            <h4>Кадр {ordinal + 1}</h4>
            <p><strong>{`${CLASS_LABELS[item.class_name] ?? item.class_name}: ${OBSERVATION_STATES[item.state] ?? item.state}`}</strong>{item.reason ? ` — ${OBSERVATION_REASONS[item.reason] ?? item.reason}` : ''}</p>
            <p>Входной ID: <code>{item.input_id}</code></p>
          </article>
        }) : <p>{complete ? 'Данные наблюдений в проекции недоступны.' : 'Частичные наблюдения недоступны.'}</p>}
      </section>
      {!showSeries && <p>Период наблюдения: {projectionContext?.period ?? run.context?.period ?? 'не указан'}.</p>}
      {showSeries && <section className="series-evidence" aria-labelledby="series-heading">
        <h3 id="series-heading">Данные серии</h3>
        <p>Период наблюдения: {projectionContext?.period ?? run.context?.period ?? 'не указан'}.</p>
        {series ? <>
          <p>Пригодных кадров: {series.usable_count}. Входные ID: {series.usable_input_ids.length ? series.usable_input_ids.join(', ') : 'нет'}.</p>
          <p>Заявленная зона наблюдения: {series.declared_observation_area ?? 'не указана'} (со слов пользователя; по изображениям не подтверждена).</p>
          <p>Порядок: {series.input_order.map(inputId => { const frame = frames.find(item => item.input_id === inputId); return frame ? `Кадр ${frame.ordinal + 1} (${inputId})` : inputId }).join(' → ') || 'не указан'}.</p>
          {observations.some(item => item.class_name === 'excavator') && <p>Кадры с экскаватором: {series.excavator_supporting_input_ids.length ? series.excavator_supporting_input_ids.join(', ') : 'нет подтверждённых'}.</p>}
          {series.dump_truck_persistence_text && <p>{series.dump_truck_persistence_text} Подтверждающие входные ID: {series.dump_truck_persistence_input_ids.join(', ')}.</p>}
        </> : <p>Сводные данные серии недоступны для этого анализа.</p>}
      </section>}
      <section className="source-thumbnails" aria-labelledby="source-heading">
        <h3 id="source-heading">Исходные кадры</h3>
        {frames.length ? frames.map((frame, index) => <article className="source-thumbnail" key={frame.input_id}>
          <h4>Кадр {frame.ordinal + 1}</h4>
          <p>Пригодность: {frame.usable === null ? 'не указана' : frame.usable ? 'пригоден' : 'не пригоден'}.</p>
          <p>Входной ID: <code>{frame.input_id}</code></p>
          <p>Исходный артефакт ID: <code>{frame.artifact_id ?? 'не указан'}</code></p>
          <p>SHA-256: <code>{frame.sha256 ?? 'не указан'}</code></p>
          <SourceImage runId={runId} artifactId={frame.artifact_id} label={`Кадр ${frame.ordinal + 1}`} description={frameDescription(frame.observations)} />
          <button type="button" className="secondary" onClick={event => { opener.current = event.currentTarget; setSelected(index) }}>Открыть кадр {frame.ordinal + 1}</button>
        </article>) : <p>{complete ? 'Исходные кадры в проекции недоступны.' : 'Исходные кадры недоступны.'}</p>}
      </section>
      <section className="rule-provenance" aria-labelledby="rule-provenance-heading">
        <h3 id="rule-provenance-heading">Правило и его источник</h3>
        {ruleRun ? <>
          {projection?.rule ? <>
            <p>Правило: {projection.rule.name || 'не указано'}, ревизия {projection.rule.revision || 'не указана'}.</p>
            <p>Источник правила: {projection.rule.provenance || 'не указан'}.</p>
            <p>Ожидание: {projection.rule.expectation || 'не указано'}.</p>
          </> : <p>Данные о правиле в проекции недоступны.</p>}
          <p>{projection?.reason ? `Результат правила: ${projection.reason}` : 'Результат правила в проекции недоступен.'}</p>
          {outcome === 'no_check' && <p>Подтверждающие входные ID: {projection?.supporting_input_ids?.join(', ') || 'не указаны'}.</p>}
        </> : complete ? <p>Правило этапа не проверялось.</p> : <p>Статус правила недоступен: анализ не завершён.</p>}
      </section>
      {ruleRun && <section className="uncertainty" aria-labelledby="uncertainty-heading">
        <h3 id="uncertainty-heading">Неопределённость</h3>
        <p>{projection?.uncertainty || 'Неопределённость не указана в проекции.'}</p>
      </section>}
      {ruleRun && outcome === 'check_requested' && <section className="check-request" aria-labelledby="check-request-heading">
        <h3 id="check-request-heading">Проверка человеком</h3>
        <p>Основание: {projection?.reason || 'не указано'}.</p>
        <p>Подтверждающие входные ID: {projection?.supporting_input_ids?.join(', ') || 'не указаны'}.</p>
        <p>Период: {projectionContext?.period ?? run.context?.period ?? 'не указан'}. Заявленная зона: {series?.declared_observation_area ?? projectionContext?.observation_area ?? run.context?.observation_area ?? 'не указана'} (со слов пользователя).</p>
        <p>Рекомендуемая проверка человеком: {projection?.recommendation || 'не указана'}.</p>
        <p>Это рекомендация для проверки, а не подтверждение нарушения.</p>
      </section>}
    </section>
    {selected !== null && <EvidenceViewer runId={runId} frames={frames} native={run.native_evidence_by_frame ?? []} profile={run.profile_snapshot}
      context={projectionContext ?? run.context} selected={selected} onSelect={setSelected}
      onClose={() => { setSelected(null); opener.current?.focus() }} />}
  </>
}

const STAGE_LABELS: Record<string, string> = {
  input_registration: 'Регистрация входных данных', frame_usability: 'Проверка пригодности кадров',
  equipment_observation: 'Распознавание техники', series_aggregation: 'Объединение наблюдений серии',
  rule_evaluation: 'Проверка правила', result_projection: 'Формирование результата',
}
const STAGE_STATES: Record<string, string> = {
  pending: 'Ожидает', running: 'Выполняется', succeeded: 'Завершено', failed: 'Ошибка выполнения', skipped: 'Пропущено',
}
const STAGE_REASONS: Record<string, string> = {
  dependency_failed: 'Предыдущий этап завершился ошибкой.', not_applicable: 'Не требуется для этого анализа.',
  no_assessable_frame_or_supported_class: 'Нет пригодного кадра или поддерживаемого класса техники.',
  profile_unauthorized: 'Профиль анализа больше не разрешён.', executor_interrupted: 'Выполнение анализа прервалось.',
  observer_timeout: 'Время распознавания истекло.', observer_execution_failed: 'Не удалось выполнить распознавание.',
  artifact_integrity_failed: 'Не удалось подтвердить целостность данных.',
  observer_identity_or_device_invalid: 'Профиль распознавания не прошёл проверку.',
  observation_normalization_failed: 'Не удалось обработать наблюдение.',
  artifact_publication_failed: 'Не удалось сохранить данные анализа.',
  ordinary_completion_rejected: 'Не удалось завершить этап анализа.',
  ordinary_reservation_rejected: 'Не удалось начать распознавание.',
  ordinary_lease_rejected: 'Выполнение анализа прервалось.',
}
const RUN_STATES: Record<string, string> = {
  queued: 'В очереди', running: 'Выполняется', succeeded: 'Завершён', failed: 'Ошибка выполнения',
}
const RUN_HEADINGS: Record<string, string> = {
  queued: 'Анализ поставлен в очередь', running: 'Анализ выполняется',
  succeeded: 'Анализ завершён', failed: 'Анализ завершился ошибкой',
}

const MAX_BYTES = 16_000_000
const MAX_PIXELS = 40_000_000
const MAX_FRAMES = 8
const PENDING_STORAGE = 'observation-pending'
const PENDING_POINTER = 'observation-pending-id'

function pendingDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('observation-recovery', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('requests')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function storePending(request: Pending): Promise<void> {
  try {
    sessionStorage.setItem(PENDING_STORAGE, JSON.stringify(request))
    return
  } catch {
    const db = await pendingDatabase()
    try {
      await new Promise<void>((resolve, reject) => {
        const transaction = db.transaction('requests', 'readwrite')
        transaction.objectStore('requests').put(request, request.key)
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => reject(transaction.error)
      })
      sessionStorage.setItem(PENDING_POINTER, request.key)
    } finally { db.close() }
  }
}

async function recoverPending(): Promise<Pending | null> {
  const saved = sessionStorage.getItem(PENDING_STORAGE)
  if (saved) { try { return JSON.parse(saved) as Pending } catch { sessionStorage.removeItem(PENDING_STORAGE) } }
  const key = sessionStorage.getItem(PENDING_POINTER)
  if (!key) return null
  const db = await pendingDatabase()
  try {
    return await new Promise<Pending | null>((resolve, reject) => {
      const request = db.transaction('requests').objectStore('requests').get(key)
      request.onsuccess = () => resolve((request.result as Pending | undefined) ?? null)
      request.onerror = () => reject(request.error)
    })
  } finally { db.close() }
}

async function clearPending(): Promise<void> {
  const key = sessionStorage.getItem(PENDING_POINTER)
  if (key) {
    try {
      const db = await pendingDatabase()
      try {
        await new Promise<void>((resolve, reject) => {
          const transaction = db.transaction('requests', 'readwrite')
          transaction.objectStore('requests').delete(key)
          transaction.oncomplete = () => resolve()
          transaction.onerror = () => reject(transaction.error)
        })
      } finally { db.close() }
    } catch { /* The pointer is cleared below even if IndexedDB cleanup fails. */ }
  }
  sessionStorage.removeItem(PENDING_POINTER)
  sessionStorage.removeItem(PENDING_STORAGE)
}

function readFile(file: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = () => reject(reader.error)
    reader.readAsArrayBuffer(file)
  })
}

async function validateImage(file: File): Promise<string | null> {
  if ((file.type && file.type !== 'image/jpeg') || !/\.jpe?g$/i.test(file.name)) return 'Поддерживаются только файлы JPEG (.jpg, .jpeg).'
  if (!file.size || file.size > MAX_BYTES) return 'Размер одного файла не должен превышать 16 МБ.'
  try {
    const bytes = new Uint8Array(await readFile(file.slice(0, 3)))
    if (bytes[0] !== 0xff || bytes[1] !== 0xd8 || bytes[2] !== 0xff) return 'Файл не удалось прочитать как изображение.'
    const bitmap = await createImageBitmap(file)
    const pixels = bitmap.width * bitmap.height
    bitmap.close()
    if (pixels > MAX_PIXELS) return 'Изображение превышает 40 миллионов пикселей.'
  } catch {
    return 'Файл не удалось прочитать как изображение.'
  }
  return null
}

async function base64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1])
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

function localPeriod(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

function periodWithOffset(value: string): string {
  const date = new Date(value)
  const minutes = -date.getTimezoneOffset()
  const sign = minutes >= 0 ? '+' : '-'
  const hours = String(Math.floor(Math.abs(minutes) / 60)).padStart(2, '0')
  const rest = String(Math.abs(minutes) % 60).padStart(2, '0')
  return `${value}:00${sign}${hours}:${rest}`
}

function validLocalPeriod(value: string): boolean {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return false
  const actual = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  return actual === value
}

function runIdFromPath(): string | null {
  if (location.pathname === '/about') return 'about'
  if (location.pathname === '/new') return 'new'
  if (location.pathname === '/history' || location.pathname === '/analyses') return 'history'
  if (location.pathname === '/' || location.pathname === '/stages') return 'stages'
  const match = location.pathname.match(/^\/runs\/([0-9a-f-]{36})$/i)
  return match?.[1] ?? null
}

function About({ heading, returnPath, onReturn }: { heading: RefObject<HTMLHeadingElement | null>; returnPath: string; onReturn: () => void }) {
  return <section className="about" aria-labelledby="about-heading">
    <div className="page-intro"><p className="eyebrow">О проекте</p><h1 ref={heading} tabIndex={-1} id="about-heading">Контроль строительства</h1><p>Прототип команды «17 мгновений ИИ» помогает рассмотреть наблюдения по земляным работам котлована и решить, нужен ли ручной осмотр.</p></div>
    <div className="about-content">
      <section className="panel" aria-labelledby="about-method"><h2 id="about-method">Что анализируется</h2><p>Пользователь передаёт отдельное изображение или упорядоченную серию изображений одной заявленной зоны. Прототип распознаёт два класса техники: экскаватор и самосвал. Зона и период указаны пользователем; сами кадры не устанавливают границы всей площадки.</p><p>Для каждого запрошенного класса на кадре показывается одно из состояний: «обнаружен», «не обнаружен в кадре», «недостаточно данных» (кадр или работа распознавания не позволяют оценить класс) и «не анализировался» (класс не был проверен). Необнаружение в кадре не доказывает отсутствие техники на всей площадке.</p><p>В режиме «Только распознать технику» система показывает наблюдения без проверки правила этапа. В режиме «Проверить правило этапа» она сопоставляет пригодные кадры серии с сохранённой неизменяемой ревизией демонстрационного правила и политики проверки. Это правило не является нормативным требованием.</p></section>
      <section className="panel" aria-labelledby="about-outcomes"><h2 id="about-outcomes">Как читать итог</h2><p>Для проверки правила оба класса должны быть проанализированы во всех пригодных кадрах одной заявленной зоны, все наблюдения обязательных классов на переданных кадрах должны поддаваться оценке, а пригодных кадров должно быть минимум три. Если класс не анализировался или хотя бы одно наблюдение обязательного класса не удалось оценить, данных для проверки правила недостаточно.</p><p>Если экскаватор обнаружен хотя бы в одном пригодном кадре, а самосвал не обнаружен ни в одном пригодном кадре серии, итог «Рекомендована проверка человеком» (<code>check_requested</code>) рекомендует человеку проверить возможную задержку вывоза грунта. Это не доказательство нарушения.</p><p>Если в пригодной серии обнаружены и экскаватор, и самосвал, итог «Проверка не запрошена» (<code>no_check</code>) означает лишь, что по этой серии запрос проверки не сформирован. Это не подтверждает соблюдение требований на всей площадке. Если наблюдения не подтверждают работу экскаватора, данных для оценки вывоза грунта недостаточно.</p></section>
      <section className="panel" aria-labelledby="about-source"><h2 id="about-source">Источник демонстрации</h2><p>Демонстрационные серии иллюстрируют работу интерфейса. Они взяты из архива организаторов <code>artifacts/dataset/Строительная_техника.zip</code>: группы <code>organizer-archive-site-85-94</code> (файлы Строительная_техника/Screenshot_87.png, Строительная_техника/Screenshot_89.png, Строительная_техника/Screenshot_90.png) и <code>organizer-archive-site-22-26</code> (файлы Строительная_техника/Screenshot_23.png, Строительная_техника/Screenshot_25.png, Строительная_техника/Screenshot_26.png). Порядок кадров соответствует архиву; указанное в примерах время 12:00 условное, а исходная принадлежность кадров конкретной камере и площадке не подтверждена. Для демонстрации PNG-файлы преобразованы в JPEG-копии; загрузка в анализ принимает только JPEG.</p><p>С запуском сохраняются переданные изображения и контекст; полученные наблюдения показываются отдельно. Для итогов «Рекомендована проверка человеком» и «Проверка не запрошена» указываются поддерживающие их кадры, ревизия правила и политика проверки; при одном лишь распознавании или недостатке данных такие кадры не выбираются.</p></section>
      <section className="panel" aria-labelledby="about-limits"><h2 id="about-limits">Границы прототипа</h2><p>Прототип не подключается к потокам камер и не отслеживает график строительства, текущий этап автоматически, тенденции или общее состояние проекта. Результат относится только к переданным изображениям и заявленному контексту.</p></section>
      <aside className="panel about-team" aria-label="Команда проекта"><img src="/team-logo.png" alt="" onError={event => { event.currentTarget.hidden = true }} /><p>Команда: <strong>17 мгновений ИИ</strong></p></aside>
    </div><a className="about-return" href={returnPath} onClick={event => { event.preventDefault(); onReturn() }}>Вернуться назад</a>
  </section>
}

export default function App() {
  const injectedChoices = (globalThis as typeof globalThis & { __ANALYSIS_CHOICES__?: Choice[] }).__ANALYSIS_CHOICES__
  const [route, setRoute] = useState(runIdFromPath)
  const routeRef = useRef(route)
  const historyPath = useRef(location.pathname === "/analyses" ? "/analyses" : "/history")
  const [scenario, setScenario] = useState('')
  const [choices, setChoices] = useState<Choice[]>(injectedChoices ?? [])
  const [choicesLoading, setChoicesLoading] = useState(!injectedChoices)
  const [choicesAttempt, setChoicesAttempt] = useState(0)
  const [stage, setStage] = useState('excavation')
  const [intent, setIntent] = useState(injectedChoices?.find(item => item.id === 'excavation')?.rule ? 'rule_evaluation' : 'observation_only')
  const observationPreferred = useRef(false)
  const [area, setArea] = useState('')
  const [period, setPeriod] = useState(localPeriod)
  const [frames, setFrames] = useState<Frame[]>([])
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState('')
  const [selectedDemo, setSelectedDemo] = useState<DemoCase | null>(null)
  const demoGeneration = useRef(0)
  const demoLoadingRef = useRef(false)
  const framesRef = useRef<Frame[]>([])
  const validationQueue = useRef<Promise<void>>(Promise.resolve())
  const [validating, setValidating] = useState(false)
  const [removed, setRemoved] = useState<{ frame: Frame; index: number } | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [notice, setNotice] = useState('')
  const [offline, setOffline] = useState(!navigator.onLine)
  const [sending, setSending] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  const [recovering, setRecovering] = useState(true)
  const [runSnapshot, setRunSnapshot] = useState<RunSnapshot | null>(null)
  const [runAnnouncement, setRunAnnouncement] = useState('')
  const [runError, setRunError] = useState('')
  const [runChecked, setRunChecked] = useState(false)
  const [runMissing, setRunMissing] = useState(false)
  const [runReadAttempt, setRunReadAttempt] = useState(0)
  const [runReading, setRunReading] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState('')
  const [historyRuns, setHistoryRuns] = useState<HistoryRun[]>([])
  const [historyError, setHistoryError] = useState('')
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyPageLoading, setHistoryPageLoading] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [historyPage, setHistoryPage] = useState(0)
  const historyPageRef = useRef(historyPage)
  historyPageRef.current = historyPage
  const [historyNextOffset, setHistoryNextOffset] = useState<number | null>(null)
  const [historyAttempt, setHistoryAttempt] = useState(0)
  const [stageSummaries, setStageSummaries] = useState<StageSummary[] | null>(null)
  const [selectedStage, setSelectedStage] = useState('excavation')
  const [stageError, setStageError] = useState('')
  const [stageAttempt, setStageAttempt] = useState(0)
  const [stageLoading, setStageLoading] = useState(false)
  const [unsupportedStageNotice, setUnsupportedStageNotice] = useState(false)
  const announcedStages = useRef<string | null>(null)
  const summary = useRef<HTMLDivElement>(null)
  const pageHeading = useRef<HTMLHeadingElement>(null)
  const focusAfterNavigation = useRef(false)
  const cameraVideo = useRef<HTMLVideoElement>(null)
  const cameraStream = useRef<MediaStream | null>(null)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraDenied, setCameraDenied] = useState(false)
  const cameraGeneration = useRef(0)
  const mounted = useRef(true)
  const busy = useRef(false)

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine)
    const pop = () => { closeCamera(); routeRef.current = runIdFromPath(); focusAfterNavigation.current = true; setRoute(routeRef.current) }
    addEventListener('online', update)
    addEventListener('offline', update)
    addEventListener('popstate', pop)
    return () => { removeEventListener('online', update); removeEventListener('offline', update); removeEventListener('popstate', pop) }
  }, [])

  useEffect(() => {
    mounted.current = true
    void recoverPending().then(request => {
      if (mounted.current && request) {
        setPending(request)
        setErrors(current => ({ ...current, submit: 'Предыдущая отправка требует проверки. Повторите её с сохранённым ключом.' }))
      }
    }).catch(() => {
      if (mounted.current) setErrors(current => ({ ...current, submit: 'Не удалось восстановить отправку. Сохраните вкладку и повторите попытку позже.' }))
    }).finally(() => { if (mounted.current) setRecovering(false) })
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    if (route !== 'new' || injectedChoices || choices.length) return
    const controller = new AbortController()
    setChoicesLoading(true)
    void fetch('/api/analysis-choices', { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error('choices_unavailable')
      return response.json()
    }).then(data => {
      if (controller.signal.aborted || !Array.isArray(data.stages)) return
      setChoices(data.stages)
      setIntent(data.stages.find((item: Choice) => item.id === 'excavation')?.rule ? 'rule_evaluation' : 'observation_only')
    }).catch(() => {}).finally(() => { if (!controller.signal.aborted) setChoicesLoading(false) })
    return () => controller.abort()
  }, [route, choicesAttempt])

  useEffect(() => {
    closeCamera()
    setRunSnapshot(null)
    setRunAnnouncement('')
    setRunError('')
    setRunChecked(false)
    setRunMissing(false)
    setRunReading(false)
    setRetrying(false)
    setRetryError('')
    announcedStages.current = null
  }, [route])

  useEffect(() => {
    if (route === 'history') {
      setHistoryRuns([])
      setHistoryPage(0)
      setHistoryNextOffset(null)
      setHistoryLoaded(false)
      setHistoryError('')
    }
  }, [route])

  useEffect(() => {
    if (!route || route === 'about' || route === 'history' || route === 'new' || route === 'stages') return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    let timeout: ReturnType<typeof setTimeout>
    let controller: AbortController | null = null
    async function read() {
      controller = new AbortController()
      setRunReading(true)
      try {
        const response = await Promise.race([
          fetch(`/api/runs/${route}`, { signal: controller.signal }),
          new Promise<Response>((_, reject) => { timeout = setTimeout(() => { controller?.abort(); reject(new Error('timeout')) }, 10000) }),
        ])
        if (!active) return
        if (response.status === 404) {
          if (announcedStages.current === null) setRunMissing(true)
          else setRunError('Не удалось получить актуальный статус. Повторите проверку.')
          setRunChecked(true)
          return
        }
        if (!response.ok) throw new Error()
        const data = await response.json() as RunSnapshot
        if (!active) return
        setRunSnapshot(data)
        setRunError('')
        setRunChecked(true)
        const states = data.stages.map(stage => `${stage.name}:${stage.state}`).join('|')
        if (announcedStages.current !== null && announcedStages.current !== states) {
          const previous = announcedStages.current.split('|')
          const changed = data.stages.filter((stage, index) => previous[index] !== `${stage.name}:${stage.state}`)
          setRunAnnouncement(changed.map(stage => `${STAGE_LABELS[stage.name] ?? 'Этап анализа'}: ${STAGE_STATES[stage.state] ?? 'Состояние доступно на сервере'}.`).join(' '))
        } else setRunAnnouncement('')
        announcedStages.current = states
        if (data.state === 'queued' || data.state === 'running') timer = setTimeout(read, 3000)
      } catch {
        if (active) { setRunError('Связь потеряна. Анализ может продолжаться на сервере.'); setRunChecked(true) }
      } finally {
        clearTimeout(timeout)
        if (active) setRunReading(false)
      }
    }
    void read()
    return () => { active = false; controller?.abort(); clearTimeout(timer); clearTimeout(timeout) }
  }, [route, runReadAttempt])

  useEffect(() => {
    if (route !== 'history') return
    let active = true
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout>
    let refresh: ReturnType<typeof setTimeout>
    setHistoryLoading(true)
    void Promise.race([
      fetch('/api/runs', { signal: controller.signal }),
      new Promise<Response>((_, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error('timeout')) }, 10000) }),
    ]).then(async response => {
      if (!response.ok) throw new Error('history_unavailable')
      const data = await response.json() as { runs: HistoryRun[]; next_offset?: number | null }
      if (!active) return
      setHistoryRuns(current => historyAttempt && current.length
        ? [...current.map(old => data.runs.find(run => (run.id ?? run.run_id) === (old.id ?? old.run_id)) ?? old),
          ...data.runs.filter(run => !current.some(old => (old.id ?? old.run_id) === (run.id ?? run.run_id)))]
        : data.runs)
      if (historyPageRef.current === 0) setHistoryNextOffset(data.next_offset ?? null)
      setHistoryLoaded(true)
      setHistoryError('')
    }).catch(() => { if (active) setHistoryError('Не удалось загрузить историю анализов.')
    }).finally(() => { clearTimeout(timeout); if (active) {
      setHistoryLoading(false)
      refresh = setTimeout(() => setHistoryAttempt(value => value + 1), 3000)
    } })
    return () => { active = false; controller.abort(); clearTimeout(timeout); clearTimeout(refresh) }
  }, [route, historyAttempt])

  useEffect(() => {
    if (route !== 'history' || historyPage === 0) return
    let active = true
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout>
    setHistoryPageLoading(true)
    void Promise.race([
      fetch(`/api/runs?offset=${historyPage}`, { signal: controller.signal }),
      new Promise<Response>((_, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error('timeout')) }, 10000) }),
    ]).then(async response => {
      if (!response.ok) throw new Error('history_unavailable')
      const data = await response.json() as { runs: HistoryRun[]; next_offset?: number | null }
      if (!active) return
      setHistoryRuns(current => [...current, ...data.runs.filter(run => !current.some(item => (item.id ?? item.run_id) === (run.id ?? run.run_id)))])
      setHistoryNextOffset(data.next_offset ?? null)
      setHistoryError('')
    }).catch(() => { if (active) setHistoryError('Не удалось загрузить историю анализов.')
    }).finally(() => { clearTimeout(timeout); if (active) setHistoryPageLoading(false) })
    return () => { active = false; controller.abort(); clearTimeout(timeout) }
  }, [route, historyPage])

  useEffect(() => {
    if (route !== 'stages') return
    let active = true
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout>
    let refresh: ReturnType<typeof setTimeout>
    setStageLoading(true)
    void Promise.race([
      (async () => { const response = await fetch('/api/stages/summary', { signal: controller.signal });
        if (!response.ok) throw new Error(); return response.json() as Promise<{ stages: StageSummary[] }> })(),
      new Promise<{ stages: StageSummary[] }>((_, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error('timeout')) }, 10000) }),
    ]).then(data => {
      if (!Array.isArray(data.stages)) throw new Error()
      if (active) { setStageSummaries(data.stages); setStageError('') }
    }).catch(() => { if (active) setStageError(stageSummaries
      ? 'Не удалось обновить этапы. Показаны последние доступные данные.'
      : 'Не удалось загрузить этапы.')
    }).finally(() => { clearTimeout(timeout); if (active) { setStageLoading(false); refresh = setTimeout(() => setStageAttempt(value => value + 1), 30000) } })
    return () => { active = false; controller.abort(); clearTimeout(timeout); clearTimeout(refresh) }
  }, [route, stageAttempt])

  async function retryRun() {
    if (!route || route === 'about' || route === 'history' || route === 'new' || route === 'stages' || retrying) return
    const sourceRoute = route
    setRetrying(true)
    setRetryError('')
    try {
      const response = await fetch(`/api/runs/${route}/retry`, { method: 'POST' })
      const data = await response.json() as { run_id?: string; code?: string }
      if (routeRef.current !== sourceRoute || !mounted.current) return
      if (!response.ok || !data.run_id) {
        setRetryError(data.code === 'retry_source_unavailable' ? 'Исходные данные повреждены или недоступны. Повторить анализ нельзя.' :
          data.code === 'profile_unauthorized' || data.code === 'profile_runtime_mismatch' ? 'Текущий профиль наблюдателя недоступен для повтора.' :
          data.code === 'retry_ineligible' ? 'Этот анализ нельзя повторить.' : 'Не удалось создать повторный анализ. Попробуйте позже.')
        return
      }
      navigate(`/runs/${data.run_id}`)
    } catch {
      if (routeRef.current === sourceRoute && mounted.current)
        setRetryError('Связь потеряна. Проверьте историю перед повторной попыткой.')
    } finally { if (routeRef.current === sourceRoute && mounted.current) setRetrying(false) }
  }

  useEffect(() => {
    if (focusAfterNavigation.current) {
      pageHeading.current?.focus()
      focusAfterNavigation.current = false
    }
    document.title = route === 'about' ? 'О проекте — Контроль строительства' : route === 'history' ? 'История анализов — Контроль строительства' : route === 'stages' ? 'Этапы — Контроль строительства' : route === 'new' ? 'Новый анализ — Контроль строительства' : route ? 'Анализ — Контроль строительства' : 'Страница не найдена — Контроль строительства'
  }, [route])

  useEffect(() => () => { cameraGeneration.current++; cameraStream.current?.getTracks().forEach(track => track.stop()) }, [])

  useEffect(() => {
    if (cameraOpen && cameraVideo.current) cameraVideo.current.srcObject = cameraStream.current
  }, [cameraOpen])

  function navigate(path: string) {
    if (path === "/analyses" || path === "/history") historyPath.current = path
    closeCamera()
    history.pushState(path === '/about' ? { aboutFromApp: true, returnPath: location.pathname } : {}, '', path)
    routeRef.current = runIdFromPath()
    focusAfterNavigation.current = true
    setRoute(routeRef.current)
    setRunError('')
  }

  function returnFromAbout() {
    if (history.state?.aboutFromApp) { history.back(); return }
    history.replaceState({}, '', '/')
    routeRef.current = runIdFromPath()
    focusAfterNavigation.current = true
    setRoute(routeRef.current)
  }

  function newAnalysis() { setUnsupportedStageNotice(route === 'stages' && selectedStage !== 'excavation'); if (selectedStage !== 'excavation') { setStage('excavation'); setIntent(choices.find(item => item.id === 'excavation')?.rule && !observationPreferred.current ? 'rule_evaluation' : 'observation_only') }; navigate('/new') }

  function updateFrames(next: Frame[]) {
    framesRef.current = next
    setFrames(next)
    setSelectedDemo(null)
  }

  async function loadDemo(caseId: string) {
    const selected = demoCases.cases.find(item => item.id === caseId)
    if (!selected || pending || sending || recovering || busy.current || demoLoadingRef.current) return
    const rule = choices.find(item => item.id === selected.stage)?.rule
    if (!rule || rule.revision !== selected.ruleRevision) {
      setDemoError('Демонстрационный пример недоступен: текущая ревизия правила изменилась или правило не загружено.')
      return
    }
    const generation = ++demoGeneration.current
    demoLoadingRef.current = true
    setDemoLoading(true)
    setDemoError('')
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout> | undefined
    try {
      await validationQueue.current
      const loaded = await Promise.race([Promise.all(selected.frames.map(async frame => {
        const response = await fetch(frame.path, { signal: controller.signal })
        if (!response.ok) throw new Error('asset_unavailable')
        const file = new File([await response.blob()], frame.path.split('/').pop()!, { type: 'image/jpeg' })
        if (await validateImage(file)) throw new Error('asset_invalid')
        const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await readFile(file))))
          .map(byte => byte.toString(16).padStart(2, '0')).join('')
        if (hash !== frame.sha256) throw new Error('asset_integrity')
        return { id: crypto.randomUUID(), file }
      })), new Promise<never>((_, reject) => {
        timeout = setTimeout(() => { controller.abort(); reject(new Error('demo_timeout')) }, 10000)
      })])
      if (!mounted.current || routeRef.current !== "new" || generation !== demoGeneration.current || busy.current) return
      closeCamera()
      updateFrames(loaded)
      setStage(selected.stage)
      setIntent(selected.intent)
      observationPreferred.current = false
      setScenario(selected.scenario)
      setArea(selected.observationArea)
      setPeriod(selected.period)
      setSelectedDemo(selected)
      setRemoved(null)
      setErrors({})
      setNotice(`Загружен демонстрационный пример: ${selected.label}. Три кадра можно изменить перед отправкой.`)
    } catch {
      if (mounted.current && generation === demoGeneration.current) setDemoError('Не удалось загрузить и проверить все кадры примера. Текущая форма сохранена; повторите выбор.')
    } finally {
      controller.abort()
      clearTimeout(timeout)
      if (generation === demoGeneration.current) {
        demoLoadingRef.current = false
        if (mounted.current) setDemoLoading(false)
      }
    }
  }

  async function addFiles(files: FileList | File[]) {
    if (pending || sending || busy.current || demoLoadingRef.current) return
    const batch = Array.from(files)
    setValidating(true)
    const task = validationQueue.current.then(async () => {
      const next = [...framesRef.current]
      const originalCount = next.length
      const rejected: string[] = []
      for (const file of batch) {
        if (next.length >= MAX_FRAMES) { rejected.push('Можно добавить не более 8 кадров.'); break }
        const error = await validateImage(file)
        if (error) rejected.push(`${file.name}: ${error}`)
        else next.push({ id: crypto.randomUUID(), file })
      }
      if (!mounted.current || routeRef.current !== 'new') return
      updateFrames(next)
      if (next.length !== originalCount) setNotice(`Добавлено кадров: ${next.length - originalCount}. Всего ${next.length}.`)
      setErrors(current => ({ ...current, images: rejected.join(' ') || undefined }))
    }).catch(() => { setErrors(current => ({ ...current, images: 'Не удалось проверить выбранные изображения. Повторите выбор файлов.' })) })
    validationQueue.current = task
    await task
    if (validationQueue.current === task) setValidating(false)
  }

  async function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files ? Array.from(event.target.files) : []
    event.target.value = ''
    await addFiles(files)
  }

  function move(index: number, delta: number) {
    const target = index + delta
    const next = [...frames]
    ;[next[index], next[target]] = [next[target], next[index]]
    updateFrames(next)
    setNotice(`${next[target].file.name}: кадр ${target + 1} из ${next.length}.`)
  }

  function remove(index: number) {
    const frame = frames[index]
    updateFrames(frames.filter(item => item.id !== frame.id))
    setRemoved({ frame, index })
    setNotice(`${frame.file.name} удалён. Можно вернуть.`)
  }

  function restore() {
    if (!removed || frames.length >= MAX_FRAMES) return
    const next = [...frames]
    const index = Math.min(removed.index, next.length)
    next.splice(index, 0, removed.frame)
    updateFrames(next)
    setNotice(`${removed.frame.file.name}: кадр ${index + 1} из ${next.length}.`)
    setRemoved(null)
  }

  async function openCamera() {
    if (demoLoadingRef.current) return
    if (!navigator.mediaDevices?.getUserMedia) {
      setErrors(current => ({ ...current, images: 'Камера недоступна. Выберите изображения из файлов.' }))
      return
    }
    const generation = ++cameraGeneration.current
    const presetGeneration = demoGeneration.current
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      if (!mounted.current || generation !== cameraGeneration.current || (routeRef.current !== 'new' || presetGeneration !== demoGeneration.current || demoLoadingRef.current)) {
        stream.getTracks().forEach(track => track.stop())
        return
      }
      cameraStream.current = stream
      setCameraOpen(true)
    } catch (error) {
      if (!mounted.current || generation !== cameraGeneration.current) return
      const denied = error instanceof DOMException && (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError')
      if (denied) setCameraDenied(true)
      setErrors(current => ({ ...current, images: denied
        ? 'Доступ к камере не предоставлен. Выберите изображения из файлов.'
        : 'Не удалось открыть камеру. Повторите попытку или выберите изображения из файлов.' }))
    }
  }

  function closeCamera() {
    cameraGeneration.current++
    cameraStream.current?.getTracks().forEach(track => track.stop())
    cameraStream.current = null
    setCameraOpen(false)
  }

  function capture() {
    const video = cameraVideo.current
    if (!video?.videoWidth || !video.videoHeight) {
      setErrors(current => ({ ...current, images: 'Камера ещё не готова. Подождите и повторите снимок.' }))
      return
    }
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) { setErrors(current => ({ ...current, images: 'Не удалось получить снимок. Повторите попытку.' })); return }
    context.drawImage(video, 0, 0)
    const generation = cameraGeneration.current
    const presetGeneration = demoGeneration.current
    canvas.toBlob(blob => {
      if (!mounted.current || generation !== cameraGeneration.current || (routeRef.current !== 'new' || presetGeneration !== demoGeneration.current || demoLoadingRef.current)) return
      if (!blob) { setErrors(current => ({ ...current, images: 'Не удалось получить снимок. Повторите попытку.' })); return }
      void addFiles([new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' })])
      closeCamera()
    }, 'image/jpeg', 0.9)
  }

  function validateForm(): Errors {
    const next: Errors = {}
    if (!scenario.trim() || scenario.trim().length > 256) next.scenario = 'Укажите сценарий длиной до 256 символов.'
    if (!area.trim() || area.trim().length > 256) next.observation_area = 'Укажите зону наблюдения длиной до 256 символов.'
    if (!period || !validLocalPeriod(period)) next.period = 'Укажите существующие местные дату и время наблюдения.'
    if (!framesRef.current.length) next.images = 'Добавьте хотя бы один кадр JPEG.'
    return next
  }

  async function send(request: Pending) {
    if (busy.current || offline) return
    busy.current = true
    setSending(true)
    setErrors(current => ({ ...current, submit: undefined }))
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout> | undefined
    try {
      const { response, data } = await Promise.race([
        (async () => {
          const response = await fetch(request.endpoint.replace(/^\/runs\//, '/api/runs/'), {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': request.key }, body: request.body,
            signal: controller.signal,
          })
          if (response.status >= 400 && response.status < 500) {
            let code = ''
            try { code = String((await response.json()).code ?? '') } catch { /* Preserve the definitive HTTP status. */ }
            return { response, data: { code } }
          }
          return { response, data: await response.json() }
        })(),
        new Promise<never>((_, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error('timeout')) }, 10000) }),
      ])
      clearTimeout(timeout)
      if (response.status >= 400 && response.status < 500) {
        await clearPending()
        setPending(null)
        setErrors(current => ({ ...current, submit: data.code === 'idempotency_key_conflict'
          ? 'Ключ отправки уже связан с другим запросом. Проверьте данные и начните новую отправку.'
          : 'Сервер отклонил запрос. Проверьте контекст и файлы, затем повторите.' }))
        queueMicrotask(() => summary.current?.focus())
        return
      }
      if (response.status === 202 && typeof data.run_id === 'string' && /^[0-9a-f-]{36}$/i.test(data.run_id)) {
        await clearPending()
        setPending(null)
        navigate(`/runs/${data.run_id}`)
      } else if (response.status === 503 && (data?.code === 'submission_publication_failed' || data?.code === 'submission_interrupted')) {
        await clearPending()
        setPending(null)
        setErrors(current => ({ ...current, submit: 'Отправка завершилась ошибкой. Проверьте данные и явно запустите новый анализ: будет создан новый ключ отправки.' }))
        queueMicrotask(() => summary.current?.focus())
      } else {
        setErrors(current => ({ ...current, submit: 'Результат отправки пока неизвестен. Повторите запрос с тем же ключом; изображения и контекст сохранены.' }))
        queueMicrotask(() => summary.current?.focus())
      }
    } catch {
      setErrors(current => ({ ...current, submit: 'Ответ сервера не получен. Повторите отправку: исходный запрос и ключ сохранены.' }))
      queueMicrotask(() => summary.current?.focus())
    } finally {
      clearTimeout(timeout)
      busy.current = false
      setSending(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy.current || offline || recovering || demoLoading) return
    if (pending) { await send(pending); return }
    busy.current = true
    await validationQueue.current
    const next = validateForm()
    setErrors(next)
    if (Object.keys(next).length) { busy.current = false; queueMicrotask(() => summary.current?.focus()); return }
    setSending(true)
    try {
      const images: string[] = []
      for (const frame of framesRef.current) images.push(await base64(frame.file))
      const body = JSON.stringify({
        intent, stage, stage_id: stage, scenario: scenario.trim(), observation_area: area.trim(),
        period: periodWithOffset(period), requested_classes: ['excavator', 'dump_truck'],
        ...(images.length === 1 ? { image_base64: images[0] } : { images_base64: images }),
      })
      const request = { endpoint: images.length === 1 ? '/api/runs/single-image' : '/api/runs/series', body, key: crypto.randomUUID() }
      await storePending(request)
      setPending(request)
      busy.current = false
      await send(request)
    } catch {
      setErrors(current => ({ ...current, submit: 'Не удалось безопасно подготовить или сохранить запрос. Форма сохранена; повторите попытку.' }))
      queueMicrotask(() => summary.current?.focus())
    } finally {
      busy.current = false
      setSending(false)
    }
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main">К основному содержимому</a>
    <header className="topbar"><div className="topbar-inner"><div className="brand"><a href="/" onClick={event => { event.preventDefault(); navigate('/') }}>Контроль строительства</a><a className="team-link" href="/about" onClick={event => { event.preventDefault(); navigate('/about') }}>17 мгновений ИИ</a></div><nav aria-label="Основная навигация"><a href="/" aria-current={route === 'stages' ? 'page' : undefined} onClick={event => { event.preventDefault(); navigate('/') }}>Этапы</a><a href={historyPath.current} aria-current={route === 'history' ? 'page' : undefined} onClick={event => { event.preventDefault(); navigate(historyPath.current) }}>Анализы</a></nav><nav className="secondary-nav" aria-label="Дополнительная навигация"><a href="/about" aria-current={route === 'about' ? 'page' : undefined} onClick={event => { event.preventDefault(); navigate('/about') }}>О проекте</a></nav><a className="primary new-analysis-link" href="/new" aria-current={route === 'new' ? 'page' : undefined} onClick={event => { event.preventDefault(); newAnalysis() }}>Новый анализ</a></div></header>
    <main id="main" className="page">
      {route === 'stages' ? <section aria-labelledby="stages-heading"><div className="page-intro"><p className="eyebrow">Обзор этапов</p><h1 ref={pageHeading} tabIndex={-1} id="stages-heading">Этапы строительства</h1><p>Здесь показаны результаты завершённых анализов, привязанных к этапу. График и состояние проекта не оцениваются.</p></div>{stageError && <div className="error" role="alert"><p>{stageError}</p><button type="button" className="secondary" onClick={() => setStageAttempt(value => value + 1)}>Повторить загрузку</button></div>}<div className="stages-layout"><section className="panel" aria-labelledby="stage-map-heading" aria-busy={stageLoading}><h2 id="stage-map-heading">Карта этапов</h2>{stageLoading && !stageSummaries && <p role="status">Загружаем этапы…</p>}<div className="stage-tiles">{stageSummaries?.map(stage => <button key={stage.stage_id} className="stage-tile" type="button" aria-pressed={selectedStage === stage.stage_id} aria-controls="stage-inspector" onClick={() => setSelectedStage(stage.stage_id)}><strong>{stage.name}</strong><span>{stage.supported ? stage.latest_result ? OUTCOME_LABELS[stage.latest_result.projection.outcome] ?? 'Результат доступен' : 'Анализов нет' : 'Не настроено в прототипе'}</span>{stage.latest_lifecycle && <small>{stage.latest_result ? 'Более новый запуск' : 'Последняя попытка'}: {RUN_STATES[stage.latest_lifecycle.state] ?? 'Состояние неизвестно'}</small>}</button>)}</div><p className="hint">В прототипе настроен анализ земляных работ котлована. Другие этапы показаны для навигации.</p><button type="button" className="secondary" disabled={stageLoading} onClick={() => setStageAttempt(value => value + 1)}>{stageLoading ? 'Обновляем…' : 'Обновить этапы'}</button></section><section className="panel stage-inspector" id="stage-inspector" aria-labelledby="inspector-heading">{(() => { const stage = stageSummaries?.find(item => item.stage_id === selectedStage); if (!stage) return <p>Выберите этап.</p>; return <><p className="eyebrow">Выбранный этап</p><h2 id="inspector-heading">{stage.name}</h2><p className="stage-outcome">{stage.supported ? stage.latest_result ? OUTCOME_LABELS[stage.latest_result.projection.outcome] ?? 'Результат доступен' : 'Анализов нет' : 'Не настроено в прототипе'}</p>{stage.supported ? <>{stage.latest_result ? <p>Результат последнего завершённого анализа с сохранёнными доказательствами. {stage.latest_result.created_at && <>Время запуска: <time dateTime={stage.latest_result.created_at}>{stage.latest_result.created_at}</time>. </>}<a href={`/runs/${stage.latest_result.run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${stage.latest_result!.run_id}`) }}>Открыть доказательства</a></p> : <p>Для этого этапа ещё нет завершённого анализа с результатом.</p>}{stage.latest_lifecycle && <p className="attention">{stage.latest_result ? 'Более новый запуск' : 'Последняя попытка'}: {RUN_STATES[stage.latest_lifecycle.state] ?? 'Состояние неизвестно'}. {stage.latest_lifecycle.created_at && <>Время запуска: <time dateTime={stage.latest_lifecycle.created_at}>{stage.latest_lifecycle.created_at}</time>. </>}<a href={`/runs/${stage.latest_lifecycle.run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${stage.latest_lifecycle!.run_id}`) }}>Открыть запуск</a>. {stage.latest_result && 'Он не заменяет завершённый результат.'}</p>}</> : <p>Для этого этапа правило не настроено в прототипе. Анализ доступен для этапа «Земляные работы котлована».</p>}</> })()}</section></div></section> : route === 'history' ? <section className="history" aria-labelledby="history-heading" aria-busy={historyLoading || historyPageLoading}>
        <div className="page-intro"><p className="eyebrow">История</p><h1 ref={pageHeading} tabIndex={-1} id="history-heading">История анализов</h1><p>Сохранённые анализы и их исходные данные.</p></div>
        {historyError && <div className="panel attention" role="alert">{historyError} <button type="button" className="secondary" onClick={() => setHistoryAttempt(value => value + 1)}>Повторить загрузку</button></div>}
        {historyLoading && !historyLoaded && <p role="status">Загружаем историю…</p>}
        {historyLoaded && !historyRuns.length && !historyError && <div className="panel"><p>Анализов пока нет.</p><a href="/new" onClick={event => { event.preventDefault(); navigate('/new') }}>Новый анализ</a></div>}
        {historyRuns.length > 0 && <ol className="history-list">{historyRuns.map(run => {
          const id = run.id ?? run.run_id
          const predecessor = run.retry_predecessor_id ?? run.retry_of_run_id
          const successor = run.retry_successor_id ?? run.successor_run_id
          return <li className="panel history-row" key={id}>
            <a className="history-link" href={`/runs/${id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${id}`) }}>Анализ {id}</a>
            <dl><div><dt>Создан</dt><dd>{run.created_at ? <time dateTime={run.created_at}>{new Date(run.created_at).toLocaleString('ru-RU')}</time> : 'Время создания неизвестно'}</dd></div>
              <div><dt>Этап</dt><dd>{run.stage === 'excavation' ? 'Земляные работы' : run.stage ? 'Другой этап' : 'Не указан'}</dd></div>
              <div><dt>Цель</dt><dd>{run.intent === 'rule_evaluation' ? 'Проверить правило этапа' : 'Только распознать технику'}</dd></div>
              <div><dt>Состояние</dt><dd>{RUN_STATES[run.state] ?? 'Состояние доступно на сервере'}</dd></div>
              {run.outcome && run.state === 'succeeded' && <div><dt>Итог</dt><dd>{OUTCOME_LABELS[run.outcome] ?? 'Результат анализа'}</dd></div>}</dl>
            {predecessor && <p>Предыдущий анализ: <a href={`/runs/${predecessor}`} onClick={event => { event.preventDefault(); navigate(`/runs/${predecessor}`) }}>{predecessor}</a></p>}
            {successor && <p>Следующий анализ: <a href={`/runs/${successor}`} onClick={event => { event.preventDefault(); navigate(`/runs/${successor}`) }}>{successor}</a></p>}
          </li>
        })}</ol>}
        {historyNextOffset !== null && !historyError && <button type="button" className="secondary" disabled={historyPageLoading} onClick={() => setHistoryPage(historyNextOffset)}>{historyPageLoading ? 'Загружаем…' : 'Показать ещё'}</button>}
      </section> : route === 'about' ? <About heading={pageHeading} returnPath={history.state?.aboutFromApp ? history.state.returnPath : '/'} onReturn={returnFromAbout} /> : route === null ? <section className="panel" aria-labelledby="not-found-heading"><h1 ref={pageHeading} tabIndex={-1} id="not-found-heading">Страница не найдена</h1><p>Проверьте адрес или откройте обзор этапов.</p></section> : route !== 'new' ? <section className="run-workspace" aria-labelledby="run-heading" aria-busy={runReading}><div className="panel run-header"><p className="eyebrow">Анализ</p><h1 ref={pageHeading} tabIndex={-1} id="run-heading">{runMissing ? 'Анализ не найден' : runSnapshot ? RUN_HEADINGS[runSnapshot.state] ?? 'Статус анализа неизвестен' : runChecked ? 'Статус анализа неизвестен' : 'Проверяем анализ…'}</h1><p>Номер анализа: <code>{route}</code></p>{(runSnapshot?.stage ?? runSnapshot?.context?.stage_id) === 'excavation' && <p>Этап строительства: <strong>Земляные работы котлована</strong></p>}{runSnapshot && <p>Состояние сервера: <strong>{RUN_STATES[runSnapshot.state] ?? 'Состояние доступно на сервере'}</strong></p>}{runError && <div className="attention"><p>{runError}</p><button type="button" className="secondary" disabled={runReading} onClick={() => { if (!runReading) { setRunReading(true); setRunReadAttempt(value => value + 1) } }}>{runReading ? 'Проверяем статус…' : 'Проверить статус'}</button></div>}<p role="status" className="sr-only">{runError || runAnnouncement}</p>{(runSnapshot?.retry_predecessor_id ?? runSnapshot?.retry_of_run_id) && <p>Повтор анализа <a href={`/runs/${(runSnapshot.retry_predecessor_id ?? runSnapshot.retry_of_run_id)}`} onClick={event => { event.preventDefault(); navigate(`/runs/${(runSnapshot.retry_predecessor_id ?? runSnapshot.retry_of_run_id)}`) }}>{(runSnapshot.retry_predecessor_id ?? runSnapshot.retry_of_run_id)}</a></p>}{(runSnapshot?.retry_successor_id ?? runSnapshot?.successor_run_id) && <p>Следующий анализ <a href={`/runs/${(runSnapshot.retry_successor_id ?? runSnapshot.successor_run_id)}`} onClick={event => { event.preventDefault(); navigate(`/runs/${(runSnapshot.retry_successor_id ?? runSnapshot.successor_run_id)}`) }}>{(runSnapshot.retry_successor_id ?? runSnapshot.successor_run_id)}</a></p>}{runSnapshot?.retry_eligible && <p>Повтор использует текущий профиль <code>{runSnapshot.retry_profile_id}</code>, ревизия допуска {runSnapshot.retry_authorization_revision}.{runSnapshot.profile_id !== runSnapshot.retry_profile_id && <> Исходный анализ использовал профиль <code>{runSnapshot.profile_id}</code>.</>}</p>}{runSnapshot?.retry_eligible && <button type="button" className="primary" disabled={retrying || offline} onClick={() => void retryRun()}>{retrying ? 'Создаём повтор…' : 'Повторить анализ'}</button>}{retryError && <p className="error" role="alert">{retryError}</p>}</div>{runSnapshot && <section className="panel pipeline" aria-labelledby="pipeline-heading"><h2 id="pipeline-heading">Этапы анализа</h2><ol className="pipeline-stages">{runSnapshot.stages.map(stage => <li key={stage.name} className={`pipeline-stage stage-${stage.state}`}><h3>{STAGE_LABELS[stage.name] ?? 'Этап анализа'}</h3><p>{STAGE_STATES[stage.state] ?? 'Состояние доступно на сервере'}</p>{stage.reason && <><p className="stage-reason">{STAGE_REASONS[stage.reason] ?? 'Причина не описана для пользователя.'}</p>{!STAGE_REASONS[stage.reason] && <details><summary>Техническая причина</summary><code>{stage.reason}</code></details>}</>}{stage.timestamp && <time dateTime={stage.timestamp}>{stage.timestamp}</time>}</li>)}</ol></section>}{runSnapshot && <ObservationResult run={runSnapshot} runId={route!} />}</section> : <>
        <div className="page-intro"><p className="eyebrow">Новый анализ</p><h1 ref={pageHeading} tabIndex={-1}>Наблюдение за техникой</h1><p>Выберите этап и цель анализа: распознавание техники или проверку демонстрационного правила. Привязка сохранится в анализе и его повторе.</p>{unsupportedStageNotice && <p className="attention">Выбранный этап не настроен в прототипе. Выберите доступный этап и цель анализа.</p>}</div>
        <section className="panel" aria-labelledby="demo-heading" aria-busy={demoLoading}>
          <h2 id="demo-heading">Включённые примеры</h2>
          <p>Загрузите три кадра в редактируемую форму. Это примеры разработки из архива организаторов, не оценка готовности распознавания.</p>
          <div className="upload-actions">{demoCases.cases.map(item => <button key={item.id} type="button" className="secondary" disabled={!!pending || recovering || sending || validating || demoLoading || choicesLoading} onClick={() => void loadDemo(item.id)}>{item.label}</button>)}</div>
          {demoLoading && <p role="status">Загружаем и проверяем кадры примера…</p>}
          {demoError && <p role="alert" className="error">{demoError}</p>}
          {pending && <p>Пока предыдущая отправка требует восстановления, загрузка примера недоступна. Сохранённые данные и ключ отправки не изменены.</p>}
          {selectedDemo && <div className="rule-context"><p>Источник: архив организаторов, группа <code>{selectedDemo.sourceGroup}</code>; порядок кадров соответствует архиву.</p><p>Отмеченная на кадрах дата: {selectedDemo.frames.map(frame => frame.displayedDate ?? 'не указана').join(', ')}. В исходном примере время 12:00 условное; проверьте период перед отправкой.</p><p>Зона наблюдения заявлена для этой серии; изображения не подтверждают её границы или отсутствие техники на всей площадке.</p></div>}
        </section>
        <form onSubmit={submit} noValidate aria-busy={sending}>
          <div className="form-grid"><section className="panel" aria-labelledby="context-heading"><h2 id="context-heading">Контекст наблюдения</h2><fieldset disabled={!!pending || sending || validating || choicesLoading || demoLoading}><div className="field"><label htmlFor="stage">Этап</label><select id="stage" value={stage} onChange={event => { const selected = event.target.value; setStage(selected); setIntent(choices.find(item => item.id === selected)?.rule && !observationPreferred.current ? 'rule_evaluation' : 'observation_only') }}>{choices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}</select></div><fieldset className="intent-selector"><legend>Цель анализа</legend><label><input type="radio" name="intent" value="rule_evaluation" checked={intent === 'rule_evaluation'} disabled={!choices.find(item => item.id === stage)?.rule} onChange={() => { observationPreferred.current = false; setIntent('rule_evaluation') }} /> Проверить правило этапа</label><label><input type="radio" name="intent" value="observation_only" checked={intent === 'observation_only'} onChange={() => { observationPreferred.current = true; setIntent('observation_only') }} /> Только распознать технику</label></fieldset>{choices.length > 0 && !choices.find(item => item.id === stage)?.rule && <p className="hint">Для этого этапа правило не настроено в прототипе</p>}{!choicesLoading && !choices.length && <p className="error">Не удалось загрузить настройки этапов. <button type="button" className="secondary" onClick={() => setChoicesAttempt(value => value + 1)}>Повторить загрузку настроек</button></p>}{intent === 'rule_evaluation' && choices.find(item => item.id === stage)?.rule && <div className="rule-context"><p><strong>Правило:</strong> {choices.find(item => item.id === stage)?.rule?.name}</p><p><strong>Ревизия:</strong> {choices.find(item => item.id === stage)?.rule?.revision}</p><p><strong>Ожидание:</strong> {choices.find(item => item.id === stage)?.rule?.expectation}</p><p><strong>Происхождение:</strong> {choices.find(item => item.id === stage)?.rule?.provenance}</p></div>}<div className="field"><label htmlFor="scenario">Сценарий</label><input id="scenario" value={scenario} onChange={event => setScenario(event.target.value)} aria-invalid={!!errors.scenario} aria-describedby={errors.scenario ? 'scenario-error' : undefined} maxLength={256} /><p className="hint">Например, наблюдение за земляными работами.</p>{errors.scenario && <p id="scenario-error" className="error">{errors.scenario}</p>}</div><div className="field"><label htmlFor="area">Зона наблюдения</label><input id="area" value={area} onChange={event => setArea(event.target.value)} aria-invalid={!!errors.observation_area} aria-describedby={errors.observation_area ? 'area-error' : undefined} maxLength={256} /><p className="hint">Укажите конкретный участок, к которому относятся кадры.</p>{errors.observation_area && <p id="area-error" className="error">{errors.observation_area}</p>}</div><div className="field"><label htmlFor="period">Дата и время наблюдения</label><input id="period" type="datetime-local" value={period} onChange={event => setPeriod(event.target.value)} aria-invalid={!!errors.period} aria-describedby={errors.period ? 'period-error' : undefined} />{errors.period && <p id="period-error" className="error">{errors.period}</p>}</div></fieldset><p className="context-summary">Зона: {area || 'не указана'}. Период: {period || 'не указан'}.</p></section>
          <section className="panel" aria-labelledby="images-heading"><h2 id="images-heading">Кадры наблюдения</h2><p className="muted">Выберите один JPEG или серию из 2–8 JPEG. Каждый файл — до 16 МБ и 40 миллионов пикселей. Порядок кадров влияет на анализ.</p>{intent === 'rule_evaluation' && frames.length > 0 && frames.length < 3 && <p className="attention">Для проверки правила нужны минимум три пригодных кадра одной зоны. Можно отправить меньше; достаточность определит сервер после анализа.</p>}<div className="upload-actions"><label className="file-button secondary" htmlFor="images">Выбрать JPEG</label><input id="images" type="file" accept="image/jpeg,.jpg,.jpeg" multiple onChange={onFiles} disabled={!!pending || sending || validating || demoLoading} aria-invalid={!!errors.images} aria-describedby={errors.images ? 'images-error' : undefined} /><button className="secondary" type="button" onClick={openCamera} disabled={!!pending || sending || validating || demoLoading || cameraOpen || cameraDenied}>Снять камерой</button></div>{errors.images && <p id="images-error" className="error" role="alert">{errors.images}</p>}{cameraOpen && <div className="camera"><video ref={cameraVideo} autoPlay playsInline muted aria-label="Изображение с камеры" /><div className="upload-actions"><button type="button" onClick={capture}>Сделать снимок</button><button className="secondary" type="button" onClick={closeCamera}>Закрыть камеру</button></div></div>}
          <h3>Порядок кадров</h3>{frames.length ? <ol className="manifest">{frames.map((frame, index) => <li key={frame.id} className="frame"><div><strong>Кадр {index + 1}</strong><span className="file-name">{frame.file.name}</span><small>{(frame.file.size / 1_000_000).toFixed(1)} МБ</small></div><div className="frame-actions"><button type="button" className="secondary" onClick={() => move(index, -1)} disabled={index === 0 || !!pending || sending || validating || demoLoading} aria-label={`Выше: ${frame.file.name}, кадр ${index + 1}`}>Выше</button><button type="button" className="secondary" onClick={() => move(index, 1)} disabled={index === frames.length - 1 || !!pending || sending || validating || demoLoading} aria-label={`Ниже: ${frame.file.name}, кадр ${index + 1}`}>Ниже</button><button type="button" className="secondary" onClick={() => remove(index)} disabled={!!pending || sending || validating || demoLoading} aria-label={`Удалить: ${frame.file.name}, кадр ${index + 1}`}>Удалить</button></div></li>)}</ol> : <p className="empty">Кадры ещё не выбраны.</p>}{removed && <div className="undo"><span>{removed.frame.file.name} удалён.</span><button className="secondary" type="button" onClick={restore} disabled={!!pending || sending || validating || demoLoading || frames.length >= MAX_FRAMES}>Вернуть</button></div>}<p role="status" className="sr-only">{notice}</p></section></div>
          <section className="submit-panel"><div ref={summary} tabIndex={-1} className="error-summary" role={Object.values(errors).some(Boolean) ? 'alert' : undefined}>{Object.values(errors).some(Boolean) && <><strong>Проверьте данные</strong><ul>{Object.entries(errors).filter(([, message]) => message).map(([key, message]) => <li key={key}><a href={`#${key === 'observation_area' ? 'area' : key === 'images' ? 'images-heading' : key === 'submit' ? 'submit-action' : key}`}>{message}</a></li>)}</ul></>}</div>{offline && <p className="offline" role="status">Нет соединения. Изображения останутся на этом устройстве до обновления страницы.</p>}{pending && <p className="attention">Результат предыдущей отправки неизвестен. Повторный запрос использует те же данные и ключ.</p>}<button id="submit-action" className="primary" type="submit" disabled={sending || offline || recovering || demoLoading || (!pending && (choicesLoading || !choices.length))}>{sending ? 'Создаём анализ…' : pending ? 'Повторить отправку' : 'Запустить анализ'}</button></section>
        </form>
      </>}
    </main>
  </div>
}
