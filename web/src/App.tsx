import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'

type Frame = { id: string; file: File }
type Pending = { endpoint: string; body: string; key: string }
type Errors = Partial<Record<'scenario' | 'observation_area' | 'period' | 'images' | 'submit', string>>
type Stage = { name: string; state: string; reason?: string | null; timestamp?: string | null }
type Input = { input_id: string; ordinal: number; sha256: string; artifact_id: string | null }
type Observation = { input_id: string; ordinal: number; class_name: string; state: string; reason?: string | null; source_artifact_id: string | null }
type NativeEvidence = { artifact_id: string; input_id: string; ordinal: number; sha256: string; invocation_id: string; profile_id: string; profile_revision: number; preprocessing_revision: string }
type Series = { usable_count: number; usable_input_ids: string[]; declared_observation_area: string | null; input_order: string[]; excavator_supporting_input_ids: string[]; dump_truck_persistence_input_ids: string[]; dump_truck_persistence_text: string | null }
type RunSnapshot = { run_id?: string; state: string; stages: Stage[]; context?: { period?: string; observation_area?: string; stage_id?: string }; requested_classes?: string[]; inputs?: Input[]; observations?: Observation[]; native_evidence_by_frame?: NativeEvidence[]; outcome?: string | null; result_projection?: { outcome: string; series?: Series } | null; retry_of_run_id?: string | null; successor_run_id?: string | null; retry_eligible?: boolean; retry_profile_id?: string; retry_authorization_revision?: number; profile_id?: string; authorization_revision?: number; created_at?: string }
type HistoryRun = { id: string; state: string; created_at: string | null; retry_of_run_id: string | null; successor_run_id: string | null }
type StageSummary = { stage_id: string; name: string; supported: boolean; latest_result: { run_id: string; created_at: string | null; projection: { outcome: string } } | null; latest_lifecycle: { run_id: string; created_at: string | null; state: string } | null }
const OUTCOME_LABELS: Record<string, string> = { no_check: 'Проверка не требуется', check_requested: 'Требуется проверка', insufficient_data: 'Недостаточно данных', observations_only: 'Только наблюдения', not_analyzed: 'Не анализировалось' }

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

function frameDescription(observations: Observation[], inputId: string): string {
  return observations.filter(item => item.input_id === inputId).map(item =>
    `${CLASS_LABELS[item.class_name] ?? item.class_name}: ${OBSERVATION_STATES[item.state] ?? item.state}${item.reason ? `; ${OBSERVATION_REASONS[item.reason] ?? item.reason}` : ''}`).join('. ')
}

