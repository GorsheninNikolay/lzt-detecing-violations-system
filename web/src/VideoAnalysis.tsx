import { useContext, useEffect, useRef, useState, type DragEvent } from 'react'
import { AiAssessmentPanel, type AiAssessment } from './AiAssessment'
import { equipmentLabel, stageLabel } from './displayLabels'
import { AccountIdentity } from './AccountIdentity'
import { validLocalPeriod } from './localPeriod'
import { savePendingVideo, restorePendingVideo, clearPendingVideo, videoScope, type PendingVideo } from './videoRecovery'
import { randomUUID } from './randomUUID'
import './video.css'

type Zone = { id: string; name: string }
type VideoFrame = { timestamp_seconds: number; input_id?: string; ordinal?: number; assessment?: { stage?: string; stage_reason?: string; objects?: { type_ru?: string; catalog_class?: string; evidence?: string; status?: string }[] } }
export type VideoSnapshot = { media_kind?: string; id?: string; run_id?: string; state: string; stage?: string; progress?: unknown; metadata?: Record<string, unknown>; device?: unknown; result?: { video_url?: string; selected_frames?: VideoFrame[]; assessment?: AiAssessment | null; limitations?: string[] }; error?: unknown; retry_cpu_eligible?: boolean }
const stages: Record<string, string> = { queued: 'В очереди', preparation: 'Подготовка видео', preparing: 'Подготовка видео', yolo: 'Распознавание двумя YOLO', deepseek: 'Разбор выбранных моментов', assembly: 'Сборка видео', encoding: 'Сборка видео', complete: 'Готово', succeeded: 'Готово', completed: 'Готово', failed: 'Обработка остановлена' }
function readable(value: unknown): string {
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}
const errors: Record<string, string> = {
  video_limits_exceeded: 'Ролик превышает ограничения: до 2 минут, 4K и 60 кадров/с. Подготовьте более короткую или уменьшенную копию.',
  video_size_exceeded: 'Размер ролика превышает 200 МБ. Подготовьте уменьшенную копию.',
  video_codec_unsupported: 'Этот видеокодек не поддерживается. Сохраните MP4 или MOV с H.264 либо H.265.',
  video_stream_invalid: 'В файле нет поддерживаемого видеопотока. Выберите другой MP4 или MOV.',
  video_metadata_invalid: 'Не удалось прочитать параметры видео. Пересохраните ролик и повторите загрузку.',
  invalid_video_file: 'Не удалось прочитать видео. Возможно, файл повреждён.',
  video_decode_failed: 'Не удалось декодировать видео. Пересохраните ролик и повторите загрузку.',
  video_timestamps_invalid: 'Временные метки видео повреждены. Пересохраните ролик перед загрузкой.',
  video_ffmpeg_unavailable: 'Обработка видео на сервере пока не настроена. Обратитесь к администратору.',
  video_gpu_failed_retry_cpu_available: 'GPU остановился во время обработки. Можно отдельно повторить распознавание на CPU.',
  video_cloud_outcome_uncertain: 'Исход вызова DeepSeek неизвестен. Автоматического повторного платного запроса не будет.',
  video_interrupted: 'Обработка прервана перезапуском сервера. Сохранённые результаты доступны ниже.',
  video_processing_failed: 'Не удалось завершить обработку видео. Сохранённые результаты доступны ниже.',
  plan_revision_conflict: 'План изменился. Обновите страницу и проверьте новую ревизию перед отправкой.',
  cloud_consent_required: 'Для запуска подтвердите согласие на передачу выбранных кадров.',
  cloud_provider_unavailable: 'Облачная обработка сейчас недоступна. Повторите позднее.',
  profile_unauthorized: 'Профиль распознавания сейчас недоступен. Обратитесь к администратору.',
  service_not_ready: 'Сервер ещё не готов к обработке. Повторите позднее.',
}
function errorMessage(value: unknown) { const text = readable(value); return errors[text] ?? text }

