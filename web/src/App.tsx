import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react'
import demoCases from './demoCases.json'
import AppHeader from './AppHeader'
import FramePreview from './FramePreview'
import NewAnalysisPage, { UploadZone } from './NewAnalysisPage'
import ReadinessPage from './ReadinessPage'
import ProviderComparisonPage from './ProviderComparisonPage'
import SignalsPage from './SignalsPage'
import './result.css'

type Frame = { id: string; file: File }
type DemoCase = (typeof demoCases.cases)[number]
type Pending = { endpoint: string; body: string; key: string }
type Errors = Partial<Record<'scenario' | 'observation_area' | 'period' | 'images' | 'submit', string>>
type Stage = { name: string; state: string; reason?: string | null; timestamp?: string | null }
type Input = { input_id: string; ordinal: number; sha256: string; artifact_id: string | null }
type Observation = { input_id: string; ordinal: number; class_name: string; state: string; reason?: string | null; source_artifact_id: string | null; input_sha256?: string; invocation_id?: string | null }
type NativeEvidence = { artifact_id: string; input_id: string; ordinal: number; sha256: string; invocation_id: string; profile_id: string; profile_revision: number; preprocessing_revision?: string | null }
type DetectedObject = { input_id: string; class_name: string; score: number; box: [number, number, number, number]; image_size: [number, number]; invocation_id: string }
type Series = { usable_count: number; usable_input_ids: string[]; declared_observation_area: string | null; input_order: string[]; excavator_supporting_input_ids: string[]; dump_truck_persistence_input_ids: string[]; dump_truck_persistence_text: string | null }
type Rule = { name: string; revision: string; expectation: string; provenance: string; recommendation: string | null }
type Choice = { id: string; label: string; rule: Rule | null }
type ResultProjection = { outcome: string; frames?: Observation[]; context?: { period?: string; observation_area?: string; stage_id?: string }; series?: Series; reason?: string | null; uncertainty?: string | null; recommendation?: string | null; rule?: Rule | null; supporting_input_ids?: string[] | null; stage_hypotheses?: { stage: string; equipment: string; scene_features: string[] }[] }
type ProfileSnapshot = { adapter?: { code?: string } }
type ResultFrame = { input_id: string; ordinal: number; artifact_id: string | null; sha256: string | null; usable: boolean | null; observations: Observation[] }
type RunSnapshot = { run_id?: string; purpose?: string; state: string; stages: Stage[]; context?: { period?: string; observation_area?: string; stage_id?: string }; intent?: string; stage?: string | null; profile_snapshot?: ProfileSnapshot; rule_snapshot?: Rule | null; requested_classes?: string[]; inputs?: Input[]; observations?: Observation[]; objects?: DetectedObject[]; native_evidence_by_frame?: NativeEvidence[]; outcome?: string | null; result_projection?: ResultProjection | null; plan_binding?: { zone_id: string; revision_id: string; capture_times: string[] } | null; stage_confirmation?: { stage: string; comment: string; created_at?: string } | null; retry_predecessor_id?: string | null; retry_successor_id?: string | null; retry_of_run_id?: string | null; successor_run_id?: string | null; retry_eligible?: boolean; retry_profile_id?: string; retry_authorization_revision?: number; profile_id?: string; authorization_revision?: number; created_at?: string }
type StageSummary = { stage_id: string; name: string; supported: boolean; latest_result: { run_id: string; created_at: string | null; projection: { outcome: string } } | null; latest_lifecycle: { run_id: string; created_at: string | null; state: string } | null }
type HistoryRun = { id: string; run_id: string; created_at: string | null; stage: string | null; intent: string; state: string; outcome: string | null; retry_predecessor_id: string | null; retry_successor_id: string | null; retry_of_run_id?: string | null; successor_run_id?: string | null }
const OUTCOME_LABELS: Record<string, string> = { observations_only: 'Только наблюдения', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось', no_check: 'Проверка не запрошена', check_requested: 'Рекомендована проверка человеком' }

const CLASS_LABELS: Record<string, string> = { excavator: 'Экскаватор', dump_truck: 'Самосвал', road_roller: 'Каток', truck_mounted_crane: 'Кран-манипулятор', concrete_mixer_truck: 'Автобетоносмеситель', bulldozer: 'Бульдозер', truck: 'Грузовик', mobile_crane: 'Автокран' }
const EQUIPMENT = Object.keys(CLASS_LABELS)
const STAGE_NAMES: Record<string, string> = { excavation: 'Земляные работы', concreting: 'Бетонные работы', roadwork: 'Дорожные работы' }
type Project = { id: string; name: string; timezone: string }
type Zone = { id: string; name: string }
type CatalogWork = { id: string; source_row: number; code: string | null; title: string }
type PlanEntry = { id?: string; catalog_work_id: string; starts_at: string; ends_at: string; state: 'planned' | 'active' | 'completed'; stage_key: string | null; expected_equipment: string[]; allowed_equipment: string[]; excluded_equipment: string[] }
type ZonePlan = { revision_id?: string; revision_number: number; entries: PlanEntry[] }
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

function SourceImage({ runId, artifactId, label, description, objects = [], showBoxes = false }: { runId: string; artifactId: string | null; label: string; description: string; objects?: DetectedObject[]; showBoxes?: boolean }) {
  const artifact = useArtifact(runId, artifactId)
  return <div className="source-image">{!artifactId ? <p className="error">Исходное изображение недоступно для этого кадра.</p> : artifact.url ? <div className="annotated-image"><img src={artifact.url} alt={`Исходное изображение: ${label}. ${description}`} />{showBoxes && objects.map((object, index) => {
    const [x1, y1, x2, y2] = object.box
    if (!(x1 >= 0 && y1 >= 0 && x2 <= 1 && y2 <= 1 && x2 > x1 && y2 > y1 && [x1, y1, x2, y2].every(Number.isFinite))) return null
    return <div key={`${object.invocation_id}-${index}`} className="object-box" aria-hidden="true" style={{ left: `${100 * x1}%`, top: `${100 * y1}%`, width: `${100 * (x2 - x1)}%`, height: `${100 * (y2 - y1)}%` }}><span>{CLASS_LABELS[object.class_name] ?? object.class_name}</span></div>
  })}</div> :
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

function EvidenceViewer({ runId, frames, native, objects, showBoxes, profile, context, selected, onClose, onSelect }: {
  runId: string; frames: ResultFrame[]; native: NativeEvidence[]; objects: DetectedObject[]; showBoxes: boolean; profile?: ProfileSnapshot; context?: RunSnapshot['context']; selected: number;
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
    <p>Период: {context?.period ?? 'не указан'}.</p>
    <div className="viewer-image"><div style={{ width: `${zoom * 100}%` }}><SourceImage key={frame.input_id} runId={runId} artifactId={frame.artifact_id} label={`Кадр ${frame.ordinal + 1}`} description={frameDescription(frame.observations)} objects={objects.filter(item => item.input_id === frame.input_id)} showBoxes={showBoxes} /></div></div>
    <details><summary>Подробности кадра</summary><p>Входной ID: <code>{frame.input_id}</code>.</p><p>Исходный артефакт ID: <code>{frame.artifact_id ?? 'не указан'}</code>. SHA-256 исходного кадра: <code>{frame.sha256 ?? 'не указан'}</code>.</p></details>
    {evidence && <details><summary>Технические данные наблюдателя</summary><p>Данные конкретного наблюдателя. Не используются правилом этапа.</p><p>Адаптер: <code>{profile?.adapter?.code ?? 'не указан'}</code>. Профиль <code>{evidence.profile_id}</code>, ревизия допуска: {evidence.profile_revision}. Вызов <code>{evidence.invocation_id}</code>. Входной ID <code>{evidence.input_id}</code>. Предобработка: {evidence.preprocessing_revision ? <code>{evidence.preprocessing_revision}</code> : 'не указана'}. Артефакт <code>{evidence.artifact_id}</code>, SHA-256 <code>{evidence.sha256}</code>.</p>{nativeError?.id === evidence.artifact_id ? <p className="error">{nativeError.code === 'integrity' ? 'Целостность артефакта не подтверждена' : 'Не удалось открыть технические данные'} <button type="button" className="secondary" onClick={() => { setNativeResult(null); setNativeError(null); retryNative(value => value + 1) }}>Повторить</button></p> : nativeResult?.id === evidence.artifact_id ? <pre>{nativeResult.text}</pre> : <p>Загружаем технические данные…</p>}</details>}
  </dialog>
}

function ObservationResult({ run, runId, pageHeading }: { run: RunSnapshot; runId: string; pageHeading?: RefObject<HTMLHeadingElement | null> }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const headingRef = pageHeading ?? heading
  const Title = pageHeading ? 'h1' : 'h2'
  const opener = useRef<HTMLButtonElement | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [activeInputId, setActiveInputId] = useState<string | null>(null)
  const [showBoxes, setShowBoxes] = useState(true)
  useEffect(() => {
    if (pageHeading && document.activeElement === document.body) pageHeading.current?.focus()
  }, [pageHeading])
  const projection = run.result_projection
  const inputs = run.inputs ?? []
  const complete = run.state === 'succeeded' && !!projection?.outcome
  const observations = complete ? projection.frames ?? [] : run.observations ?? []
  const frames = makeResultFrames(observations, inputs, complete ? projection.series?.usable_input_ids : undefined, complete)
  const objects = run.objects ?? []
  const outcome = complete ? projection.outcome : null
  const inputOnly = run.purpose === 'comparison_campaign' && !complete && !observations.length && frames.length > 0
  if (!complete && !observations.length && !inputOnly) return null

  const ruleRun = complete && outcome !== 'observations_only'
  const series = projection?.series
  const projectionContext = projection?.context
  const showSeries = complete && (ruleRun || frames.length > 1)
  const supportingIds = complete ? projection.supporting_input_ids ?? [] : []
  const defaultFrame = frames.find(frame => supportingIds.includes(frame.input_id)) ?? frames[0]
  const activeFrame = frames.find(frame => frame.input_id === activeInputId) ?? defaultFrame
  const activeIndex = activeFrame ? frames.findIndex(frame => frame.input_id === activeFrame.input_id) : -1
  const area = series?.declared_observation_area ?? projectionContext?.observation_area ?? run.context?.observation_area ?? 'не указана'
  const period = projectionContext?.period ?? run.context?.period ?? 'не указан'
  const frameName = (inputId: string) => {
    const frame = frames.find(item => item.input_id === inputId)
    return frame ? 'Кадр ' + (frame.ordinal + 1) : inputId
  }
  return <>
    {!pageHeading && <button type="button" className="secondary result-jump" onClick={() => headingRef.current?.focus()}>{complete ? 'Перейти к результату' : inputOnly ? 'Перейти к исходным кадрам' : 'Перейти к частичным наблюдениям'}</button>}
    <section className={'panel result result-' + (outcome ?? 'partial')} aria-labelledby={pageHeading ? 'run-heading' : 'result-heading'}>
      <div className="result-summary">
        <Title ref={headingRef} tabIndex={-1} id={pageHeading ? 'run-heading' : 'result-heading'}>{complete ? OUTCOME_LABELS[outcome ?? ''] ?? 'Результат анализа' : inputOnly ? 'Исходные кадры — анализ не завершён' : 'Частичные наблюдения — анализ не завершён'}</Title>
        {!complete && <p className="result-caution">Анализ не завершён. Показаны только сохранённые к этому моменту данные.</p>}
        {ruleRun && projection?.reason && <p className="result-lead">{projection.reason}</p>}
        {outcome === 'check_requested' && <p className="result-recommendation">{projection?.recommendation || 'Рекомендация не указана в результате.'}</p>}
        {outcome === 'check_requested' && <p>Это рекомендация для проверки, а не подтверждение нарушения.</p>}
      </div>

      <div className="result-layout">
        <section className="result-basis" aria-labelledby="basis-heading">
          <h3 id="basis-heading">Основание вывода</h3>
          <p>Период наблюдения: {period}.</p>
          <p>Заявленная зона наблюдения: {area} (со слов пользователя; по изображениям не подтверждена).</p>
          <section className="observation-rows" aria-labelledby="observations-heading">
            <h4 id="observations-heading">Наблюдения по кадрам</h4>
            {observations.length ? observations.map((item, index) => {
              const input = inputs.find(value => value.input_id === item.input_id)
              const ordinal = complete ? item.ordinal : input?.ordinal ?? item.ordinal
              return <article className="observation-row" key={item.input_id + '-' + item.class_name + '-' + index}>
                <h5>Кадр {ordinal + 1}</h5>
                <p><strong>{CLASS_LABELS[item.class_name] ?? item.class_name}: {OBSERVATION_STATES[item.state] ?? item.state}</strong>{item.reason ? ' — ' + (OBSERVATION_REASONS[item.reason] ?? item.reason) : ''}</p>
              </article>
            }) : <p>{complete ? 'Данные наблюдений в проекции недоступны.' : 'Частичные наблюдения недоступны.'}</p>}
          </section>
          {showSeries && <section className="series-evidence" aria-labelledby="series-heading">
            <h4 id="series-heading">Данные серии</h4>
            {series ? <>
              <p>Пригодных кадров: {series.usable_count}. {series.usable_input_ids?.length ? series.usable_input_ids.map(frameName).join(', ') : 'Подтверждённых кадров нет'}.</p>
              <p>Порядок: {series.input_order?.map(frameName).join(' → ') || 'не указан'}.</p>
              {observations.some(item => item.class_name === 'excavator') && <p>Кадры с экскаватором: {series.excavator_supporting_input_ids?.length ? series.excavator_supporting_input_ids.map(frameName).join(', ') : 'нет подтверждённых'}.</p>}
              {series.dump_truck_persistence_text && <p>{series.dump_truck_persistence_text} Подтверждающие кадры: {series.dump_truck_persistence_input_ids?.map(frameName).join(', ') || 'не указаны'}.</p>}
            </> : <p>Сводные данные серии недоступны для этого анализа.</p>}
          </section>}
          <section className="rule-provenance" aria-labelledby="rule-provenance-heading">
            <h4 id="rule-provenance-heading">Правило и его источник</h4>
            {ruleRun ? <>
              {projection?.rule ? <>
                <p>Правило: {projection.rule.name || 'не указано'}, ревизия {projection.rule.revision || 'не указана'}.</p>
                <p>Источник правила: {projection.rule.provenance || 'не указан'}.</p>
                <p>Ожидание: {projection.rule.expectation || 'не указано'}.</p>
              </> : <p>Данные о правиле в проекции недоступны.</p>}
              <p>{projection?.reason ? 'Результат правила: ' + projection.reason : 'Результат правила в проекции недоступен.'}</p>
              {outcome === 'no_check' && <p>Подтверждающие кадры: {supportingIds.length ? supportingIds.map(frameName).join(', ') : 'не указаны'}.</p>}
            </> : complete ? <p>Правило этапа не проверялось.</p> : <p>Статус правила недоступен: анализ не завершён.</p>}
          </section>
          {ruleRun && <section className="uncertainty" aria-labelledby="uncertainty-heading">
            <h4 id="uncertainty-heading">Неопределённость</h4>
            <p>{projection?.uncertainty || 'Неопределённость не указана в проекции.'}</p>
          </section>}
          {ruleRun && outcome === 'check_requested' && <section className="check-request" aria-labelledby="check-request-heading">
            <h4 id="check-request-heading">Проверка человеком</h4>
            <p>Основание: {projection?.reason || 'не указано'}.</p>
            <p>Подтверждающие кадры: {supportingIds.length ? supportingIds.map(frameName).join(', ') : 'не указаны'}.</p>
            <p>Период: {period}. Заявленная зона: {area} (со слов пользователя).</p>
            <p>Рекомендуемая проверка человеком: {projection?.recommendation || 'не указана'}.</p>
            <p>Это рекомендация для проверки, а не подтверждение нарушения.</p>
          </section>}
        </section>

        <section className="result-visual" aria-labelledby="source-heading">
          <div className="result-visual-heading">
            <h3 id="source-heading">Исходные кадры</h3>
            {objects.length > 0 && <label className="box-toggle"><input type="checkbox" checked={showBoxes} onChange={event => setShowBoxes(event.target.checked)} /> Показывать рамки объектов</label>}
          </div>
          {activeFrame ? <>
            <div className="result-feature-image">
              <SourceImage key={activeFrame.input_id} runId={runId} artifactId={activeFrame.artifact_id} label={'Кадр ' + (activeFrame.ordinal + 1)} description={frameDescription(activeFrame.observations)} objects={objects.filter(item => item.input_id === activeFrame.input_id)} showBoxes={showBoxes} />
            </div>
            <div className="result-frame-caption">
              <div><strong>Кадр {activeFrame.ordinal + 1}</strong><span>Пригодность: {activeFrame.usable === null ? 'не указана' : activeFrame.usable ? 'пригоден' : 'не пригоден'}.</span></div>
              <button type="button" className="secondary" onClick={event => { opener.current = event.currentTarget; setSelected(activeIndex) }}>Открыть кадр {activeFrame.ordinal + 1}</button>
            </div>
            {objects.some(item => item.input_id === activeFrame.input_id) && <ul className="object-list">{objects.filter(item => item.input_id === activeFrame.input_id).map((item, index) => <li key={item.invocation_id + '-' + index}>{CLASS_LABELS[item.class_name] ?? item.class_name} — {Math.round(item.score * 100)}%</li>)}</ul>}
          </> : <p>{complete ? 'Исходные кадры в проекции недоступны.' : 'Исходные кадры недоступны.'}</p>}
          {frames.length > 1 && <div className="source-thumbnails" aria-label="Выбор исходного кадра">{frames.map(frame => <article className="source-thumbnail" key={frame.input_id}>
            <SourceImage runId={runId} artifactId={frame.artifact_id} label={'Кадр ' + (frame.ordinal + 1)} description={frameDescription(frame.observations)} />
            <h4>Кадр {frame.ordinal + 1}</h4>
            {supportingIds.includes(frame.input_id) && <span className="supporting-frame">Поддерживает вывод</span>}
            <button type="button" className="secondary" aria-pressed={activeFrame?.input_id === frame.input_id} onClick={() => setActiveInputId(frame.input_id)}>Выбрать кадр {frame.ordinal + 1}</button>
          </article>)}</div>}
        </section>
      </div>

      <details className="result-details">
        <summary>Подробности анализа и кадров</summary>
        <p>Подтверждающие входные ID: {supportingIds.join(', ') || 'не указаны'}.</p>
        {series && <p>Пригодные входные ID: {series.usable_input_ids?.join(', ') || 'не указаны'}. Порядок: {series.input_order?.join(' → ') || 'не указан'}.</p>}
        <ol>{frames.map(frame => <li key={frame.input_id}>Кадр {frame.ordinal + 1}. Входной ID: <code>{frame.input_id}</code>. Исходный артефакт ID: <code>{frame.artifact_id ?? 'не указан'}</code>. SHA-256: <code>{frame.sha256 ?? 'не указан'}</code>.</li>)}</ol>
      </details>
    </section>
    {selected !== null && <EvidenceViewer runId={runId} frames={frames} native={run.native_evidence_by_frame ?? []} objects={objects} showBoxes={showBoxes} profile={run.profile_snapshot}
      context={projectionContext ?? run.context} selected={selected} onSelect={index => { setSelected(index); setActiveInputId(frames[index].input_id) }}
      onClose={() => { setSelected(null); opener.current?.focus() }} />}
  </>
}


function RunPipeline({ run }: { run: RunSnapshot }) {
  return <details className="panel pipeline pipeline-details" open={run.state !== 'succeeded' || !run.result_projection?.outcome}>
    <summary>Этапы анализа</summary>
    <ol className="pipeline-stages">{run.stages.map(stage => <li key={stage.name} className={'pipeline-stage stage-' + stage.state}>
      <h3>{STAGE_LABELS[stage.name] ?? 'Этап анализа'}</h3>
      <p>{STAGE_STATES[stage.state] ?? 'Состояние доступно на сервере'}</p>
      {stage.reason && <><p className="stage-reason">{STAGE_REASONS[stage.reason] ?? 'Причина не описана для пользователя.'}</p>{!STAGE_REASONS[stage.reason] && <details><summary>Техническая причина</summary><code>{stage.reason}</code></details>}</>}
      {stage.timestamp && <time dateTime={stage.timestamp}>{stage.timestamp}</time>}
    </li>)}</ol>
  </details>
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
  const isJpeg = /\.jpe?g$/i.test(file.name) && (!file.type || file.type === 'image/jpeg')
  const isPng = /\.png$/i.test(file.name) && (!file.type || file.type === 'image/png')
  if (!isJpeg && !isPng) return 'Поддерживаются файлы JPEG (.jpg, .jpeg) и PNG (.png).'
  if (!file.size || file.size > MAX_BYTES) return 'Размер одного файла не должен превышать 16 МБ.'
  try {
    const bytes = new Uint8Array(await readFile(file.slice(0, 8)))
    if (isJpeg ? bytes[0] !== 0xff || bytes[1] !== 0xd8 || bytes[2] !== 0xff
      : bytes.some((value, index) => value !== [137, 80, 78, 71, 13, 10, 26, 10][index])) return 'Файл не удалось прочитать как изображение.'
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
  if (location.pathname === '/readiness') return 'readiness'
  if (location.pathname === '/provider-comparison') return 'provider-comparison'
  if (location.pathname === '/new') return 'new'
  if (location.pathname === '/plan') return 'plan'
  if (location.pathname === '/signals') return 'signals'
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
      <section className="panel" aria-labelledby="about-source"><h2 id="about-source">Источник демонстрации</h2><p>Демонстрационные серии иллюстрируют работу интерфейса. Они взяты из архива организаторов <code>artifacts/dataset/Строительная_техника.zip</code>: группы <code>organizer-archive-site-85-94</code> (файлы Строительная_техника/Screenshot_87.png, Строительная_техника/Screenshot_89.png, Строительная_техника/Screenshot_90.png) и <code>organizer-archive-site-22-26</code> (файлы Строительная_техника/Screenshot_23.png, Строительная_техника/Screenshot_25.png, Строительная_техника/Screenshot_26.png). Порядок кадров соответствует архиву; указанное в примерах время 12:00 условное, а исходная принадлежность кадров конкретной камере и площадке не подтверждена. Для демонстрации PNG-файлы преобразованы в JPEG-копии; загрузка в анализ принимает JPEG и PNG.</p><p>С запуском сохраняются переданные изображения и контекст; полученные наблюдения показываются отдельно. Для итогов «Рекомендована проверка человеком» и «Проверка не запрошена» указываются поддерживающие их кадры, ревизия правила и политика проверки; при одном лишь распознавании или недостатке данных такие кадры не выбираются.</p></section>
      <section className="panel" aria-labelledby="about-limits"><h2 id="about-limits">Границы прототипа</h2><p>Прототип не подключается к потокам камер и не отслеживает график строительства, текущий этап автоматически, тенденции или общее состояние проекта. Результат относится только к переданным изображениям и заявленному контексту.</p></section>
      <aside className="panel about-team" aria-label="Команда проекта"><img src="/team-logo.png" alt="" onError={event => { event.currentTarget.hidden = true }} /><p>Команда: <strong>17 мгновений ИИ</strong></p></aside>
    </div><a className="about-return" href={returnPath} onClick={event => { event.preventDefault(); onReturn() }}>Вернуться назад</a>
  </section>
}

async function siteRequest<T>(path: string, method = 'GET', body?: object): Promise<T> {
  const response = await fetch(`/api${path}`, { method, ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  if (!response.ok) throw new Error((await response.json().catch(() => ({})) as { code?: string }).code ?? 'request_failed')
  return response.json() as Promise<T>
}

function localDateTime(value: string): string {
  const date = new Date(value)
  const minutes = date.getTimezoneOffset()
  return new Date(date.getTime() - minutes * 60_000).toISOString().slice(0, 16)
}

function SiteWorkspace({ heading }: { heading: RefObject<HTMLHeadingElement | null> }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [zones, setZones] = useState<Zone[]>([])
  const [zoneId, setZoneId] = useState('')
  const [works, setWorks] = useState<CatalogWork[]>([])
  const [plan, setPlan] = useState<ZonePlan>({ revision_number: 0, entries: [] })
  const [draft, setDraft] = useState<PlanEntry[]>([])
  const [projectName, setProjectName] = useState('')
  const [zoneName, setZoneName] = useState('')
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Moscow')
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const loadProjects = async () => setProjects((await siteRequest<{ projects: Project[] }>('/projects')).projects)
  const loadZones = async (id: string) => setZones((await siteRequest<{ zones: Zone[] }>(`/projects/${id}/zones`)).zones)
  const loadPlan = async (id: string) => {
    const current = await siteRequest<ZonePlan>(`/zones/${id}/plan`)
    setPlan(current)
    setDraft(current.entries.map(entry => ({ ...entry, starts_at: localDateTime(entry.starts_at), ends_at: localDateTime(entry.ends_at) })))
  }
  useEffect(() => { void Promise.all([loadProjects(), siteRequest<{ works: CatalogWork[] }>('/catalog/works')])
    .then(([, catalog]) => setWorks(catalog.works)).catch(() => setError('Не удалось загрузить проекты или каталог работ.')) }, [])
  useEffect(() => { setZones([]); setZoneId(''); setPlan({ revision_number: 0, entries: [] }); setDraft([])
    if (projectId) void loadZones(projectId).catch(() => setError('Не удалось загрузить зоны.')) }, [projectId])
  useEffect(() => { setPlan({ revision_number: 0, entries: [] }); setDraft([])
    if (zoneId) void loadPlan(zoneId).catch(() => setError('Не удалось загрузить план зоны.')) }, [zoneId])
  async function mutate(action: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('')
    try { await action() } catch (cause) { setError(cause instanceof Error && cause.message === 'plan_revision_conflict'
      ? 'План уже изменён. Сохраните введённые данные отдельно и обновите ревизию.' : 'Операция не выполнена. Проверьте данные и попробуйте снова.') }
    finally { setBusy(false) }
  }
  const addEntry = () => setDraft(current => [...current, { catalog_work_id: works[0]?.id ?? '', starts_at: localPeriod(), ends_at: localPeriod(), state: 'planned', stage_key: null, expected_equipment: [], allowed_equipment: [], excluded_equipment: [] }])
  const changeEntry = (index: number, change: Partial<PlanEntry>) => setDraft(current => current.map((entry, position) => position === index ? { ...entry, ...change } : entry))
  const visibleWorks = works.filter(work => `${work.code ?? ''} ${work.title}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  return <section className="site-workspace" aria-labelledby="site-heading">
    <div className="page-intro"><h1 ref={heading} tabIndex={-1} id="site-heading">Проект и план зоны</h1><p>Работы из исходного каталога можно запланировать параллельно. Каждое сохранение создаёт новую ревизию.</p></div>
    {error && <p className="error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="site-columns"><section className="panel"><h2>Проект и зона</h2>
      <label className="field">Проект<select value={projectId} onChange={event => setProjectId(event.target.value)}><option value="">Выберите проект</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <form onSubmit={event => { event.preventDefault(); void mutate(async () => { const created = await siteRequest<Project>('/projects', 'POST', { name: projectName, timezone }); await loadProjects(); setProjectId(created.id); setProjectName(''); setNotice('Проект создан.') }) }}><div className="field"><label htmlFor="project-name">Новый проект</label><input id="project-name" required maxLength={200} value={projectName} onChange={event => setProjectName(event.target.value)} /></div><div className="field"><label htmlFor="project-timezone">Часовой пояс</label><input id="project-timezone" required value={timezone} onChange={event => setTimezone(event.target.value)} /></div><button type="submit" className="secondary" disabled={busy}>Создать проект</button></form>
      {projectId && <><label className="field">Зона<select value={zoneId} onChange={event => setZoneId(event.target.value)}><option value="">Выберите зону</option>{zones.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><form onSubmit={event => { event.preventDefault(); void mutate(async () => { const created = await siteRequest<Zone>(`/projects/${projectId}/zones`, 'POST', { name: zoneName }); await loadZones(projectId); setZoneId(created.id); setZoneName(''); setNotice('Зона создана.') }) }}><div className="field"><label htmlFor="zone-name">Новая зона</label><input id="zone-name" required maxLength={200} value={zoneName} onChange={event => setZoneName(event.target.value)} /></div><button type="submit" className="secondary" disabled={busy}>Создать зону</button></form></>}
    </section><section className="panel"><h2>Каталог работ</h2><p>Строк в источнике: {works.length}.</p><div className="field"><label htmlFor="catalog-search">Найти работу по коду или названию</label><input id="catalog-search" value={search} onChange={event => setSearch(event.target.value)} /></div><div className="catalog-results"><ol>{visibleWorks.slice(0, 100).map(work => <li key={work.id}><code>{work.code ?? '—'}</code> {work.title} <small>строка {work.source_row}</small></li>)}</ol>{visibleWorks.length > 100 && <p>Показаны первые 100 строк. Уточните поиск.</p>}</div></section></div>
    {zoneId && <section className="panel plan-editor"><h2>План зоны · ревизия {plan.revision_number}</h2><p>Время вводится по часовому поясу этого компьютера и сохраняется с его UTC-смещением. Выбранная ревизия сохранится с анализом.</p><div className="plan-entries">{draft.map((entry, index) => <fieldset key={entry.id ?? index} className="plan-entry"><legend>Работа {index + 1}</legend><div className="field"><label htmlFor={`work-${index}`}>Работа каталога</label><select id={`work-${index}`} value={entry.catalog_work_id} onChange={event => changeEntry(index, { catalog_work_id: event.target.value })}>{works.map(work => <option key={work.id} value={work.id}>{work.code ?? '—'} · {work.title} (строка {work.source_row})</option>)}</select></div><div className="plan-fields"><div className="field"><label htmlFor={`start-${index}`}>Начало</label><input id={`start-${index}`} type="datetime-local" value={entry.starts_at} onChange={event => changeEntry(index, { starts_at: event.target.value })} /></div><div className="field"><label htmlFor={`end-${index}`}>Окончание</label><input id={`end-${index}`} type="datetime-local" value={entry.ends_at} onChange={event => changeEntry(index, { ends_at: event.target.value })} /></div><div className="field"><label htmlFor={`state-${index}`}>Состояние</label><select id={`state-${index}`} value={entry.state} onChange={event => changeEntry(index, { state: event.target.value as PlanEntry['state'] })}><option value="planned">Запланирована</option><option value="active">Активна</option><option value="completed">Завершена</option></select></div><div className="field"><label htmlFor={`stage-${index}`}>Сценарий анализа</label><select id={`stage-${index}`} value={entry.stage_key ?? ''} onChange={event => changeEntry(index, { stage_key: event.target.value || null })}><option value="">Без автоматического сценария</option>{Object.entries(STAGE_NAMES).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></div></div>{(['expected_equipment', 'allowed_equipment', 'excluded_equipment'] as const).map((field, fieldIndex) => <div className="field" key={field}><label htmlFor={`${field}-${index}`}>{['Ожидаемая техника', 'Допустимая техника', 'Явно не предусмотренная техника'][fieldIndex]}</label><select id={`${field}-${index}`} multiple value={entry[field]} onChange={event => changeEntry(index, { [field]: Array.from(event.target.selectedOptions, option => option.value) })}>{EQUIPMENT.map(machine => <option key={machine} value={machine}>{CLASS_LABELS[machine]}</option>)}</select></div>)}<button type="button" className="secondary" onClick={() => setDraft(current => current.filter((_, position) => position !== index))}>Удалить работу</button></fieldset>)}</div><div className="upload-actions"><button type="button" className="secondary" disabled={busy || !works.length} onClick={addEntry}>Добавить работу</button><button type="button" className="primary" disabled={busy} onClick={() => void mutate(async () => { const saved = await siteRequest<{ revision_number: number }>(`/zones/${zoneId}/plan`, 'PUT', { expected_revision: plan.revision_number, entries: draft.map(({ id: _id, starts_at, ends_at, ...rest }) => ({ ...rest, start_at: periodWithOffset(starts_at), end_at: periodWithOffset(ends_at) })) }); await loadPlan(zoneId); setNotice(`Сохранена ревизия ${saved.revision_number}.`) })}>Сохранить новую ревизию</button><button type="button" className="secondary" disabled={busy} onClick={() => void mutate(() => loadPlan(zoneId))}>Обновить с сервера</button></div></section>}
  </section>
}

function StageConfirmation({ run, runId }: { run: RunSnapshot; runId: string }) {
  const [stage, setStage] = useState(run.result_projection?.stage_hypotheses?.[0]?.stage ?? '')
  const [comment, setComment] = useState('')
  const [confirmed, setConfirmed] = useState(run.stage_confirmation)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { if (run.stage_confirmation) setConfirmed(run.stage_confirmation) }, [run.stage_confirmation?.stage])
  useEffect(() => { if (!stage && run.result_projection?.stage_hypotheses?.[0]?.stage) setStage(run.result_projection.stage_hypotheses[0].stage) }, [run.result_projection?.stage_hypotheses])
  if (run.state !== 'succeeded' || run.purpose === 'comparison_campaign') return null
  const hypotheses = run.result_projection?.stage_hypotheses ?? []
  return <section className="panel stage-confirmation" aria-labelledby="hypotheses-heading"><h2 id="hypotheses-heading">Гипотезы этапа</h2>{hypotheses.length ? <ul>{hypotheses.map(item => <li key={item.stage}>{STAGE_NAMES[item.stage] ?? item.stage}: {CLASS_LABELS[item.equipment] ?? item.equipment}, признаки сцены {item.scene_features.join(', ')}</li>)}</ul> : <p>По этим кадрам этап определить не удалось.</p>}{confirmed ? <p>Человек подтвердил этап «{STAGE_NAMES[confirmed.stage] ?? confirmed.stage}». {confirmed.comment}</p> : <><p>Подтвердите или исправьте этап. Подтверждение не меняет план автоматически.</p><div className="field"><label htmlFor="confirmed-stage">Этап</label><select id="confirmed-stage" value={stage} onChange={event => setStage(event.target.value)}><option value="">Выберите этап</option>{Object.entries(STAGE_NAMES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><div className="field"><label htmlFor="stage-comment">Комментарий</label><textarea id="stage-comment" maxLength={2000} value={comment} onChange={event => setComment(event.target.value)} /></div><button type="button" className="secondary" disabled={!stage || busy} onClick={() => { setBusy(true); setError(''); void siteRequest<{ stage: string; comment: string }>(`/runs/${runId}/confirm-stage`, 'POST', { stage, comment }).then(setConfirmed).catch(() => setError('Не удалось сохранить подтверждение этапа.')).finally(() => setBusy(false)) }}>Подтвердить этап</button>{error && <p className="error" role="alert">{error}</p>}</>}</section>
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
  const [captureTimes, setCaptureTimes] = useState<Record<string, string>>({})
  const [analysisProjects, setAnalysisProjects] = useState<Project[]>([])
  const [planPickerOpen, setPlanPickerOpen] = useState(false)
  const [analysisProjectId, setAnalysisProjectId] = useState('')
  const [analysisZones, setAnalysisZones] = useState<Zone[]>([])
  const [analysisZoneId, setAnalysisZoneId] = useState('')
  const [analysisPlan, setAnalysisPlan] = useState<ZonePlan | null>(null)
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
  const [runSnapshotRoute, setRunSnapshotRoute] = useState<string | null>(null)
  const visibleRunSnapshot = runSnapshotRoute === route ? runSnapshot : null
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
    const pop = () => { closeCamera(); routeRef.current = runIdFromPath(); focusAfterNavigation.current = true; setRunSnapshot(null); setRunChecked(false); setRunMissing(false); setRoute(routeRef.current) }
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
    if (route !== 'new' || !planPickerOpen) return
    let active = true
    void siteRequest<{ projects: Project[] }>('/projects').then(data => { if (active && Array.isArray(data.projects)) setAnalysisProjects(data.projects) }).catch(() => {})
    return () => { active = false }
  }, [route, planPickerOpen])
  useEffect(() => {
    setAnalysisZones([]); setAnalysisZoneId(''); setAnalysisPlan(null)
    if (!analysisProjectId) return
    let active = true
    void siteRequest<{ zones: Zone[] }>(`/projects/${analysisProjectId}/zones`).then(data => { if (active && Array.isArray(data.zones)) setAnalysisZones(data.zones) }).catch(() => {})
    return () => { active = false }
  }, [analysisProjectId])
  useEffect(() => {
    setAnalysisPlan(null)
    if (!analysisZoneId) return
    const chosenZone = analysisZones.find(zone => zone.id === analysisZoneId)
    if (chosenZone) setArea(chosenZone.name)
    let active = true
    void siteRequest<ZonePlan>(`/zones/${analysisZoneId}/plan`).then(data => { if (active && data.revision_id) setAnalysisPlan(data) }).catch(() => {})
    return () => { active = false }
  }, [analysisZoneId, analysisZones])

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
    setRunSnapshotRoute(null)
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
    if (!route || route === 'about' || route === 'readiness' || route === 'provider-comparison' || route === 'history' || route === 'new' || route === 'stages' || route === 'plan' || route === 'signals') return
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
        if (!active || routeRef.current !== route) return
        if (response.status === 404) {
          if (announcedStages.current === null) setRunMissing(true)
          else setRunError('Не удалось получить актуальный статус. Повторите проверку.')
          setRunChecked(true)
          return
        }
        if (!response.ok) throw new Error()
        const data = await response.json() as RunSnapshot
        if (!active || routeRef.current !== route) return
        if (data.run_id && data.run_id !== route) {
          setRunError('Получены данные другого анализа. Повторите проверку.')
          setRunChecked(true)
          return
        }
        setRunSnapshot(data)
        setRunSnapshotRoute(route)
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
        if (active && routeRef.current === route) { setRunError('Связь потеряна. Анализ может продолжаться на сервере.'); setRunChecked(true) }
      } finally {
        clearTimeout(timeout)
        if (active && routeRef.current === route) setRunReading(false)
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
    if (!route || route === 'about' || route === 'readiness' || route === 'provider-comparison' || route === 'history' || route === 'new' || route === 'stages' || route === 'plan' || route === 'signals' || retrying) return
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
    document.title = route === 'about' ? 'О проекте — Контроль строительства' : route === 'provider-comparison' ? 'Сравнение провайдеров — Контроль строительства' : route === 'readiness' ? 'Готовность — Контроль строительства' : route === 'history' ? 'История анализов — Контроль строительства' : route === 'stages' ? 'Этапы — Контроль строительства' : route === 'plan' ? 'План — Контроль строительства' : route === 'signals' ? 'Сигналы — Контроль строительства' : route === 'new' ? 'Новый анализ — Контроль строительства' : route ? 'Анализ — Контроль строительства' : 'Страница не найдена — Контроль строительства'
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
    setRunSnapshot(null)
    setRunChecked(false)
    setRunMissing(false)
    setRoute(routeRef.current)
    setRunError('')
  }

  function returnFromAbout() {
    if (history.state?.aboutFromApp) { history.back(); return }
    history.replaceState({}, '', '/')
    routeRef.current = runIdFromPath()
    focusAfterNavigation.current = true
    setRunSnapshot(null)
    setRunChecked(false)
    setRunMissing(false)
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
    if (!framesRef.current.length) next.images = 'Добавьте хотя бы один кадр JPEG или PNG.'
    if (planPickerOpen && (!analysisProjectId || !analysisZoneId || !analysisPlan?.revision_id)) next.submit = 'Выберите проект и зону с сохранённой ревизией плана либо отмените привязку.'
    if (analysisPlan?.revision_id && framesRef.current.some(frame => !validLocalPeriod(captureTimes[frame.id] ?? period))) next.images = 'Укажите существующее время съёмки для каждого кадра.'
    if (intent === 'rule_evaluation' && framesRef.current.some(frame => /\.png$/i.test(frame.file.name))) next.images = 'Текущее правило принимает JPEG. Для PNG выберите «Только распознать технику».'
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
        period: periodWithOffset(period), requested_classes: intent === 'rule_evaluation' ? ['excavator', 'dump_truck'] : EQUIPMENT,
        ...(analysisProjectId && analysisPlan?.revision_id ? { project_id: analysisProjectId, zone_id: analysisZoneId,
          plan_revision_id: analysisPlan.revision_id,
          capture_times: framesRef.current.map(frame => periodWithOffset(captureTimes[frame.id] ?? period)) } : {}),
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
    <AppHeader route={route} historyPath={historyPath.current} navigate={navigate} onNewAnalysis={newAnalysis} />
    <main id="main" className="page">
      {route === 'plan' ? <SiteWorkspace heading={pageHeading} /> : route === 'signals' ? <SignalsPage heading={pageHeading} onOpenRun={id => navigate(`/runs/${id}`)} /> : route === 'stages' ? <section aria-labelledby="stages-heading"><div className="page-intro"><p className="eyebrow">Обзор этапов</p><h1 ref={pageHeading} tabIndex={-1} id="stages-heading">Этапы строительства</h1><p>Здесь показаны результаты завершённых анализов, привязанных к этапу. График и состояние проекта не оцениваются.</p></div>{stageError && <div className="error" role="alert"><p>{stageError}</p><button type="button" className="secondary" onClick={() => setStageAttempt(value => value + 1)}>Повторить загрузку</button></div>}<div className="stages-layout"><section className="panel" aria-labelledby="stage-map-heading" aria-busy={stageLoading}><h2 id="stage-map-heading">Карта этапов</h2>{stageLoading && !stageSummaries && <p role="status">Загружаем этапы…</p>}<div className="stage-tiles">{stageSummaries?.map(stage => <button key={stage.stage_id} className="stage-tile" type="button" aria-pressed={selectedStage === stage.stage_id} aria-controls="stage-inspector" onClick={() => setSelectedStage(stage.stage_id)}><strong>{stage.name}</strong><span>{stage.supported ? stage.latest_result ? OUTCOME_LABELS[stage.latest_result.projection.outcome] ?? 'Результат доступен' : 'Анализов нет' : 'Не настроено в прототипе'}</span>{stage.latest_lifecycle && <small>{stage.latest_result ? 'Более новый запуск' : 'Последняя попытка'}: {RUN_STATES[stage.latest_lifecycle.state] ?? 'Состояние неизвестно'}</small>}</button>)}</div><p className="hint">В прототипе настроен анализ земляных работ котлована. Другие этапы показаны для навигации.</p><button type="button" className="secondary" disabled={stageLoading} onClick={() => setStageAttempt(value => value + 1)}>{stageLoading ? 'Обновляем…' : 'Обновить этапы'}</button></section><section className="panel stage-inspector" id="stage-inspector" aria-labelledby="inspector-heading">{(() => { const stage = stageSummaries?.find(item => item.stage_id === selectedStage); if (!stage) return <p>Выберите этап.</p>; return <><p className="eyebrow">Выбранный этап</p><h2 id="inspector-heading">{stage.name}</h2><p className="stage-outcome">{stage.supported ? stage.latest_result ? OUTCOME_LABELS[stage.latest_result.projection.outcome] ?? 'Результат доступен' : 'Анализов нет' : 'Не настроено в прототипе'}</p>{stage.supported ? <>{stage.latest_result ? <p>Результат последнего завершённого анализа с сохранёнными доказательствами. {stage.latest_result.created_at && <>Время запуска: <time dateTime={stage.latest_result.created_at}>{stage.latest_result.created_at}</time>. </>}<a href={`/runs/${stage.latest_result.run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${stage.latest_result!.run_id}`) }}>Открыть доказательства</a></p> : <p>Для этого этапа ещё нет завершённого анализа с результатом.</p>}{stage.latest_lifecycle && <p className="attention">{stage.latest_result ? 'Более новый запуск' : 'Последняя попытка'}: {RUN_STATES[stage.latest_lifecycle.state] ?? 'Состояние неизвестно'}. {stage.latest_lifecycle.created_at && <>Время запуска: <time dateTime={stage.latest_lifecycle.created_at}>{stage.latest_lifecycle.created_at}</time>. </>}<a href={`/runs/${stage.latest_lifecycle.run_id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${stage.latest_lifecycle!.run_id}`) }}>Открыть запуск</a>. {stage.latest_result && 'Он не заменяет завершённый результат.'}</p>}</> : <p>Для этого этапа правило не настроено в прототипе. Анализ доступен для этапа «Земляные работы котлована».</p>}</> })()}</section></div></section> : route === 'history' ? <section className="history" aria-labelledby="history-heading" aria-busy={historyLoading || historyPageLoading}>
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
      </section> : route === 'readiness' ? <ReadinessPage heading={pageHeading} onOpen={navigate} /> : route === 'provider-comparison' ? <ProviderComparisonPage heading={pageHeading} onOpen={navigate} /> : route === 'about' ? <About heading={pageHeading} returnPath={history.state?.aboutFromApp ? history.state.returnPath : '/'} onReturn={returnFromAbout} /> : route === null ? <section className="panel" aria-labelledby="not-found-heading"><h1 ref={pageHeading} tabIndex={-1} id="not-found-heading">Страница не найдена</h1><p>Проверьте адрес или откройте обзор этапов.</p></section> : route !== 'new' ? <section className="run-workspace" aria-labelledby="run-heading" aria-busy={runReading}>{visibleRunSnapshot?.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome && <ObservationResult run={visibleRunSnapshot} runId={route!} pageHeading={pageHeading} />}<div className="panel run-header"><details className="run-meta" open={visibleRunSnapshot?.state !== 'succeeded' || !visibleRunSnapshot?.result_projection?.outcome || !!runError}><summary>{visibleRunSnapshot?.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome ? 'Подробности анализа' : 'Данные анализа'}</summary><p className="eyebrow">{visibleRunSnapshot?.purpose === "comparison_campaign" ? "Доказательство сравнительной кампании" : "Анализ"}</p>{visibleRunSnapshot?.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome ? <h2 id="run-status-heading">Анализ завершён</h2> : <h1 ref={pageHeading} tabIndex={-1} id="run-heading">{runMissing ? 'Анализ не найден' : visibleRunSnapshot ? RUN_HEADINGS[visibleRunSnapshot.state] ?? 'Статус анализа неизвестен' : runChecked ? 'Статус анализа неизвестен' : 'Проверяем анализ…'}</h1>}<p>Номер анализа: <code>{route}</code></p>{(visibleRunSnapshot?.stage ?? visibleRunSnapshot?.context?.stage_id) === 'excavation' && <p>Этап строительства: <strong>Земляные работы котлована</strong></p>}{visibleRunSnapshot && <p>Состояние сервера: <strong>{RUN_STATES[visibleRunSnapshot.state] ?? 'Состояние доступно на сервере'}</strong></p>}{runError && <div className="attention"><p>{runError}</p><button type="button" className="secondary" disabled={runReading} onClick={() => { if (!runReading) { setRunReading(true); setRunReadAttempt(value => value + 1) } }}>{runReading ? 'Проверяем статус…' : 'Проверить статус'}</button></div>}<p role="status" className="sr-only">{runError || runAnnouncement}</p>{(visibleRunSnapshot?.retry_predecessor_id ?? visibleRunSnapshot?.retry_of_run_id) && <p>Повтор анализа <a href={`/runs/${(visibleRunSnapshot.retry_predecessor_id ?? visibleRunSnapshot.retry_of_run_id)}`} onClick={event => { event.preventDefault(); navigate(`/runs/${(visibleRunSnapshot.retry_predecessor_id ?? visibleRunSnapshot.retry_of_run_id)}`) }}>{(visibleRunSnapshot.retry_predecessor_id ?? visibleRunSnapshot.retry_of_run_id)}</a></p>}{(visibleRunSnapshot?.retry_successor_id ?? visibleRunSnapshot?.successor_run_id) && <p>Следующий анализ <a href={`/runs/${(visibleRunSnapshot.retry_successor_id ?? visibleRunSnapshot.successor_run_id)}`} onClick={event => { event.preventDefault(); navigate(`/runs/${(visibleRunSnapshot.retry_successor_id ?? visibleRunSnapshot.successor_run_id)}`) }}>{(visibleRunSnapshot.retry_successor_id ?? visibleRunSnapshot.successor_run_id)}</a></p>}{visibleRunSnapshot?.retry_eligible && <p>Повтор использует текущий профиль <code>{visibleRunSnapshot.retry_profile_id}</code>, ревизия допуска {visibleRunSnapshot.retry_authorization_revision}.{visibleRunSnapshot.profile_id !== visibleRunSnapshot.retry_profile_id && <> Исходный анализ использовал профиль <code>{visibleRunSnapshot.profile_id}</code>.</>}</p>}{visibleRunSnapshot?.retry_eligible && <button type="button" className="primary" disabled={retrying || offline} onClick={() => void retryRun()}>{retrying ? 'Создаём повтор…' : 'Повторить анализ'}</button>}{retryError && <p className="error" role="alert">{retryError}</p>}</details></div>{visibleRunSnapshot && !(visibleRunSnapshot.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome) && <ObservationResult run={visibleRunSnapshot} runId={route!} />}{visibleRunSnapshot && <RunPipeline run={visibleRunSnapshot} />}{visibleRunSnapshot?.plan_binding && <details className="panel run-plan-binding"><summary>Привязка к плану</summary><p>Зона <code>{visibleRunSnapshot.plan_binding.zone_id}</code>, ревизия <code>{visibleRunSnapshot.plan_binding.revision_id}</code>. Время кадров: {visibleRunSnapshot.plan_binding.capture_times.join(', ')}.</p></details>}{visibleRunSnapshot && <StageConfirmation key={route} run={visibleRunSnapshot} runId={route!} />}</section> : <NewAnalysisPage>
        <div className="page-intro new-analysis-intro"><h1 ref={pageHeading} tabIndex={-1}>Новый анализ</h1><p>Подготовьте наблюдение за техникой: выберите цель, укажите контекст и добавьте кадры в порядке съёмки. Привязка сохранится в анализе и его повторе.</p>{unsupportedStageNotice && <p className="attention">Выбранный этап не настроен в прототипе. Выберите доступный этап и цель анализа.</p>}</div>
        <details className="demo-examples panel" aria-busy={demoLoading}>
          <summary id="demo-heading">Включённые примеры</summary>
          <p>Загрузите три кадра в редактируемую форму. Это примеры разработки из архива организаторов, не оценка готовности распознавания.</p>
          <div className="upload-actions">{demoCases.cases.map(item => <button key={item.id} type="button" className="secondary" disabled={!!pending || recovering || sending || validating || demoLoading || choicesLoading} onClick={() => void loadDemo(item.id)}>{item.label}</button>)}</div>
          {demoLoading && <p role="status">Загружаем и проверяем кадры примера…</p>}
          {demoError && <p role="alert" className="error">{demoError}</p>}
          {pending && <p>Пока предыдущая отправка требует восстановления, загрузка примера недоступна. Сохранённые данные и ключ отправки не изменены.</p>}
          {selectedDemo && <div className="rule-context"><p>Источник: архив организаторов, группа <code>{selectedDemo.sourceGroup}</code>; порядок кадров соответствует архиву.</p><p>Отмеченная на кадрах дата: {selectedDemo.frames.map(frame => frame.displayedDate ?? 'не указана').join(', ')}. В исходном примере время 12:00 условное; проверьте период перед отправкой.</p><p>Зона наблюдения заявлена для этой серии; изображения не подтверждают её границы или отсутствие техники на всей площадке.</p></div>}
        </details>
        <form className="new-analysis-form" onSubmit={submit} noValidate aria-busy={sending}>
          <div className="form-grid"><section className="panel" aria-labelledby="context-heading"><h2 id="context-heading">Контекст наблюдения</h2><fieldset disabled={!!pending || sending || validating || choicesLoading || demoLoading}><div className="field"><label htmlFor="stage">Этап</label><select id="stage" value={stage} onChange={event => { const selected = event.target.value; setStage(selected); setIntent(choices.find(item => item.id === selected)?.rule && !observationPreferred.current ? 'rule_evaluation' : 'observation_only') }}>{choices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}</select></div><fieldset className="intent-selector"><legend>Цель анализа</legend><label><input type="radio" name="intent" value="rule_evaluation" checked={intent === 'rule_evaluation'} disabled={!choices.find(item => item.id === stage)?.rule} onChange={() => { observationPreferred.current = false; setIntent('rule_evaluation') }} /> Проверить правило этапа</label><label><input type="radio" name="intent" value="observation_only" checked={intent === 'observation_only'} onChange={() => { observationPreferred.current = true; setIntent('observation_only') }} /> Только распознать технику</label></fieldset>{choices.length > 0 && !choices.find(item => item.id === stage)?.rule && <p className="hint">Для этого этапа правило не настроено в прототипе</p>}{!choicesLoading && !choices.length && <p className="error">Не удалось загрузить настройки этапов. <button type="button" className="secondary" onClick={() => setChoicesAttempt(value => value + 1)}>Повторить загрузку настроек</button></p>}<div className="field"><label htmlFor="scenario">Сценарий</label><input id="scenario" value={scenario} onChange={event => setScenario(event.target.value)} aria-invalid={!!errors.scenario} aria-describedby={errors.scenario ? 'scenario-error' : undefined} maxLength={256} /><p className="hint">Например, наблюдение за земляными работами.</p>{errors.scenario && <p id="scenario-error" className="error">{errors.scenario}</p>}</div><div className="field"><label htmlFor="area">Зона наблюдения</label><input id="area" value={area} readOnly={!!analysisZoneId} onChange={event => setArea(event.target.value)} aria-invalid={!!errors.observation_area} aria-describedby={errors.observation_area ? 'area-error' : undefined} maxLength={256} /><p className="hint">{analysisZoneId ? 'Используется название выбранной зоны плана.' : 'Укажите конкретный участок, к которому относятся кадры.'}</p>{errors.observation_area && <p id="area-error" className="error">{errors.observation_area}</p>}</div><div className="field"><label htmlFor="period">Дата и время наблюдения</label><input id="period" type="datetime-local" value={period} onChange={event => setPeriod(event.target.value)} aria-invalid={!!errors.period} aria-describedby={errors.period ? 'period-error' : undefined} />{errors.period && <p id="period-error" className="error">{errors.period}</p>}</div>{!planPickerOpen ? <button type="button" className="secondary" onClick={() => setPlanPickerOpen(true)}>Привязать к плану</button> : <><div className="field"><label htmlFor="analysis-project">Проект плана</label><select id="analysis-project" value={analysisProjectId} onChange={event => setAnalysisProjectId(event.target.value)}><option value="">Без привязки к плану</option>{analysisProjects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>{analysisProjectId && <div className="field"><label htmlFor="analysis-zone">Зона плана</label><select id="analysis-zone" value={analysisZoneId} onChange={event => setAnalysisZoneId(event.target.value)}><option value="">Выберите зону</option>{analysisZones.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>}{analysisZoneId && <p>Ревизия плана: {analysisPlan?.revision_number ?? 'не создана'}. {analysisPlan?.revision_id && <code>{analysisPlan.revision_id}</code>}</p>}<button type="button" className="secondary" onClick={() => { setPlanPickerOpen(false); setAnalysisProjectId('') }}>Без привязки к плану</button></>}</fieldset><p className="context-summary">Зона: {area || 'не указана'}. Период: {period || 'не указан'}.</p></section>
          <section className="panel" aria-labelledby="images-heading"><h2 id="images-heading">Кадры наблюдения</h2><p className="muted">Выберите одно изображение JPEG или PNG либо серию из 2–8 изображений. Каждый файл — до 16 МБ и 40 миллионов пикселей. Порядок кадров влияет на анализ.</p>{intent === 'rule_evaluation' && frames.length > 0 && frames.length < 3 && <p className="attention">Для проверки правила нужны минимум три пригодных кадра одной зоны. Можно отправить меньше; достаточность определит сервер после анализа.</p>}<UploadZone onFiles={files => void addFiles(files)} onCamera={() => void openCamera()} disabled={!!pending || sending || validating || demoLoading} cameraDisabled={!!pending || sending || validating || demoLoading || cameraOpen || cameraDenied} invalid={!!errors.images} describedBy={errors.images ? 'images-error' : undefined} />{errors.images && <p id="images-error" className="error" role="alert">{errors.images}</p>}{cameraOpen && <div className="camera"><video ref={cameraVideo} autoPlay playsInline muted aria-label="Изображение с камеры" /><div className="upload-actions"><button type="button" onClick={capture}>Сделать снимок</button><button className="secondary" type="button" onClick={closeCamera}>Закрыть камеру</button></div></div>}
          <h3>Порядок кадров</h3>{frames.length ? <ol className="manifest">{frames.map((frame, index) => <li key={frame.id} className="frame"><FramePreview file={frame.file} ordinal={index + 1} /><div><strong>Кадр {index + 1}</strong><span className="file-name">{frame.file.name}</span><small>{(frame.file.size / 1_000_000).toFixed(1)} МБ</small>{analysisPlan?.revision_id && <label>Время съёмки<input type="datetime-local" value={captureTimes[frame.id] ?? period} onChange={event => setCaptureTimes(current => ({ ...current, [frame.id]: event.target.value }))} /></label>}</div><div className="frame-actions"><button type="button" className="secondary" onClick={() => move(index, -1)} disabled={index === 0 || !!pending || sending || validating || demoLoading} aria-label={`Выше: ${frame.file.name}, кадр ${index + 1}`}>Выше</button><button type="button" className="secondary" onClick={() => move(index, 1)} disabled={index === frames.length - 1 || !!pending || sending || validating || demoLoading} aria-label={`Ниже: ${frame.file.name}, кадр ${index + 1}`}>Ниже</button><button type="button" className="secondary" onClick={() => remove(index)} disabled={!!pending || sending || validating || demoLoading} aria-label={`Удалить: ${frame.file.name}, кадр ${index + 1}`}>Удалить</button></div></li>)}</ol> : <p className="empty">Кадры ещё не выбраны.</p>}{removed && <div className="undo"><span>{removed.frame.file.name} удалён.</span><button className="secondary" type="button" onClick={restore} disabled={!!pending || sending || validating || demoLoading || frames.length >= MAX_FRAMES}>Вернуть</button></div>}<p role="status" className="sr-only">{notice}</p></section></div>
          <section className="submit-panel"><div ref={summary} tabIndex={-1} className="error-summary" role={Object.values(errors).some(Boolean) ? 'alert' : undefined}>{Object.values(errors).some(Boolean) && <><strong>Проверьте данные</strong><ul>{Object.entries(errors).filter(([, message]) => message).map(([key, message]) => <li key={key}><a href={`#${key === 'observation_area' ? 'area' : key === 'images' ? 'images-heading' : key === 'submit' ? 'submit-action' : key}`}>{message}</a></li>)}</ul></>}</div>{offline && <p className="offline" role="status">Нет соединения. Изображения останутся на этом устройстве до обновления страницы.</p>}{pending && <p className="attention">Результат предыдущей отправки неизвестен. Повторный запрос использует те же данные и ключ.</p>}<button id="submit-action" className="primary" type="submit" disabled={sending || offline || recovering || demoLoading || (!pending && (choicesLoading || !choices.length))}>{sending ? 'Создаём анализ…' : pending ? 'Повторить отправку' : 'Запустить анализ'}</button></section>
        </form>
      </NewAnalysisPage>}
    </main>
  </div>
}