function EvidenceViewer({ runId, inputs, observations, native, context, selected, onClose, onSelect }: {
  runId: string; inputs: Input[]; observations: Observation[]; native: NativeEvidence[]; context?: RunSnapshot['context']; selected: number;
  onClose: () => void; onSelect: (index: number) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [zoom, setZoom] = useState(1)
  const [nativeResult, setNativeResult] = useState<{ id: string; text: string } | null>(null)
  const [nativeError, setNativeError] = useState<{ id: string; code: string } | null>(null)
  const [nativeAttempt, retryNative] = useState(0)
  const frame = inputs[selected]
  const evidence = native.find(item => item.input_id === frame.input_id)
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close() }, [])
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
  return <dialog ref={dialog} aria-label="Просмотр исходных кадров" onClose={onClose} className="evidence-dialog">
    <div className="viewer-toolbar"><button type="button" className="secondary" onClick={onClose}>Закрыть</button><button type="button" className="secondary" disabled={selected === 0} onClick={() => { onSelect(selected - 1); setZoom(1) }}>Предыдущий кадр</button><button type="button" className="secondary" disabled={selected === inputs.length - 1} onClick={() => { onSelect(selected + 1); setZoom(1) }}>Следующий кадр</button><button type="button" className="secondary" onClick={() => setZoom(value => Math.min(4, value + .5))}>Увеличить</button><button type="button" className="secondary" onClick={() => setZoom(value => Math.max(1, value - .5))}>Уменьшить</button><button type="button" className="secondary" onClick={() => setZoom(1)}>Сбросить масштаб</button></div>
    <p role="status">Кадр {selected + 1} из {inputs.length}. Масштаб {Math.round(zoom * 100)}%.</p>
    <p>Входной ID: <code>{frame.input_id}</code>. Период: {context?.period ?? 'не указан'}. SHA-256 исходного кадра: <code>{frame.sha256}</code>.</p>
    <div className="viewer-image"><div style={{ width: `${zoom * 100}%` }}><SourceImage key={frame.input_id} runId={runId} artifactId={frame.artifact_id} label={`Кадр ${selected + 1}`} description={frameDescription(observations, frame.input_id)} /></div></div>
    {evidence && <details><summary>Технические данные наблюдателя</summary><p>Данные конкретного наблюдателя. Не используются правилом этапа.</p><p>Кадр {selected + 1}, входной ID <code>{frame.input_id}</code>. Вызов <code>{evidence.invocation_id}</code>. Профиль <code>{evidence.profile_id}</code>, ревизия допуска: {evidence.profile_revision}. Наблюдатель/адаптер: Grounding DINO local. Предобработка <code>{evidence.preprocessing_revision}</code>. Артефакт <code>{evidence.artifact_id}</code>, SHA-256 <code>{evidence.sha256}</code>.</p>{nativeError?.id === evidence.artifact_id ? <p className="error">{nativeError.code === 'integrity' ? 'Целостность артефакта не подтверждена' : 'Не удалось открыть технические данные'} <button type="button" className="secondary" onClick={() => { setNativeResult(null); setNativeError(null); retryNative(value => value + 1) }}>Повторить</button></p> : nativeResult?.id === evidence.artifact_id ? <pre>{nativeResult.text}</pre> : <p>Загружаем технические данные…</p>}</details>}
  </dialog>
}

function ObservationResult({ run, runId }: { run: RunSnapshot; runId: string }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const inputs = run.inputs ?? []
  const observations = run.observations ?? []
  const complete = run.state === 'succeeded' && run.outcome === 'observations_only'
  const series = run.result_projection?.series
  if (!complete && !observations.length) return null
  return <><button type="button" className="secondary" onClick={() => heading.current?.focus()}>{complete ? 'Перейти к результату' : 'Перейти к частичным наблюдениям'}</button><section className="panel result" aria-labelledby="result-heading"><h2 ref={heading} tabIndex={-1} id="result-heading">{complete ? 'Только наблюдения' : 'Частичные наблюдения — анализ не завершён'}</h2>{complete && <p>Правило этапа не проверялось</p>}<p>Период наблюдения: {run.context?.period ?? 'не указан'}</p><div className="result-frames">{inputs.filter(input => observations.some(item => item.input_id === input.input_id)).map(input => <article className="result-frame" key={input.input_id}><div><h3>Кадр {input.ordinal + 1}</h3><p>Входной ID: <code>{input.input_id}</code></p><SourceImage runId={runId} artifactId={input.artifact_id} label={`Кадр ${input.ordinal + 1}`} description={frameDescription(observations, input.input_id)} /><button type="button" className="secondary" onClick={event => { opener.current = event.currentTarget; setSelected(inputs.indexOf(input)) }}>Открыть кадр {input.ordinal + 1}</button></div><ul>{observations.filter(item => item.input_id === input.input_id).map(item => <li key={item.class_name}><strong>{CLASS_LABELS[item.class_name] ?? item.class_name}: {OBSERVATION_STATES[item.state] ?? item.state}</strong>{item.reason && <p>{OBSERVATION_REASONS[item.reason] ?? item.reason}</p>}<p>Кадр {input.ordinal + 1}, входной ID <code>{item.input_id}</code></p></li>)}</ul></article>)}</div>{complete && inputs.length > 1 && <section className="series-evidence" aria-labelledby="series-heading"><h3 id="series-heading">Данные серии</h3>{series ? <><p>Пригодных кадров: {series.usable_count}. Входные ID: {series.usable_input_ids.length ? series.usable_input_ids.join(', ') : 'нет'}.</p><p>Заявленная зона наблюдения: {series.declared_observation_area ?? 'не указана'} (со слов пользователя; по изображениям не подтверждена).</p><p>Порядок: {series.input_order.map(inputId => { const input = inputs.find(item => item.input_id === inputId); return input ? `Кадр ${input.ordinal + 1} (${inputId})` : inputId }).join(' → ')}.</p>{run.requested_classes?.includes('excavator') && <p>Кадры с экскаватором: {series.excavator_supporting_input_ids.length ? series.excavator_supporting_input_ids.join(', ') : 'нет подтверждённых'}.</p>}{series.dump_truck_persistence_text && <p>{series.dump_truck_persistence_text} Подтверждающие входные ID: {series.dump_truck_persistence_input_ids.join(', ')}.</p>}</> : <p>Сводные данные серии недоступны для этого анализа.</p>}</section>}</section>{selected !== null && <EvidenceViewer runId={runId} inputs={inputs} observations={observations} native={run.native_evidence_by_frame ?? []} context={run.context} selected={selected} onSelect={setSelected} onClose={() => { setSelected(null); opener.current?.focus() }} />}</>
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
  if (location.pathname === '/new') return 'new'
  if (location.pathname === '/history') return 'history'
  if (location.pathname === '/' || location.pathname === '/stages') return 'stages'
  const match = location.pathname.match(/^\/runs\/([0-9a-f-]{36})$/i)
  return match?.[1] ?? null
}