async function responseData(response: Response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail?.message ?? data.detail?.code ?? data.code ?? (typeof data.detail === 'string' ? data.detail : `Ошибка сервера (${response.status})`))
  return data
}

export function VideoAnalysisForm({ projectId, accountId = '', onOpen, onDirty, onLockChange, provider = 'deepseek', providerLabel = 'DeepSeek' }: { projectId: string; accountId?: string; onLockChange?: (locked: boolean) => void; provider?: string; providerLabel?: string; onOpen: (path: string) => void; onDirty: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [zones, setZones] = useState<Zone[]>([])
  const [zone, setZone] = useState('')
  const [plan, setPlan] = useState<{ revision_id?: string; revision_number: number } | null>(null)
  const [planLoading, setPlanLoading] = useState(false)
  const [started, setStarted] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [unknown, setUnknown] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [recovering, setRecovering] = useState(true)
  const [storageReady, setStorageReady] = useState(false)
  const scope = videoScope(accountId, projectId)
  const lifetime = useRef(0)
  const submitting = useRef(false)
  const uploadController = useRef<AbortController | null>(null)
  useEffect(() => { onLockChange?.(busy || unknown); return () => onLockChange?.(false) }, [busy, unknown, onLockChange])
  const request = useRef<PendingVideo | null>(null)
  useEffect(() => {
    const generation = ++lifetime.current
    request.current = null; submitting.current = false
    setFile(null); setBusy(false); setUnknown(false); setConsent(false)
    setRecovering(true); setStorageReady(false)
    void restorePendingVideo(scope).then(pending => {
      if (lifetime.current !== generation) return
      setStorageReady(true)
      if (pending) {
        request.current = pending; setFile(pending.file); setUnknown(true); setConsent(true)
        setZone(new URLSearchParams(pending.query).get('zone_id') ?? '')
        onDirty()
      }
    }).catch(() => { if (lifetime.current === generation) setError('Не удалось открыть хранилище восстановления. Разрешите локальное хранение в браузере и обновите страницу; видео пока не отправлено.') }).finally(() => { if (lifetime.current === generation) setRecovering(false) })
    return () => { lifetime.current++; uploadController.current?.abort() }
  }, [scope])
  useEffect(() => {
    if (!projectId) return
    const controller = new AbortController()
    void fetch(`/api/projects/${projectId}/zones`, { signal: controller.signal }).then(responseData).then(data => { if (!controller.signal.aborted) { setZones(data.zones); setZone(current => current || data.zones[0]?.id || '') } }).catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить участки. Обновите страницу перед отправкой.') })
    return () => controller.abort()
  }, [projectId])
  useEffect(() => {
    setPlan(null)
    if (!zone) return
    const controller = new AbortController()
    setPlanLoading(true)
    void fetch(`/api/zones/${zone}/plan`, { signal: controller.signal }).then(responseData).then(data => { if (!controller.signal.aborted) setPlan(data) }).catch(() => { if (!controller.signal.aborted) setError('Не удалось проверить ревизию плана. Обновите страницу перед отправкой.') }).finally(() => { if (!controller.signal.aborted) setPlanLoading(false) })
    return () => controller.abort()
  }, [zone])
  function select(files: File[]) {
    if (busy || unknown) return
    onDirty()
    setConsent(false)
    setFile(null)
    if (files.length !== 1) { setError('Выберите один ролик MP4 или MOV.'); return }
    const selected = files[0]
    if (!/\.(mp4|mov)$/i.test(selected.name)) { setError('Поддерживаются файлы MP4 и MOV.'); return }
    if (selected.size > 200_000_000 || !selected.size) { setError('Размер ролика должен быть от 1 байта до 200 МБ.'); return }
    setFile(selected); request.current = null; setError('')
  }
  function drop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setDragging(false); select(Array.from(event.dataTransfer.files)) }
  async function submit() {
    if (submitting.current || recovering || !storageReady || !file || !consent) return
    if (!request.current && confirmed && !validLocalPeriod(started)) {
      setError('Укажите существующие местные дату и время начала съёмки.'); return
    }
    const generation = lifetime.current
    const active = () => lifetime.current === generation
    submitting.current = true
    setBusy(true); setError('')
    let dispatched = false
    try {
      if (!request.current) {
        const params = new URLSearchParams({ cloud_processing_consent: 'true', cloud_provider: provider })
        if (projectId) params.set('project_id', projectId)
        if (zone) params.set('zone_id', zone)
        if (confirmed && plan?.revision_id) params.set('plan_revision_id', plan.revision_id)
        if (confirmed && started) params.set('capture_started_at', new Date(started).toISOString())
        const pending = { key: randomUUID(), query: params.toString(), file }
        const saved = await savePendingVideo(scope, pending)
        if (!active()) return
        request.current = saved
        if (saved.key !== pending.key) {
          setFile(saved.file); setZone(new URLSearchParams(saved.query).get('zone_id') ?? ''); setUnknown(true); setConsent(true)
          setError('В другой вкладке уже сохранена отправка для этого проекта. Восстановлен её исходный ролик; нажмите «Восстановить отправку», чтобы проверить тот же запрос.'); return
        }
      }
      const pending = request.current
      setUnknown(true)
      const controller = new AbortController()
      uploadController.current = controller
      dispatched = true
      const response = await fetch(`/api/runs/video?${pending.query}`, { method: 'POST', signal: controller.signal, headers: { 'Content-Type': /\.mov$/i.test(pending.file.name) ? 'video/quicktime' : 'video/mp4', 'Idempotency-Key': pending.key }, body: pending.file })
      if (!active()) return
      if (!response.ok && response.status < 500) {
        await clearPendingVideo(scope, pending.key)
        if (!active()) return
        request.current = null; setUnknown(false)
      }
      const data = await responseData(response)
      if (!active()) return
      if (typeof data.run_id !== 'string') throw new Error('Сервер не вернул номер анализа. Восстановите отправку с прежним ключом.')
      await clearPendingVideo(scope, pending.key)
      if (!active()) return
      setUnknown(false)
      onOpen(`/runs/${data.run_id}`)
    } catch (reason) {
      if (!active()) return
      setError(!dispatched ? 'Не удалось сохранить видео для безопасного восстановления. Освободите место в браузере и повторите; запрос не отправлен.' : reason instanceof TypeError ? 'Связь прервалась. Результат отправки неизвестен; повтор использует сохранённые файл и ключ, чтобы не создавать ещё один анализ.' : errorMessage(reason instanceof Error ? reason.message : reason))
    } finally { if (active()) { submitting.current = false; setBusy(false) } }
  }
  return <section className="panel video-upload" aria-labelledby="video-heading" aria-busy={busy}>
    <h2 id="video-heading">Видео наблюдения</h2>
    {!projectId && <p className="attention">Для видео откройте проект и выберите «Новый анализ». Так ролик и результаты сохранятся в нужном участке.</p>}
    <p>Один MP4 или MOV: до 2 минут и 200 МБ, H.264/H.265, до 4K и 60 кадров/с. Сервер проверит параметры до распознавания. Результат: MP4 до 720p со звуком и рамками обеих YOLO.</p>
    <fieldset disabled={busy || unknown || recovering || !storageReady}>
      <div className="upload-zone" data-dragging={dragging} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={drop}>
        <p className="upload-zone-title">Перетащите ролик сюда</p><label className="file-button secondary" htmlFor="video-file">Выбрать видео</label><input id="video-file" type="file" accept="video/mp4,video/quicktime,.mp4,.mov" onChange={event => { select(Array.from(event.target.files ?? [])); event.target.value = '' }} />
      </div>
      {file && <p role="status">{file.name} · {(file.size / 1_000_000).toFixed(1)} МБ</p>}
      {projectId && <label className="field" htmlFor="video-zone">Участок<select id="video-zone" value={zone} onChange={event => { setZone(event.target.value); onDirty() }}>{zones.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      {zone && <p>{planLoading ? 'Проверяем план…' : plan?.revision_id ? `При подтверждённом времени используем ревизию плана ${plan.revision_number}.` : 'В участке пока нет сохранённого плана. Анализируем наблюдения.'}</p>}
      <label className="field" htmlFor="video-start">Начало съёмки (по часовому поясу устройства)<input id="video-start" type="datetime-local" value={started} onChange={event => { setStarted(event.target.value); setConfirmed(false); onDirty() }} /></label>
      <label><input type="checkbox" checked={confirmed} disabled={!started} onChange={event => { setConfirmed(event.target.checked); onDirty() }} /> Подтверждаю время начала съёмки для сопоставления с планом</label>
      <p>Если время неизвестно, оставьте поле пустым. Покажем относительное время ролика без выводов о соблюдении сроков.</p>
      <label><input type="checkbox" checked={consent} onChange={event => { setConsent(event.target.checked); onDirty() }} /> Разрешаю отправить до 8 выбранных кадров и контекст в {providerLabel} для облачного разбора моделью DeepSeek. Звук модели не передаётся.</label>
    </fieldset>
    <p>Обе YOLO обрабатывают каждый кадр. DeepSeek разбирает до 8 равномерно выбранных моментов: выводы не доказывают отсутствие событий между ними. Устройство обработки определяется сервером; CPU работает медленнее.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {unknown && <p className="attention">Исход отправки неизвестен. Файл и исходные параметры сохранены в браузере для этого аккаунта и проекта. Восстановите отправку с прежним ключом.</p>}
    <button type="button" className="primary" disabled={busy || recovering || !storageReady || !file || !consent || !projectId || !zone || (!unknown && (planLoading || !plan))} onClick={() => void submit()}>{recovering ? 'Проверяем сохранённую отправку…' : busy ? 'Загружаем видео…' : unknown ? 'Восстановить отправку' : 'Запустить анализ видео'}</button>
  </section>
}

export function VideoResult({ runId, initial, readOnly, onOpen }: { runId: string; initial: VideoSnapshot; readOnly: boolean; onOpen: (path: string) => void }) {
  const [snapshot, setSnapshot] = useState(initial)
  const [error, setError] = useState('')
  const [readError, setReadError] = useState('')
  const [retrying, setRetrying] = useState(false)
  const video = useRef<HTMLVideoElement>(null)
  const accountId = useContext(AccountIdentity)
  const retryStorageKey = `video-cpu-retry:${videoScope(accountId, runId)}`
  const retryKey = useRef('')
  const retryController = useRef<AbortController | null>(null)
  const retryGeneration = useRef(0)
  const retryBusy = useRef(false)
  useEffect(() => { retryGeneration.current++; retryBusy.current = false; retryKey.current = ''; return () => { retryGeneration.current++; retryController.current?.abort() } }, [runId, accountId])
  useEffect(() => {
    let canceled = false
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function read() {
      try {
        const data = await responseData(await fetch(`/api/video-runs/${runId}`, { signal: controller.signal }))
        if (canceled) return
        setSnapshot(data); setReadError('')
        if (!['succeeded', 'failed', 'partial'].includes(data.state)) timer = setTimeout(() => void read(), 2000)
      } catch { if (!canceled) { setReadError('Не удалось обновить состояние. Сохранённые данные показаны ниже; проверим снова.'); timer = setTimeout(() => void read(), 5000) } }
    }
    void read()
    return () => { canceled = true; controller.abort(); clearTimeout(timer) }
  }, [runId])
  async function retry() {
    if (retryBusy.current) return
    retryBusy.current = true
    const generation = retryGeneration.current
    const controller = new AbortController()
    retryController.current = controller
    setRetrying(true)
    try {
      retryKey.current = localStorage.getItem(retryStorageKey) || retryKey.current || `video-cpu-${runId}`
      localStorage.setItem(retryStorageKey, retryKey.current)
      const data = await responseData(await fetch(`/api/video-runs/${runId}/retry-cpu`, { method: 'POST', signal: controller.signal, headers: { 'Idempotency-Key': retryKey.current } }))
      if (retryGeneration.current !== generation) return
      localStorage.removeItem(retryStorageKey)
      onOpen(`/runs/${data.run_id}`)
    } catch (reason) { if (retryGeneration.current === generation) setError(readable(reason instanceof Error ? reason.message : reason)) }
    finally { if (retryGeneration.current === generation) { retryBusy.current = false; setRetrying(false) } }
  }
  const result = snapshot.result
  return <section className="panel video-result" aria-labelledby="video-result-heading"><h1 id="video-result-heading">Видеоанализ</h1>
    <p role="status">{snapshot.state === 'failed' ? stages.failed : stages[snapshot.stage ?? ''] ?? stages[snapshot.state] ?? 'Обработка видео'}</p>
    {!!snapshot.device && <p>Фактическое устройство: {typeof snapshot.device === 'object' && snapshot.device !== null ? readable((snapshot.device as Record<string, unknown>).actual_device) : readable(snapshot.device)}{readable(snapshot.device).toLowerCase().includes('cpu') ? '. CPU обрабатывает видео медленнее.' : ''}</p>}
    {typeof snapshot.progress === 'number' && <p>Обработано: {Math.round(snapshot.progress * 100)}%</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {readError && <p className="error" role="alert">{readError}</p>}
    {!!snapshot.error && <p className="error" role="alert">{errorMessage(snapshot.error)}</p>}
    {snapshot.state === 'failed' && <p>Обработка остановлена. Сохранённая разметка доступна ниже, если сборка видео завершилась. Объяснение DeepSeek может отсутствовать.</p>}
    {result?.video_url && <><video ref={video} controls playsInline preload="metadata" src={result.video_url} aria-label="Видео с рамками двух YOLO" /><p><a className="secondary" href={result.video_url} download={`analysis-${runId}.mp4`}>Скачать MP4 с рамками</a></p></>}
    {!!result?.assessment && <AiAssessmentPanel assessment={result.assessment} evidence={[]} inputs={(result.selected_frames ?? []).map((frame, index) => ({ input_id: frame.input_id ?? String(index), ordinal: index, sha256: '', artifact_id: null }))} onOpenFrame={id => { const frame = result.selected_frames?.find(item => item.input_id === id); if (video.current && frame) { video.current.currentTime = frame.timestamp_seconds; video.current.focus() } }} />}
    {!!result?.selected_frames?.length && <section><h2>Моменты, переданные DeepSeek</h2><ol>{result.selected_frames.map((frame, index) => <li key={index}><button type="button" className="secondary" disabled={!result.video_url} onClick={() => { if (video.current) { video.current.currentTime = frame.timestamp_seconds; video.current.focus() } }}>{frame.timestamp_seconds.toFixed(2)} с</button>{!!frame.assessment && <><p>{stageLabel(frame.assessment.stage ?? 'unknown')}: {frame.assessment.stage_reason}</p>{!!frame.assessment.objects?.length && <ul>{frame.assessment.objects.map((object, index) => <li key={index}>{equipmentLabel(object.catalog_class ?? '', object.type_ru)}{object.status === 'uncertain' ? ' (тип не определён уверенно)' : ''}: {object.evidence}</li>)}</ul>}</>}</li>)}</ol></section>}
    <p>Объяснение относится только к выбранным моментам. Отсутствие событий между ними не подтверждено.</p>
    {result?.limitations?.map((limitation, index) => <p key={index}>{limitation}</p>)}
    {snapshot.retry_cpu_eligible && !readOnly && <button type="button" className="secondary" disabled={retrying} onClick={() => void retry()}>{retrying ? 'Создаём повтор…' : 'Повторить YOLO на CPU'}</button>}
    <details><summary>Технические сведения</summary><pre className="video-explanation">{readable({ metadata: snapshot.metadata, device: snapshot.device })}</pre></details>
  </section>
}