export default function App() {
  const [route, setRoute] = useState(runIdFromPath)
  const routeRef = useRef(route)
  const [scenario, setScenario] = useState('')
  const [area, setArea] = useState('')
  const [period, setPeriod] = useState(localPeriod)
  const [frames, setFrames] = useState<Frame[]>([])
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
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [historyPage, setHistoryPage] = useState(0)
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
    if (!route || route === 'history' || route === 'new' || route === 'stages') return
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
    setHistoryLoading(true)
    void fetch(historyPage ? `/api/runs?offset=${historyPage}` : '/api/runs').then(async response => {
      if (!response.ok) throw new Error()
      const data = await response.json() as { runs: HistoryRun[]; next_offset: number | null }
      if (active) {
        setHistoryRuns(current => historyPage ? [...current, ...data.runs.filter(run => !current.some(item => item.id === run.id))] : data.runs)
        setHistoryNextOffset(data.next_offset)
        setHistoryLoaded(true)
        setHistoryError('')
      }
    }).catch(() => { if (active) setHistoryError('Не удалось загрузить историю анализов.')
    }).finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [route, historyPage, historyAttempt])

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
    if (!route || route === 'history' || route === 'new' || route === 'stages' || retrying) return
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
    document.title = route === 'history' ? 'История анализов — Контроль строительства' : route === 'stages' ? 'Этапы — Контроль строительства' : route === 'new' ? 'Новый анализ — Контроль строительства' : route ? 'Анализ — Контроль строительства' : 'Страница не найдена — Контроль строительства'
  }, [route])

  useEffect(() => () => { cameraGeneration.current++; cameraStream.current?.getTracks().forEach(track => track.stop()) }, [])

  useEffect(() => {
    if (cameraOpen && cameraVideo.current) cameraVideo.current.srcObject = cameraStream.current
  }, [cameraOpen])

  function navigate(path: string) {
    closeCamera()
    history.pushState({}, '', path)
    routeRef.current = runIdFromPath()
    focusAfterNavigation.current = true
    setRoute(routeRef.current)
    setRunError('')
  }

  function newAnalysis() { setUnsupportedStageNotice(route === 'stages' && selectedStage !== 'excavation'); setSelectedStage('excavation'); navigate('/new') }

  function updateFrames(next: Frame[]) {
    framesRef.current = next
    setFrames(next)
  }

  async function addFiles(files: FileList | File[]) {
    if (pending || sending || busy.current) return
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
    if (!navigator.mediaDevices?.getUserMedia) {
      setErrors(current => ({ ...current, images: 'Камера недоступна. Выберите изображения из файлов.' }))
      return
    }
    const generation = ++cameraGeneration.current
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      if (!mounted.current || generation !== cameraGeneration.current || routeRef.current !== 'new') {
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
    canvas.toBlob(blob => {
      if (!mounted.current || generation !== cameraGeneration.current || routeRef.current !== 'new') return
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
    try {
      const response = await fetch(request.endpoint.replace(/^\/runs\//, '/api/runs/'), {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': request.key }, body: request.body,
      })
      if (response.status >= 400 && response.status < 500) {
        let code = ''
        try { code = String((await response.json()).code ?? '') } catch { /* Preserve the definitive HTTP status. */ }
        await clearPending()
        setPending(null)
        setErrors(current => ({ ...current, submit: code === 'idempotency_key_conflict'
          ? 'Ключ отправки уже связан с другим запросом. Проверьте данные и начните новую отправку.'
          : 'Сервер отклонил запрос. Проверьте контекст и файлы, затем повторите.' }))
        queueMicrotask(() => summary.current?.focus())
        return
      }
      const data = await response.json()
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
      busy.current = false
      setSending(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy.current || offline || recovering) return
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
        intent: 'observation_only', stage_id: selectedStage, scenario: scenario.trim(), observation_area: area.trim(),
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
    <header className="topbar"><div className="topbar-inner"><a className="brand" href="/" onClick={event => { event.preventDefault(); navigate('/') }}>Контроль строительства <span>17 мгновений ИИ</span></a><nav aria-label="Основная навигация"><a href="/" aria-current={route === 'stages' ? 'page' : undefined} onClick={event => { event.preventDefault(); navigate('/') }}>Этапы</a><a href="/history" aria-current={route === 'history' ? 'page' : undefined} onClick={event => { event.preventDefault(); navigate('/history') }}>Анализы</a></nav><a className="primary new-analysis-link" href="/new" aria-current={route === 'new' ? 'page' : undefined} onClick={event => { event.preventDefault(); newAnalysis() }}>Новый анализ</a></div></header>
    <main id="main" className="page">
      {route === 'stages' ? <section aria-labelledby="stages-heading"><div className="page-intro"><p className="eyebrow">Обзор этапов</p><h1 ref={pageHeading} tabIndex={-1} id="stages-heading">Этапы строительства</h1><p>Здесь показаны результаты завершённых анализов, привязанных к этапу. График и состояние проекта не оцениваются.</p></div>{stageError && <div className="error" role="alert"><p>{stageError}</p><button type="button" className="secondary" onClick={() => setStageAttempt(value => value + 1)}>Повторить загрузку</button></div>}<div className="stages-layout"><section className="panel" aria-labelledby="stage-map-heading" aria-busy={stageLoading}><h2 id="stage-map-heading">Карта этапов</h2>{stageLoading && !stageSummaries && <p role="status">Загружаем этапы…</p>}<div className="stage-tiles">{stageSummaries?.map(stage => <button key={stage.stage_id} className="stage-tile" type="button" aria-pressed={selectedStage === stage.stage_id} aria-controls="stage-inspector" onClick={() => setSelectedStage(stage.stage_id)}><strong>{stage.name}</strong><span>{stage.supported ? stage.latest_result ? OUTCOME_LABELS[stage.latest_result.projection.outcome] ?? 'Результат доступен' : 'Анализов нет' : 'Не настроено в прототипе'}</span>{stage.latest_lifecycle && <small>{stage.latest_result ? 'Более новый запуск' : 'Последняя попытка'}: {RUN_STATES[stage.latest_lifecycle.state] ?? 'Состояние неизвестно'}</small>}</button>)}</div><p className="hint">В прототипе настроен анализ земляных работ котлована. Другие этапы показаны для навигации.</p><button type="button" className="secondary" disabled={stageLoading} onClick={() => setStageAttempt(value => value + 1)}>{stageLoading ? 'Обновляем…' : 'Обновить этапы'}</button></section><section className="panel stage-inspector" id="stage-inspector" aria-labelledby="inspector-heading">{(() => { const stage = stageSummaries?.find(item => item.stage_id === selectedStage); if (!stage) return <p>Выберите этап.</p>; return <><p className="eyebrow">Выбранный этап</p><h2 id="inspector-heading">{stage.name}</h2><p className="stage-outcome">{stage.supported ? stage.latest_result ? OUTCOME_LABELS[stage.latest_result.projection.outcome] ?? 'Результат доступен' : 'Анализов нет' : 'Не настроено в прототипе'}</p>{stage.supported ? <>{stage.latest_result ? <p>Результат последнего завершённого анализа с сохранёнными доказательствами. {stage.latest_result.created_at && <>Время запуска: <time dateTime={stage.latest_result.created_at}>{stage.latest_result.created_at}</time>. </>}<a href={`/runs/${stage.latest_result.run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${stage.latest_result!.run_id}`) }}>Открыть доказательства</a></p> : <p>Для этого этапа ещё нет завершённого анализа с результатом.</p>}{stage.latest_lifecycle && <p className="attention">{stage.latest_result ? 'Более новый запуск' : 'Последняя попытка'}: {RUN_STATES[stage.latest_lifecycle.state] ?? 'Состояние неизвестно'}. {stage.latest_lifecycle.created_at && <>Время запуска: <time dateTime={stage.latest_lifecycle.created_at}>{stage.latest_lifecycle.created_at}</time>. </>}<a href={`/runs/${stage.latest_lifecycle.run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${stage.latest_lifecycle!.run_id}`) }}>Открыть запуск</a>. {stage.latest_result && 'Он не заменяет завершённый результат.'}</p>}</> : <p>Для этого этапа правило не настроено в прототипе. Анализ доступен для этапа «Земляные работы котлована».</p>}</> })()}</section></div></section> : route === 'history' ? <section className="panel run-history" aria-labelledby="history-heading"><h1 ref={pageHeading} tabIndex={-1} id="history-heading">История анализов</h1>{historyLoading && !historyLoaded && <p role="status">Загружаем историю…</p>}{historyError && <div className="error" role="alert"><p>{historyError}</p><button type="button" className="secondary" onClick={() => setHistoryAttempt(value => value + 1)}>Повторить загрузку</button></div>}{historyLoaded && !historyError && !historyRuns.length && <p>Анализов пока нет.</p>}<ol>{historyRuns.map(run => <li key={run.id}><a href={`/runs/${run.id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${run.id}`) }}>{run.id}</a> — {RUN_STATES[run.state] ?? run.state}, {run.created_at ? <time dateTime={run.created_at}>{run.created_at}</time> : 'дата создания неизвестна'}{run.retry_of_run_id && <> · повтор анализа <a href={`/runs/${run.retry_of_run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${run.retry_of_run_id}`) }}>{run.retry_of_run_id}</a></>}{run.successor_run_id && <> · следующий <a href={`/runs/${run.successor_run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${run.successor_run_id}`) }}>{run.successor_run_id}</a></>}</li>)}</ol>{historyNextOffset !== null && !historyError && <button type="button" className="secondary" disabled={historyLoading} onClick={() => setHistoryPage(historyNextOffset)}>{historyLoading ? 'Загружаем…' : 'Показать ещё'}</button>}</section> : route === null ? <section className="panel" aria-labelledby="not-found-heading"><h1 ref={pageHeading} tabIndex={-1} id="not-found-heading">Страница не найдена</h1><p>Проверьте адрес или откройте обзор этапов.</p></section> : route !== 'new' ? <section className="run-workspace" aria-labelledby="run-heading" aria-busy={runReading}><div className="panel run-header"><p className="eyebrow">Анализ</p><h1 ref={pageHeading} tabIndex={-1} id="run-heading">{runMissing ? 'Анализ не найден' : runSnapshot ? RUN_HEADINGS[runSnapshot.state] ?? 'Статус анализа неизвестен' : runChecked ? 'Статус анализа неизвестен' : 'Проверяем анализ…'}</h1><p>Номер анализа: <code>{route}</code></p>{runSnapshot?.context?.stage_id === 'excavation' && <p>Этап строительства: <strong>Земляные работы котлована</strong></p>}{runSnapshot && <p>Состояние сервера: <strong>{RUN_STATES[runSnapshot.state] ?? 'Состояние доступно на сервере'}</strong></p>}{runError && <div className="attention"><p>{runError}</p><button type="button" className="secondary" disabled={runReading} onClick={() => { if (!runReading) { setRunReading(true); setRunReadAttempt(value => value + 1) } }}>{runReading ? 'Проверяем статус…' : 'Проверить статус'}</button></div>}<p role="status" className="sr-only">{runError || runAnnouncement}</p>{runSnapshot?.retry_of_run_id && <p>Повтор анализа <a href={`/runs/${runSnapshot.retry_of_run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${runSnapshot.retry_of_run_id}`) }}>{runSnapshot.retry_of_run_id}</a></p>}{runSnapshot?.successor_run_id && <p>Следующий анализ <a href={`/runs/${runSnapshot.successor_run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${runSnapshot.successor_run_id}`) }}>{runSnapshot.successor_run_id}</a></p>}{runSnapshot?.retry_eligible && <p>Повтор использует текущий профиль <code>{runSnapshot.retry_profile_id}</code>, ревизия допуска {runSnapshot.retry_authorization_revision}.{runSnapshot.profile_id !== runSnapshot.retry_profile_id && <> Исходный анализ использовал профиль <code>{runSnapshot.profile_id}</code>.</>}</p>}{runSnapshot?.retry_eligible && <button type="button" className="primary" disabled={retrying || offline} onClick={() => void retryRun()}>{retrying ? 'Создаём повтор…' : 'Повторить анализ'}</button>}{retryError && <p className="error" role="alert">{retryError}</p>}</div>{runSnapshot && <section className="panel pipeline" aria-labelledby="pipeline-heading"><h2 id="pipeline-heading">Этапы анализа</h2><ol className="pipeline-stages">{runSnapshot.stages.map(stage => <li key={stage.name} className={`pipeline-stage stage-${stage.state}`}><h3>{STAGE_LABELS[stage.name] ?? 'Этап анализа'}</h3><p>{STAGE_STATES[stage.state] ?? 'Состояние доступно на сервере'}</p>{stage.reason && <><p className="stage-reason">{STAGE_REASONS[stage.reason] ?? 'Причина не описана для пользователя.'}</p>{!STAGE_REASONS[stage.reason] && <details><summary>Техническая причина</summary><code>{stage.reason}</code></details>}</>}{stage.timestamp && <time dateTime={stage.timestamp}>{stage.timestamp}</time>}</li>)}</ol></section>}{runSnapshot && <ObservationResult run={runSnapshot} runId={route!} />}</section> : <>
        <div className="page-intro"><p className="eyebrow">Новый анализ</p><h1 ref={pageHeading} tabIndex={-1}>Наблюдение за техникой</h1><p>Этап строительства: <strong>Земляные работы котлована</strong>. Привязка сохранится в анализе и его повторе.</p>{unsupportedStageNotice && <p className="attention">Выбранный этап не настроен в прототипе. Новый анализ привязан к этапу «Земляные работы котлована».</p>}<p>Добавьте снимки и контекст наблюдения. Анализ распознаёт экскаватор и самосвал на отдельных кадрах; правило этапа и отсутствие техники на всей площадке здесь не проверяются.</p></div>
        <form onSubmit={submit} noValidate aria-busy={sending}>
          <div className="form-grid"><section className="panel" aria-labelledby="context-heading"><h2 id="context-heading">Контекст наблюдения</h2><p className="muted">Режим: только распознать технику</p><fieldset disabled={!!pending || sending || validating}><div className="field"><label htmlFor="scenario">Сценарий</label><input id="scenario" value={scenario} onChange={event => setScenario(event.target.value)} aria-invalid={!!errors.scenario} aria-describedby={errors.scenario ? 'scenario-error' : undefined} maxLength={256} /><p className="hint">Например, наблюдение за земляными работами.</p>{errors.scenario && <p id="scenario-error" className="error">{errors.scenario}</p>}</div><div className="field"><label htmlFor="area">Зона наблюдения</label><input id="area" value={area} onChange={event => setArea(event.target.value)} aria-invalid={!!errors.observation_area} aria-describedby={errors.observation_area ? 'area-error' : undefined} maxLength={256} /><p className="hint">Укажите конкретный участок, к которому относятся кадры.</p>{errors.observation_area && <p id="area-error" className="error">{errors.observation_area}</p>}</div><div className="field"><label htmlFor="period">Дата и время наблюдения</label><input id="period" type="datetime-local" value={period} onChange={event => setPeriod(event.target.value)} aria-invalid={!!errors.period} aria-describedby={errors.period ? 'period-error' : undefined} />{errors.period && <p id="period-error" className="error">{errors.period}</p>}</div></fieldset></section>
          <section className="panel" aria-labelledby="images-heading"><h2 id="images-heading">Кадры наблюдения</h2><p className="muted">Выберите один JPEG или серию из 2–8 JPEG. Каждый файл — до 16 МБ и 40 миллионов пикселей. Порядок кадров влияет на анализ.</p><div className="upload-actions"><label className="file-button secondary" htmlFor="images">Выбрать JPEG</label><input id="images" type="file" accept="image/jpeg,.jpg,.jpeg" multiple onChange={onFiles} disabled={!!pending || sending || validating} aria-invalid={!!errors.images} aria-describedby={errors.images ? 'images-error' : undefined} /><button className="secondary" type="button" onClick={openCamera} disabled={!!pending || sending || validating || cameraOpen || cameraDenied}>Снять камерой</button></div>{errors.images && <p id="images-error" className="error" role="alert">{errors.images}</p>}{cameraOpen && <div className="camera"><video ref={cameraVideo} autoPlay playsInline muted aria-label="Изображение с камеры" /><div className="upload-actions"><button type="button" onClick={capture}>Сделать снимок</button><button className="secondary" type="button" onClick={closeCamera}>Закрыть камеру</button></div></div>}
          <h3>Порядок кадров</h3>{frames.length ? <ol className="manifest">{frames.map((frame, index) => <li key={frame.id} className="frame"><div><strong>Кадр {index + 1}</strong><span className="file-name">{frame.file.name}</span><small>{(frame.file.size / 1_000_000).toFixed(1)} МБ</small></div><div className="frame-actions"><button type="button" className="secondary" onClick={() => move(index, -1)} disabled={index === 0 || !!pending || sending || validating} aria-label={`Выше: ${frame.file.name}, кадр ${index + 1}`}>Выше</button><button type="button" className="secondary" onClick={() => move(index, 1)} disabled={index === frames.length - 1 || !!pending || sending || validating} aria-label={`Ниже: ${frame.file.name}, кадр ${index + 1}`}>Ниже</button><button type="button" className="secondary" onClick={() => remove(index)} disabled={!!pending || sending || validating} aria-label={`Удалить: ${frame.file.name}, кадр ${index + 1}`}>Удалить</button></div></li>)}</ol> : <p className="empty">Кадры ещё не выбраны.</p>}{removed && <div className="undo"><span>{removed.frame.file.name} удалён.</span><button className="secondary" type="button" onClick={restore} disabled={!!pending || sending || validating || frames.length >= MAX_FRAMES}>Вернуть</button></div>}<p role="status" className="sr-only">{notice}</p></section></div>
          <section className="submit-panel"><div ref={summary} tabIndex={-1} className="error-summary" role={Object.values(errors).some(Boolean) ? 'alert' : undefined}>{Object.values(errors).some(Boolean) && <><strong>Проверьте данные</strong><ul>{Object.entries(errors).filter(([, message]) => message).map(([key, message]) => <li key={key}><a href={`#${key === 'observation_area' ? 'area' : key === 'images' ? 'images-heading' : key === 'submit' ? 'submit-action' : key}`}>{message}</a></li>)}</ul></>}</div>{offline && <p className="offline" role="status">Нет соединения. Изображения останутся на этом устройстве до обновления страницы.</p>}{pending && <p className="attention">Результат предыдущей отправки неизвестен. Повторный запрос использует те же данные и ключ.</p>}<button id="submit-action" className="primary" type="submit" disabled={sending || offline || recovering}>{sending ? 'Создаём анализ…' : pending ? 'Повторить отправку' : 'Запустить анализ'}</button></section>
        </form>
      </>}
    </main>
  </div>
}
