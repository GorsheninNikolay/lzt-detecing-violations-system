import { SourceImage, EvidenceViewer, makeResultFrames, frameDescription, type Input, type Observation, type NativeEvidence, type DetectedObject, type ProfileSnapshot } from './EvidenceViewer'
import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react'
import demoCases from './demoCases.json'
import AppHeader from './AppHeader'
import PublicSupport from './PublicSupport'
import { attributionHeaders } from './engagement'
import FramePreview from './FramePreview'
import NewAnalysisPage, { UploadZone } from './NewAnalysisPage'
import ReadinessPage from './ReadinessPage'
import ProviderComparisonPage from './ProviderComparisonPage'
import SignalsPage from './SignalsPage'
import './result.css'
import { AnnotationEditor } from './Annotations'
import { AiAssessmentPanel, type AiAssessment, type AiEvidence } from './AiAssessment'

type Frame = { id: string; file: File }
type DemoCase = (typeof demoCases.cases)[number]
type Pending = { endpoint: string; body: string; key: string }
type Errors = Partial<Record<'scenario' | 'observation_area' | 'period' | 'images' | 'submit', string>>
type Stage = { name: string; state: string; reason?: string | null; timestamp?: string | null }
type Series = { usable_count: number; usable_input_ids: string[]; declared_observation_area: string | null; input_order: string[]; excavator_supporting_input_ids: string[]; dump_truck_persistence_input_ids: string[]; dump_truck_persistence_text: string | null }
type Rule = { name: string; revision: string; expectation: string; provenance: string; recommendation: string | null }
type Choice = { id: string; label: string; rule: Rule | null }
type ResultProjection = { outcome: string; frames?: Observation[]; context?: { period?: string; observation_area?: string; stage_id?: string; project_id?: string; zone_id?: string; capture_times?: string[] }; series?: Series; reason?: string | null; uncertainty?: string | null; recommendation?: string | null; rule?: Rule | null; supporting_input_ids?: string[] | null; stage_hypotheses?: { stage: string; equipment: string; scene_features: string[] }[] }
type RunSnapshot = { ai_assessment?: AiAssessment | null; ai_evidence?: AiEvidence[]; planned_works?: { title: string; stage_key: string | null; starts_at: string; ends_at: string; state: string }[]; project_id?: string | null; zone_id?: string | null; run_id?: string; purpose?: string; state: string; stages: Stage[]; context?: { period?: string; observation_area?: string; stage_id?: string; project_id?: string; zone_id?: string; capture_times?: string[] }; intent?: string; stage?: string | null; profile_snapshot?: ProfileSnapshot; rule_snapshot?: Rule | null; requested_classes?: string[]; inputs?: Input[]; observations?: Observation[]; objects?: DetectedObject[]; native_evidence_by_frame?: NativeEvidence[]; outcome?: string | null; result_projection?: ResultProjection | null; plan_binding?: { zone_id: string; revision_id: string; capture_times: string[] } | null; stage_confirmation?: { stage: string; comment: string; created_at?: string } | null; retry_predecessor_id?: string | null; retry_successor_id?: string | null; retry_of_run_id?: string | null; successor_run_id?: string | null; retry_eligible?: boolean; retry_profile_id?: string; retry_authorization_revision?: number; profile_id?: string; authorization_revision?: number; created_at?: string }

type HistoryRun = { project_id?: string | null; id: string; run_id: string; created_at: string | null; stage: string | null; intent: string; state: string; outcome: string | null; retry_predecessor_id: string | null; retry_successor_id: string | null; retry_of_run_id?: string | null; successor_run_id?: string | null }
const OUTCOME_LABELS: Record<string, string> = { observations_only: 'Только наблюдения', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось', no_check: 'Проверка не запрошена', check_requested: 'Рекомендована проверка человеком' }

const CLASS_LABELS: Record<string, string> = { excavator: 'Экскаватор', dump_truck: 'Самосвал', road_roller: 'Каток', truck_mounted_crane: 'Кран-манипулятор', concrete_mixer_truck: 'Автобетоносмеситель', bulldozer: 'Бульдозер', truck: 'Грузовик', mobile_crane: 'Автокран' }
const EQUIPMENT = Object.keys(CLASS_LABELS)
const PLAN_STAGES = ['excavation', 'concreting', 'roadwork']
const STAGE_NAMES: Record<string, string> = { unknown: 'Не определён', ambiguous: 'Неоднозначный этап', preparation: 'Подготовительные работы', demolition: 'Демонтаж', excavation: 'Земляные работы', concreting: 'Бетонные работы', installation: 'Монтаж', roadwork: 'Дорожные работы', utilities: 'Инженерные сети', landscaping: 'Благоустройство' }
type Project = { id: string; name: string; timezone: string }
type Zone = { id: string; name: string }
type CatalogWork = { id: string; source_row: number; code: string | null; title: string }
type PlanEntry = { id?: string; catalog_work_id: string; starts_at: string; ends_at: string; state: 'planned' | 'active' | 'completed'; stage_key: string | null; expected_equipment: string[]; allowed_equipment: string[]; excluded_equipment: string[] }
type ZonePlan = { revision_id?: string; revision_number: number; entries: PlanEntry[] }
const OBSERVATION_STATES: Record<string, string> = { detected: 'Обнаружен', not_detected_in_frame: 'Не обнаружен в кадре', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось' }
const OBSERVATION_REASONS: Record<string, string> = { frame_unassessable: 'Кадр непригоден для распознавания.', unsupported_class: 'Класс не поддерживается профилем распознавания.', observer_unavailable: 'Распознавание недоступно.' }

function ObservationResult({ run, runId, pageHeading, onOpen }: { run: RunSnapshot; runId: string; pageHeading?: RefObject<HTMLHeadingElement | null>; onOpen?: (path: string) => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const headingRef = pageHeading ?? heading
  const Title = pageHeading ? 'h1' : 'h2'
  const opener = useRef<HTMLButtonElement | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [activeInputId, setActiveInputId] = useState<string | null>(null)
  const [showBoxes, setShowBoxes] = useState(true)
  const [selectedObject, setSelectedObject] = useState<number | null>(null)
  const [editing, setEditing] = useState(false)
  const correction = useRef<HTMLDetailsElement>(null)
  useEffect(() => {
    if (pageHeading && document.activeElement === document.body) pageHeading.current?.focus()
  }, [pageHeading])
  const projection = run.result_projection
  const inputs = run.inputs ?? []
  const complete = run.state === 'succeeded' && !!projection?.outcome
  const observations = [...(complete ? projection.frames ?? [] : run.observations ?? [])].sort((a, b) => Number(b.state === 'detected') - Number(a.state === 'detected'))
  const frames = makeResultFrames(observations, inputs, complete ? projection.series?.usable_input_ids : undefined, complete)
  const objects = run.objects ?? []
  const outcome = complete ? projection.outcome : null
  const inputOnly = !complete && !observations.length && frames.length > 0 && (run.purpose === 'comparison_campaign' || !!run.ai_evidence?.length)
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
        <section className={`result-visual ${editing?'is-editing':''}`} aria-labelledby="source-heading">
          <div className="result-visual-heading">
            <h3 id="source-heading">Исходные кадры</h3>
            {objects.length > 0 && <label className="box-toggle"><input type="checkbox" checked={showBoxes} onChange={event => setShowBoxes(event.target.checked)} /> Показывать рамки объектов</label>}
          </div>
          {activeFrame ? <>
            <div className="result-feature-image">
              <SourceImage key={activeFrame.input_id} runId={runId} artifactId={activeFrame.artifact_id} label={'Кадр ' + (activeFrame.ordinal + 1)} description={frameDescription(activeFrame.observations)} objects={objects.filter(item => item.input_id === activeFrame.input_id)} showBoxes={showBoxes} selectedObject={selectedObject} onSelectObject={setSelectedObject} />
            </div>
            <div className="result-frame-caption">
              {run.context?.capture_times?.[activeFrame.ordinal] && <p>Время съёмки: <time dateTime={run.context.capture_times[activeFrame.ordinal]}>{new Date(run.context.capture_times[activeFrame.ordinal]).toLocaleString('ru-RU')}</time></p>}
              <div><strong>Кадр {activeFrame.ordinal + 1}</strong><span>Пригодность: {activeFrame.usable === null ? 'не указана' : activeFrame.usable ? 'пригоден' : 'не пригоден'}.</span></div>
              <button type="button" className="secondary" onClick={event => { opener.current = event.currentTarget; setSelected(activeIndex) }}>Открыть кадр {activeFrame.ordinal + 1}</button>
            </div>
            <ol className="object-list">{objects.filter(item => item.input_id === activeFrame.input_id).map((item, index) => <li key={item.id ?? item.invocation_id + '-' + index}><button type="button" aria-pressed={selectedObject === index} onClick={() => setSelectedObject(index)}>{index + 1}. {item.details?.type_ru ?? CLASS_LABELS[item.class_name] ?? item.class_name}</button>{item.details && <p>{item.details.status === 'uncertain' && <strong>Тип не определён уверенно. </strong>}{item.details.evidence}{!item.box && <> · Без рамки: {item.details.missing_localization_reason}</>}</p>}<details><summary>Оценка модели</summary><p>{item.score === null ? 'Числовая уверенность не предоставлена.' : `${Math.round(item.score * 100)}% — оценка модели для этого объекта, не гарантия правильности и не вероятность нарушения.`}</p></details></li>)}</ol>
            {!objects.some(item => item.input_id === activeFrame.input_id) && <p>Рамок объектов нет. {activeFrame.observations.filter(item => item.state !== 'not_analyzed').map(item => `${CLASS_LABELS[item.class_name] ?? item.class_name}: ${OBSERVATION_STATES[item.state] ?? item.state}`).join('. ') || 'Текстовые наблюдения пока не получены.'}</p>}
            {activeFrame.artifact_id && activeFrame.sha256 && run.purpose !== 'comparison_campaign' && <details className="correction-workspace" ref={correction} onToggle={event => setEditing(event.currentTarget.open)}><summary>Исправить разметку</summary>{editing && <><button type="button" className="secondary" onClick={() => { if (correction.current) { correction.current.open = false; correction.current.querySelector('summary')?.focus() } }}>Вернуться к результату</button><AnnotationEditor key={activeFrame.input_id} runId={runId} inputId={activeFrame.input_id} checksum={activeFrame.sha256} artifactId={activeFrame.artifact_id} initial={objects.filter(item => item.input_id === activeFrame.input_id && item.box && EQUIPMENT.includes(item.class_name)).map((item,index) => ({ id: item.id ?? `00000000-0000-4000-8000-${String(index).padStart(12,'0')}`, class_name:item.class_name, box:item.box! }))} /></>}</details>}
          </> : <p>{complete ? 'Исходные кадры в проекции недоступны.' : 'Исходные кадры недоступны.'}</p>}
          {frames.length > 1 && <div className="source-thumbnails" aria-label="Выбор исходного кадра">{frames.map(frame => <article className="source-thumbnail" key={frame.input_id}>
            <SourceImage thumbnail runId={runId} artifactId={frame.artifact_id} label={'Кадр ' + (frame.ordinal + 1)} description={frameDescription(frame.observations)} />
            <h4>Кадр {frame.ordinal + 1}</h4>
            {supportingIds.includes(frame.input_id) && <span className="supporting-frame">Поддерживает вывод</span>}
            <button type="button" className="secondary" aria-pressed={activeFrame?.input_id === frame.input_id} onClick={() => { setActiveInputId(frame.input_id); setSelectedObject(null) }}>Выбрать кадр {frame.ordinal + 1}</button>
          </article>)}</div>}
        </section>
        <details className="result-basis"><summary>Основание вывода</summary>
        {complete && outcome === 'observations_only' && <section aria-label="Требует внимания"><h3>Что проверить</h3><p>{run.plan_binding ? <>Сопоставление относится к сохранённому плану. <a href={`/projects/${run.project_id ?? run.context?.project_id}/signals`} onClick={event => { if (onOpen) { event.preventDefault(); onOpen(`/projects/${run.project_id ?? run.context?.project_id}/signals`) } }}>Открыть сигналы проекта</a></> : 'Сопоставление с планом не выполнялось. Наблюдения не подтверждают соблюдение плана.'}</p></section>}
          <h3 id="basis-heading">Основание вывода</h3>
          <p>Период наблюдения: {period}.</p>
          <p>Заявленный участок наблюдения: {area} (со слов пользователя; по изображениям не подтверждена).</p>
          <section className="observation-rows" aria-labelledby="observations-heading">
            <h4 id="observations-heading">Техника на фотографиях</h4>
            {observations.length ? observations.filter(item => item.state !== 'not_analyzed' || item.reason !== 'unsupported_class').map((item, index) => {
              const input = inputs.find(value => value.input_id === item.input_id)
              const ordinal = complete ? item.ordinal : input?.ordinal ?? item.ordinal
              return <article className="observation-row" key={item.input_id + '-' + item.class_name + '-' + index}>
                <h5>Кадр {ordinal + 1}</h5>
                <p><strong>{CLASS_LABELS[item.class_name] ?? item.class_name}: {OBSERVATION_STATES[item.state] ?? item.state}</strong>{item.reason ? ' — ' + (OBSERVATION_REASONS[item.reason] ?? item.reason) : ''}</p>
              </article>
            }) : <p>{complete ? 'Данные наблюдений в проекции недоступны.' : 'Частичные наблюдения недоступны.'}</p>}
          </section>
          {observations.some(item => item.state === 'not_analyzed' && item.reason === 'unsupported_class') && <details><summary>Неподдерживаемые классы</summary>{observations.filter(item => item.state === 'not_analyzed' && item.reason === 'unsupported_class').map((item,index) => <article className="observation-row" key={index}><h5>Кадр {item.ordinal + 1}</h5><p>{CLASS_LABELS[item.class_name] ?? item.class_name}: Не анализировалось — Класс не поддерживается профилем распознавания.</p></article>)}</details>}
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
            <p>Период: {period}. Заявленный участок: {area} (со слов пользователя).</p>
            <p>Рекомендуемая проверка человеком: {projection?.recommendation || 'не указана'}.</p>
            <p>Это рекомендация для проверки, а не подтверждение нарушения.</p>
          </section>}
        </details>


      </div>

      <details className="result-details">
        <summary>Подробности анализа и кадров</summary>
        <p>Подтверждающие входные ID: {supportingIds.join(', ') || 'не указаны'}.</p>
        {series && <p>Пригодные входные ID: {series.usable_input_ids?.join(', ') || 'не указаны'}. Порядок: {series.input_order?.join(' → ') || 'не указан'}.</p>}
        <ol>{frames.map(frame => <li key={frame.input_id}>Кадр {frame.ordinal + 1}. Входной ID: <code>{frame.input_id}</code>. Исходный артефакт ID: <code>{frame.artifact_id ?? 'не указан'}</code>. SHA-256: <code>{frame.sha256 ?? 'не указан'}</code>.</li>)}</ol>
      </details>
    </section>
    {(run.ai_assessment || !!run.ai_evidence?.length) && <AiAssessmentPanel assessment={run.ai_assessment} evidence={run.ai_evidence ?? []} inputs={inputs} onOpenFrame={id => { const index = frames.findIndex(frame => frame.input_id === id); if (index >= 0) setSelected(index) }} />}
    {selected !== null && <EvidenceViewer runId={runId} frames={frames} native={run.native_evidence_by_frame ?? []} objects={objects} showBoxes={showBoxes} profile={run.profile_snapshot}
      context={projectionContext ?? run.context} selected={selected} onSelect={index => { setSelected(index); setActiveInputId(frames[index].input_id) }}
      onClose={() => { setSelected(null); opener.current?.focus() }} />}
  </>
}


function RunPipeline({ run, runId, disconnected }: { run: RunSnapshot; runId: string; disconnected: boolean }) {
  const [motion, setMotion] = useState(() => { try { return localStorage.getItem('analysis-motion') !== 'off' } catch { return false } })
  useEffect(() => { document.documentElement.dataset.analysisMotion = motion ? 'on' : 'off' }, [motion])
  const [activeId,setActiveId] = useState<string|null>(null)
  const current = run.stages.find(stage => stage.state === 'running')
  const failed = run.stages.find(stage=>stage.state==='failed')
  const active = run.state === 'running' && !disconnected
  const inputs=run.inputs??[]
  const input = inputs.find(item=>item.input_id===activeId)??inputs[0]
  const title=disconnected?'Связь прервана — проверяем состояние':failed?`Ошибка: ${STAGE_LABELS[failed.name]??'обработка'}`:current?STAGE_LABELS[current.name]??'Обработка фотографий':run.state==='queued'?'Ожидает начала обработки':run.state==='failed'?'Анализ завершился ошибкой':'Ожидаем состояние следующего этапа'
  const explanation=disconnected?'Последнее полученное состояние сохранено. Движение остановлено до ответа сервера.':failed?STAGE_REASONS[failed.reason??'']??'Обработка остановилась. Полученные данные сохранены; подробности и повтор анализа доступны ниже.':current?STAGE_EXPLANATIONS[current.name]??'Сервер обрабатывает фотографии.':run.state==='queued'?'Фотографии приняты. Обработка начнётся, когда сервер назначит исполнителя.':'Неполученные этапы не считаются завершёнными. Пропущенные этапы отмечены отдельно.'
  return <>{run.state !== 'succeeded' && <section className={`analysis-scene ${active && motion ? 'is-running' : ''} ${active && motion && current?.name==='equipment_observation'?'is-recognizing':''}`} aria-label="Ход анализа">
    <div className="analysis-photo-column"><div className="analysis-photo">{input?.artifact_id ? <SourceImage runId={runId} artifactId={input.artifact_id} label={`Кадр анализа ${input.ordinal+1}`} description="" objects={(run.objects ?? []).filter(item => item.input_id === input.input_id)} showBoxes /> : <p>Ожидаем зарегистрированные фотографии</p>}<div className="analysis-sweep" aria-hidden="true" /></div>
    {inputs.length>1&&<div className="analysis-thumbnails" aria-label="Кадры обработки">{inputs.map(frame=><div key={frame.input_id} className="analysis-thumbnail"><SourceImage thumbnail runId={runId} artifactId={frame.artifact_id} label={`Кадр ${frame.ordinal+1}`} description=""/><button aria-pressed={frame.input_id===input?.input_id} onClick={()=>setActiveId(frame.input_id)}>Кадр {frame.ordinal+1}</button></div>)}</div>}</div>
    <div className="analysis-state"><div key={`${title}:${disconnected}`} className={`analysis-stage-copy ${motion&&!disconnected?'motion-enabled':''}`}><h2>{title}</h2><p>{explanation}</p></div>
    <ol className="analysis-route" aria-label="Краткие этапы">{Object.keys(STAGE_LABELS).map(name=>{const stage=run.stages.find(item=>item.name===name),state=stage?.state??'pending';return <li key={name} className={`route-${state}`} aria-current={state==='running'?'step':undefined}><span className="route-marker" aria-hidden="true">{state==='succeeded'?<svg viewBox="0 0 20 20"><path d="m4 10 4 4 8-9" fill="none" stroke="currentColor" strokeWidth="2"/></svg>:null}</span><span>{STAGE_LABELS[name]}<small>{STAGE_STATES[state]??state}{state==='skipped'?` · ${STAGE_REASONS[stage?.reason??'']??'Не выполнено для этого анализа'}`:''}</small></span></li>})}</ol>
    <label><input type="checkbox" checked={motion} onChange={event => { setMotion(event.target.checked); try { localStorage.setItem('analysis-motion',event.target.checked ? 'on' : 'off') } catch { /* Motion remains optional without storage. */ } }} /> Движение во время анализа</label></div></section>}<details className="panel pipeline pipeline-details" >
    <summary>Этапы анализа</summary>
    <ol className="pipeline-stages">{run.stages.map(stage => <li key={stage.name} className={'pipeline-stage stage-' + stage.state}>
      <h3>{STAGE_LABELS[stage.name] ?? 'Этап анализа'}</h3>
      <p>{STAGE_STATES[stage.state] ?? 'Состояние доступно на сервере'}</p>
      {stage.reason && <><p className="stage-reason">{STAGE_REASONS[stage.reason] ?? 'Причина не описана для пользователя.'}</p>{!STAGE_REASONS[stage.reason] && <details><summary>Техническая причина</summary><code>{stage.reason}</code></details>}</>}
      {stage.timestamp && <time dateTime={stage.timestamp}>{new Date(stage.timestamp).toLocaleString('ru-RU')}</time>}
    </li>)}</ol>
  </details></>
}

const STAGE_LABELS: Record<string, string> = {
  input_registration: 'Регистрация входных данных', frame_usability: 'Проверка пригодности кадров',
  equipment_observation: 'Распознавание техники', series_aggregation: 'Объединение наблюдений серии',
  rule_evaluation: 'Проверка правила', result_projection: 'Формирование результата',
}
const STAGE_EXPLANATIONS: Record<string,string> = {
  input_registration:'Сохраняем фотографии и связываем каждый кадр с этим анализом.',
  frame_usability:'Проверяем, какие кадры пригодны для наблюдений.',
  equipment_observation:'Распознаём технику. Рамки появляются только после получения объектов от сервера.',
  series_aggregation:'Сопоставляем полученные наблюдения в пределах одной серии.',
  rule_evaluation:'Проверяем применимое правило по подтверждённым наблюдениям.',
  result_projection:'Сохраняем результат, его основания и ограничения.',
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
  if (location.pathname === '/') return 'projects'
  if (location.pathname === '/archive') return 'history'
  const workspace = location.pathname.match(/^\/projects\/([0-9a-f-]{36})(?:\/(analyses|new|plan|signals|runs\/[0-9a-f-]{36}))?$/i)
  if (workspace) return !workspace[2] ? 'overview' : workspace[2] === 'analyses' ? 'history' : workspace[2].startsWith('runs/') ? workspace[2].slice(5) : workspace[2]
  if (location.pathname === '/stages') return 'projects'
  const match = location.pathname.match(/^\/runs\/([0-9a-f-]{36})$/i)
  return match?.[1] ?? null
}

function About({ heading, returnPath, onReturn }: { heading: RefObject<HTMLHeadingElement | null>; returnPath: string; onReturn: () => void }) {
  return <section className="about" aria-labelledby="about-heading">
    <div className="page-intro"><p className="eyebrow">О проекте</p><h1 ref={heading} tabIndex={-1} id="about-heading">Контроль строительства</h1><p>Прототип команды «17 мгновений ИИ» помогает рассмотреть наблюдения по земляным работам котлована и решить, нужен ли ручной осмотр.</p></div>
    <div className="about-content">
      <section className="panel" aria-labelledby="about-method"><h2 id="about-method">Что анализируется</h2><p>Пользователь передаёт отдельное изображение или упорядоченную серию изображений одного заявленного участка. Прототип распознаёт два класса техники: экскаватор и самосвал. Участок и период указаны пользователем; сами кадры не устанавливают границы всей площадки.</p><p>Для каждого запрошенного класса на кадре показывается одно из состояний: «обнаружен», «не обнаружен в кадре», «недостаточно данных» (кадр или работа распознавания не позволяют оценить класс) и «не анализировался» (класс не был проверен). Необнаружение в кадре не доказывает отсутствие техники на всей площадке.</p><p>В режиме «Только распознать технику» система показывает наблюдения без проверки правила этапа. В режиме «Проверить правило этапа» она сопоставляет пригодные кадры серии с сохранённой неизменяемой ревизией демонстрационного правила и политики проверки. Это правило не является нормативным требованием.</p></section>
      <section className="panel" aria-labelledby="about-outcomes"><h2 id="about-outcomes">Как читать итог</h2><p>Для проверки правила оба класса должны быть проанализированы во всех пригодных кадрах одного заявленного участка, все наблюдения обязательных классов на переданных кадрах должны поддаваться оценке, а пригодных кадров должно быть минимум три. Если класс не анализировался или хотя бы одно наблюдение обязательного класса не удалось оценить, данных для проверки правила недостаточно.</p><p>Если экскаватор обнаружен хотя бы в одном пригодном кадре, а самосвал не обнаружен ни в одном пригодном кадре серии, итог «Рекомендована проверка человеком» (<code>check_requested</code>) рекомендует человеку проверить возможную задержку вывоза грунта. Это не доказательство нарушения.</p><p>Если в пригодной серии обнаружены и экскаватор, и самосвал, итог «Проверка не запрошена» (<code>no_check</code>) означает лишь, что по этой серии запрос проверки не сформирован. Это не подтверждает соблюдение требований на всей площадке. Если наблюдения не подтверждают работу экскаватора, данных для оценки вывоза грунта недостаточно.</p></section>
      <section className="panel" aria-labelledby="about-source"><h2 id="about-source">Источник демонстрации</h2><p>Демонстрационные серии иллюстрируют работу интерфейса. Они взяты из архива организаторов <code>artifacts/dataset/Строительная_техника.zip</code>: группы <code>organizer-archive-site-85-94</code> (файлы Строительная_техника/Screenshot_87.png, Строительная_техника/Screenshot_89.png, Строительная_техника/Screenshot_90.png) и <code>organizer-archive-site-22-26</code> (файлы Строительная_техника/Screenshot_23.png, Строительная_техника/Screenshot_25.png, Строительная_техника/Screenshot_26.png). Порядок кадров соответствует архиву; указанное в примерах время 12:00 условное, а исходная принадлежность кадров конкретной камере и площадке не подтверждена. Для демонстрации PNG-файлы преобразованы в JPEG-копии; загрузка в анализ принимает JPEG и PNG.</p><p>С запуском сохраняются переданные изображения и контекст; полученные наблюдения показываются отдельно. Для итогов «Рекомендована проверка человеком» и «Проверка не запрошена» указываются поддерживающие их кадры, ревизия правила и политика проверки; при одном лишь распознавании или недостатке данных такие кадры не выбираются.</p></section>
      <section className="panel" aria-labelledby="about-limits"><h2 id="about-limits">Границы прототипа</h2><p>Прототип не подключается к потокам камер и не отслеживает график строительства, текущий этап автоматически, тенденции или общее состояние проекта. Результат относится только к переданным изображениям и заявленному контексту.</p></section>
      <details className="panel"><summary>Архив экспериментов</summary><a href="/readiness">Историческая проверка качества</a><p><a href="/provider-comparison">Историческое сравнение моделей ИИ</a></p><p>Эти профили выведены из исполнения. Сохранённые результаты доступны для изучения.</p></details><aside className="panel about-team" aria-label="Команда проекта"><img src="/team-logo.png" alt="" onError={event => { event.currentTarget.hidden = true }} /><p>Команда: <strong>17 мгновений ИИ</strong></p></aside>
    </div><a className="about-return" href={returnPath} onClick={event => { event.preventDefault(); onReturn() }}>Вернуться назад</a>
  </section>
}

async function siteRequest<T>(path: string, method = 'GET', body?: object, signal?: AbortSignal, requestKey?: string): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  if (signal?.aborted) controller.abort()
  let timeout: ReturnType<typeof setTimeout> | undefined
  const read = async () => {
    const response = await fetch(`/api${path}`, { method, signal: controller.signal, ...(body ? { headers: { 'Content-Type': 'application/json', ...attributionHeaders(), ...(path === '/projects' && method === 'POST' ? { 'Idempotency-Key': requestKey ?? crypto.randomUUID() } : {}) }, body: JSON.stringify(body) } : {}) })
    if (!response.ok) throw new Error((await response.json().catch(() => ({})) as { code?: string }).code ?? 'request_failed')
    return response.json() as Promise<T>
  }
  try {
    return method === 'GET' ? await Promise.race([read(), new Promise<T>((_, reject) => {
      timeout = setTimeout(() => { controller.abort(); reject(new Error('read_timeout')) }, 10000)
    })]) : await read()
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', abort) }
}

function localDateTime(value: string): string {
  const date = new Date(value)
  const minutes = date.getTimezoneOffset()
  return new Date(date.getTime() - minutes * 60_000).toISOString().slice(0, 16)
}

function SiteWorkspace({ heading, projectId, onDirty }: { heading: RefObject<HTMLHeadingElement | null>; projectId: string; onDirty: (dirty: boolean) => void }) {
  const [zones, setZones] = useState<Zone[]>([])
  const [zoneId, setZoneId] = useState('')
  const [works, setWorks] = useState<CatalogWork[]>([])
  const [plan, setPlan] = useState<ZonePlan>({ revision_number: 0, entries: [] })
  const [draft, setDraft] = useState<PlanEntry[]>([])
  const [zoneName, setZoneName] = useState('')
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [readAttempt, setReadAttempt] = useState(0)
  const areaRef = useRef(zoneId)
  areaRef.current = zoneId
  const live = useRef(true)
  useEffect(() => { live.current = true; return () => { live.current = false } }, [])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const loadZones = async (id: string) => setZones((await siteRequest<{ zones: Zone[] }>(`/projects/${id}/zones`)).zones)
  const [baseline, setBaseline] = useState('[]')
  const loadPlan = async (id: string, signal?: AbortSignal) => {
    const current = await siteRequest<ZonePlan>(`/zones/${id}/plan`, 'GET', undefined, signal)
    if (signal?.aborted || !live.current || areaRef.current !== id) return
    setBaseline(JSON.stringify(current.entries.map(entry => ({ ...entry, starts_at: localDateTime(entry.starts_at), ends_at: localDateTime(entry.ends_at) }))))
    setPlan(current)
    setDraft(current.entries.map(entry => ({ ...entry, starts_at: localDateTime(entry.starts_at), ends_at: localDateTime(entry.ends_at) })))
  }
  const dirty = JSON.stringify(draft) !== baseline
  useEffect(() => { onDirty(dirty || busy); return () => onDirty(false) }, [dirty, busy, onDirty])
  useEffect(() => {
    const controller = new AbortController()
    void siteRequest<{ works: CatalogWork[] }>('/catalog/works', 'GET', undefined, controller.signal)
      .then(data => { if (!controller.signal.aborted) setWorks(data.works) }).catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить каталог работ.') })
    void siteRequest<{ zones: Zone[] }>(`/projects/${projectId}/zones`, 'GET', undefined, controller.signal)
      .then(data => { if (!controller.signal.aborted) { setZones(data.zones); setZoneId(data.zones[0]?.id ?? '') } }).catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить участки.') })
    return () => controller.abort()
  }, [projectId, readAttempt])
  useEffect(() => {
    const controller = new AbortController()
    setPlan({ revision_number: 0, entries: [] }); setDraft([]); setBaseline('[]')
    setLoading(!!zoneId)
    if (zoneId) void loadPlan(zoneId, controller.signal).catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить план участка.') }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [zoneId, readAttempt])
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
    <div className="page-intro"><h1 ref={heading} tabIndex={-1} id="site-heading">Проект и план участка</h1><p>Работы из исходного каталога можно запланировать параллельно. Каждое сохранение создаёт новую ревизию.</p></div>
    {error && <p className="error" role="alert">{error} <button type="button" disabled={busy || loading} onClick={() => { if (!dirty || window.confirm("Заменить черновик сохранённым планом?")) { setError(''); setReadAttempt(value => value + 1) } }}>Повторить загрузку</button></p>}{notice && <p role="status">{notice}</p>}
    <div className="site-columns"><section className="panel"><h2>Проект и участок</h2>
      {projectId && <><label className="field">Участок<select disabled={busy || loading} aria-label="Участок" value={zoneId} onChange={event => { if (!dirty || window.confirm("Покинуть несохранённый план?")) setZoneId(event.target.value) }}><option value="">Выберите участок</option>{zones.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><form onSubmit={event => { event.preventDefault(); if (dirty && !window.confirm("Покинуть несохранённый план?")) return; void mutate(async () => { const created = await siteRequest<Zone>(`/projects/${projectId}/zones`, 'POST', { name: zoneName }); await loadZones(projectId); setZoneId(created.id); setZoneName(''); setNotice('Участок создан.') }) }}><div className="field"><label htmlFor="zone-name">Новый участок</label><input id="zone-name" required maxLength={200} value={zoneName} onChange={event => setZoneName(event.target.value)} /></div><button type="submit" className="secondary" disabled={busy || loading}>Создать участок</button></form></>}
    </section><section className="panel"><h2>Каталог работ</h2><p>Строк в источнике: {works.length}.</p><div className="field"><label htmlFor="catalog-search">Найти работу по коду или названию</label><input id="catalog-search" value={search} onChange={event => setSearch(event.target.value)} /></div><div className="catalog-results"><ol>{visibleWorks.slice(0, 100).map(work => <li key={work.id}><code>{work.code ?? '—'}</code> {work.title} <small>строка {work.source_row}</small></li>)}</ol>{visibleWorks.length > 100 && <p>Показаны первые 100 строк. Уточните поиск.</p>}</div></section></div>
    {zoneId && <section className="panel plan-editor"><h2>План участка · ревизия {plan.revision_number}</h2><p>Время вводится по часовому поясу этого компьютера и сохраняется с его UTC-смещением. Выбранная ревизия сохранится с анализом.</p><div className="plan-entries">{draft.map((entry, index) => <fieldset disabled={busy || loading} key={entry.id ?? index} className="plan-entry"><legend>Работа {index + 1}</legend><div className="field"><label htmlFor={`work-${index}`}>Работа каталога</label><select id={`work-${index}`} value={entry.catalog_work_id} onChange={event => changeEntry(index, { catalog_work_id: event.target.value })}>{works.map(work => <option key={work.id} value={work.id}>{work.code ?? '—'} · {work.title} (строка {work.source_row})</option>)}</select></div><div className="plan-fields"><div className="field"><label htmlFor={`start-${index}`}>Начало</label><input id={`start-${index}`} type="datetime-local" value={entry.starts_at} onChange={event => changeEntry(index, { starts_at: event.target.value })} /></div><div className="field"><label htmlFor={`end-${index}`}>Окончание</label><input id={`end-${index}`} type="datetime-local" value={entry.ends_at} onChange={event => changeEntry(index, { ends_at: event.target.value })} /></div><div className="field"><label htmlFor={`state-${index}`}>Состояние</label><select id={`state-${index}`} value={entry.state} onChange={event => changeEntry(index, { state: event.target.value as PlanEntry['state'] })}><option value="planned">Запланирована</option><option value="active">Активна</option><option value="completed">Завершена</option></select></div><div className="field"><label htmlFor={`stage-${index}`}>Сценарий анализа</label><select id={`stage-${index}`} value={entry.stage_key ?? ''} onChange={event => changeEntry(index, { stage_key: event.target.value || null })}><option value="">Без автоматического сценария</option>{PLAN_STAGES.map(key => <option key={key} value={key}>{STAGE_NAMES[key]}</option>)}</select></div></div>{(['expected_equipment', 'allowed_equipment', 'excluded_equipment'] as const).map((field, fieldIndex) => <fieldset className="equipment-checkboxes" key={field}><legend>{['Ожидаемая техника', 'Допустимая техника', 'Явно не предусмотренная техника'][fieldIndex]} · работа {index + 1}</legend>{EQUIPMENT.map(machine => <label key={machine}><input type="checkbox" checked={entry[field].includes(machine)} onChange={event => changeEntry(index, { [field]: event.target.checked ? [...entry[field],machine] : entry[field].filter(value => value !== machine) })} />{CLASS_LABELS[machine]}</label>)}</fieldset>)}<button type="button" className="secondary" onClick={() => setDraft(current => current.filter((_, position) => position !== index))}>Удалить работу</button></fieldset>)}</div><div className="upload-actions"><button type="button" className="secondary" disabled={busy || loading || !works.length} onClick={addEntry}>Добавить работу</button><button type="button" className="primary" disabled={busy || loading} onClick={() => void mutate(async () => { const saved = await siteRequest<{ revision_number: number }>(`/zones/${zoneId}/plan`, 'PUT', { expected_revision: plan.revision_number, entries: draft.map(({ id: _id, starts_at, ends_at, ...rest }) => ({ ...rest, start_at: periodWithOffset(starts_at), end_at: periodWithOffset(ends_at) })) }); await loadPlan(zoneId); setNotice(`Сохранена ревизия ${saved.revision_number}.`) })}>Сохранить новую ревизию</button><button type="button" className="secondary" disabled={busy || loading} onClick={() => { if (!dirty || window.confirm("Заменить черновик сохранённым планом?")) void mutate(() => loadPlan(zoneId)) }}>Обновить с сервера</button></div></section>}
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
  return <section className="panel stage-confirmation" aria-labelledby="hypotheses-heading"><h2 id="hypotheses-heading">Гипотеза модели об этапе</h2>{run.ai_assessment ? <p>{STAGE_NAMES[run.ai_assessment.stage_hypothesis.stage] ?? run.ai_assessment.stage_hypothesis.stage}: {run.ai_assessment.stage_hypothesis.reason}</p> : hypotheses.length ? <ul>{hypotheses.map(item => <li key={item.stage}>{STAGE_NAMES[item.stage] ?? item.stage}: {CLASS_LABELS[item.equipment] ?? item.equipment}, признаки сцены {item.scene_features.join(', ')}</li>)}</ul> : <p>{run.profile_snapshot?.observation_contract === "equipment-boxes-v2" ? "По этим кадрам этап определить не удалось: нужны техника и подтверждающий признак сцены в одном кадре." : "Этот профиль распознаёт присутствие техники, но не признаки сцены. Гипотеза этапа для него недоступна."}</p>}{confirmed ? <p>Человек подтвердил этап «{STAGE_NAMES[confirmed.stage] ?? confirmed.stage}». {confirmed.comment}</p> : <><h3>Подтверждение человеком</h3><p>Подтвердите или исправьте этап. Подтверждение не меняет план автоматически.</p><div className="field"><label htmlFor="confirmed-stage">Этап</label><select id="confirmed-stage" value={stage} onChange={event => setStage(event.target.value)}><option value="">Выберите этап</option>{Object.entries(STAGE_NAMES).filter(([value]) => !['unknown', 'ambiguous'].includes(value)).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><div className="field"><label htmlFor="stage-comment">Комментарий</label><textarea id="stage-comment" maxLength={2000} value={comment} onChange={event => setComment(event.target.value)} /></div><button type="button" className="secondary" disabled={!stage || busy} onClick={() => { setBusy(true); setError(''); void siteRequest<{ stage: string; comment: string }>(`/runs/${runId}/confirm-stage`, 'POST', { stage, comment }).then(setConfirmed).catch(() => setError('Не удалось сохранить подтверждение этапа.')).finally(() => setBusy(false)) }}>Подтвердить этап</button>{error && <p className="error" role="alert">{error}</p>}</>}</section>
}

function ProjectList({ heading, projects, loaded, navigate, onCreated, onDraft }: { heading: RefObject<HTMLHeadingElement | null>; projects: Project[]; loaded: boolean; navigate: (path: string) => void; onCreated: (project: Project) => void; onDraft: (dirty: boolean) => void }) {
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { onDraft(!!name.trim() || busy); return () => onDraft(false) }, [name, busy, onDraft])
  const pendingCreation = useRef<{ body: string; key: string } | null>(null)
  return <section aria-labelledby="projects-heading"><div className="page-intro"><h1 id="projects-heading" ref={heading} tabIndex={-1}>Проекты</h1><p>Создайте проект, загрузите фотографии и рассмотрите результат. План можно добавить позже.</p><p>Общий список доступен всем посетителям без регистрации.</p></div>{!loaded ? <p role="status">Загружаем проекты…</p> : projects.length ? <ul className="project-list">{projects.map(project => <li className="panel" key={project.id}><h2><a href={`/projects/${project.id}`} onClick={event => { event.preventDefault(); navigate(`/projects/${project.id}`) }}>{project.name}</a></h2><p>{project.timezone}</p></li>)}</ul> : <p className="panel">Проектов пока нет. Начните с названия — основной участок создастся автоматически.</p>}<details className="project-create-action" open={!projects.length}><summary>Создать новый проект</summary><form className="panel project-create" onSubmit={event => { event.preventDefault(); setBusy(true); setError(''); const body = { name: name.trim(), timezone }; const serialized = JSON.stringify(body); if (pendingCreation.current?.body !== serialized) pendingCreation.current = { body: serialized, key: crypto.randomUUID() }; void siteRequest<Project>('/projects', 'POST', body, undefined, pendingCreation.current.key).then(onCreated).catch(() => setError('Не удалось создать проект. Проверьте название и повторите попытку.')).finally(() => setBusy(false)) }}><label className="field" htmlFor="project-name">Название проекта<input id="project-name" required maxLength={200} value={name} onChange={event => setName(event.target.value)} /></label><details><summary>Дополнительные настройки</summary><label className="field" htmlFor="project-timezone">Часовой пояс<input id="project-timezone" required value={timezone} onChange={event => setTimezone(event.target.value)} /></label></details><button className="primary" disabled={busy || !name.trim()}>{busy ? 'Создаём…' : 'Создать проект'}</button>{error && <p className="error" role="alert">{error}</p>}</form></details><p><a href="/archive" onClick={event => { event.preventDefault(); navigate('/archive') }}>Архив анализов без проекта</a></p></section>
}

function ProjectOverview({ projectId, projectName, heading, navigate }: { projectId: string; projectName?: string; heading: RefObject<HTMLHeadingElement | null>; navigate: (path: string) => void }) {
  const [data, setData] = useState<{ runs: HistoryRun[]; total: number; open: number; plans: { zone: Zone; plan: ZonePlan }[]; works: CatalogWork[] } | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    const read = <T,>(path: string) => siteRequest<T>(path, 'GET', undefined, controller.signal)
    void Promise.all([read<{ runs: HistoryRun[]; total: number }>(`/runs?project_id=${projectId}`), read<{ signals: { state: string }[] }>(`/signals?project_id=${projectId}`), read<{ zones: Zone[] }>(`/projects/${projectId}/zones`), read<{ works: CatalogWork[] }>('/catalog/works')]).then(async ([history, signals, zones, catalog]) => {
      const plans = await Promise.all(zones.zones.map(async zone => ({ zone, plan: await read<ZonePlan>(`/zones/${zone.id}/plan`) })))
      if (!controller.signal.aborted) { setData({ runs: history.runs, total: history.total, open: signals.signals.filter(signal => signal.state !== 'closed').length, plans, works: catalog.works }); setError('') }
    }).catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить обзор проекта. Повторите попытку.') })
    return () => controller.abort()
  }, [projectId, attempt])
  return <section className="project-overview" aria-labelledby="overview-heading"><div className="page-intro"><p className="eyebrow">Обзор проекта</p><h1 ref={heading} tabIndex={-1} id="overview-heading">{projectName ?? 'Проект'}</h1><p>Фотографии показывают наблюдения в выбранном участке. Решение о состоянии работ принимает человек.</p><a className="primary" href={`/projects/${projectId}/new`} onClick={event => { event.preventDefault(); navigate('/new') }}>Загрузить фотографии</a></div>{error && <p className="error" role="alert">{error} <button onClick={() => setAttempt(value => value + 1)}>Повторить</button></p>}{!data && !error && <p role="status">Загружаем обзор…</p>}{data && <><section className="panel"><h2>Последние анализы</h2><p>Всего: {data.total}. <a href={`/projects/${projectId}/analyses`} onClick={event => { event.preventDefault(); navigate('/analyses') }}>Все анализы</a></p>{data.runs.length ? <ul>{data.runs.slice(0, 5).map(run => <li key={run.id}><a href={`/projects/${projectId}/runs/${run.id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${run.id}`) }}>{run.created_at ? new Date(run.created_at).toLocaleString('ru-RU') : 'Открыть анализ'}</a> — {RUN_STATES[run.state] ?? 'Состояние неизвестно'}{run.outcome ? ` · ${OUTCOME_LABELS[run.outcome] ?? 'Результат доступен'}` : ''}</li>)}</ul> : <p>Фотографии ещё не анализировались.</p>}</section><section className="panel"><h2>Требуют внимания</h2><p>Открытых сигналов: {data.open}. <a href={`/projects/${projectId}/signals`} onClick={event => { event.preventDefault(); navigate('/signals') }}>Рассмотреть сигналы</a></p><p>Сигнал — рекомендация для проверки, а не подтверждение нарушения.</p></section><section className="panel"><h2>Запланированные работы</h2>{data.plans.some(item => item.plan.entries.length) ? data.plans.map(({ zone, plan }) => <div key={zone.id}><h3>{zone.name}</h3><ul>{plan.entries.map((entry, index) => <li key={entry.id ?? index}>{data.works.find(work => work.id === entry.catalog_work_id)?.title ?? 'Работа каталога'} — {new Date(entry.starts_at).toLocaleDateString('ru-RU')}–{new Date(entry.ends_at).toLocaleDateString('ru-RU')}; {entry.state === 'completed' ? 'завершена' : entry.state === 'active' ? 'активна' : 'запланирована'}</li>)}</ul></div>) : <p>План пока не добавлен. Анализ фотографий доступен без плана.</p>}<a href={`/projects/${projectId}/plan`} onClick={event => { event.preventDefault(); navigate('/plan') }}>Открыть план</a></section></>}</section>
}

export default function App() {
  const injectedChoices = (globalThis as typeof globalThis & { __ANALYSIS_CHOICES__?: Choice[] }).__ANALYSIS_CHOICES__
  const [route, setRoute] = useState(runIdFromPath)
  const [projectId, setProjectId] = useState(() => location.pathname.match(/^\/projects\/([0-9a-f-]{36})/i)?.[1] ?? '')
  const [projects, setProjects] = useState<Project[]>([])
  const [projectsError, setProjectsError] = useState('')
  const [projectsAttempt, setProjectsAttempt] = useState(0)
  const [projectsLoaded, setProjectsLoaded] = useState(false)
  const [planDirty, setPlanDirty] = useState(false)
  const [projectDraft, setProjectDraft] = useState(false)
  const [uploadDirty, setUploadDirty] = useState(false)
  const currentPath = useRef(location.pathname)
  const navigationGeneration = useRef(0)
  const historyPosition = useRef<number>(history.state?.workspacePosition ?? 0)
  const restoringHistory = useRef(false)

  const draftDirty = useRef(false)
  const [historyTotal, setHistoryTotal] = useState<number | null>(null)
  const project = projects.find(item => item.id === projectId)
  const scoped = (path: string) => projectId && /^\/(new|plan|signals|analyses|history|runs\/)/.test(path) ? `/projects/${projectId}${path === '/history' ? '/analyses' : path}` : path

  const routeRef = useRef(route)
  const historyPath = useRef(location.pathname === "/analyses" ? "/analyses" : "/history")
  const [scenario, setScenario] = useState('')
  const [choices, setChoices] = useState<Choice[]>(injectedChoices ?? [])
  const [choicesLoading, setChoicesLoading] = useState(!injectedChoices)
  const [choicesAttempt, setChoicesAttempt] = useState(0)
  const [stage, setStage] = useState('excavation')
  const intent: string = 'observation_only'
  const [area, setArea] = useState('')
  const [period, setPeriod] = useState(localPeriod)
  const [captureTimes, setCaptureTimes] = useState<Record<string, string>>({})
  const [analysisProjects, setAnalysisProjects] = useState<Project[]>([])
  const [planPickerOpen, setPlanPickerOpen] = useState(false)
  const [analysisProjectId, setAnalysisProjectId] = useState(projectId)
  const [analysisZones, setAnalysisZones] = useState<Zone[]>([])
  const [analysisZoneId, setAnalysisZoneId] = useState('')
  const [analysisPlan, setAnalysisPlan] = useState<ZonePlan | null>(null)
  const [workspaceReadError, setWorkspaceReadError] = useState('')
  const [workspaceReadAttempt, setWorkspaceReadAttempt] = useState(0)
  const [frames, setFrames] = useState<Frame[]>([])
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState('')
  const [trainingProject, setTrainingProject] = useState('')
  const [trainingBusy, setTrainingBusy] = useState(false)
  const [trainingFrameId, setTrainingFrameId] = useState('')
  const trainingFrame = useRef('')
  const [trainingRunId, setTrainingRunId] = useState('')
  const trainingRun = useRef('')
  const trainingGeneration = useRef(0)
  const trainingRequest = useRef<AbortController | null>(null)
  const trainingLoading = useRef(false)
  const trainingEdits = useRef(0)
  const currentProjectDraft = useRef(projectDraft)
  currentProjectDraft.current = projectDraft
  const trainingReady = !!trainingFrameId && frames.length === 1 && frames[0].id === trainingFrameId
  const trainingOwner = useRef('')
  const [trainingError, setTrainingError] = useState('')
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
  const [cloudConsent, setCloudConsent] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  const consentScope = JSON.stringify({ projectId, route, frames: frames.map(frame => frame.id),
    scenario, area, period, stage, captureTimes, analysisProjectId, analysisZoneId,
    planPickerOpen, planRevisionId: analysisPlan?.revision_id })
  useEffect(() => {
    if (pending) {
      try { setCloudConsent(JSON.parse(pending.body).cloud_processing_consent === true) }
      catch { setCloudConsent(false) }
    } else setCloudConsent(false)
  }, [pending, consentScope])
  let pendingProject = ''
  try { pendingProject = pending ? JSON.parse(pending.body).project_id ?? '' : '' } catch { /* Legacy request remains unchanged. */ }
  const foreignPending = !!pending && pendingProject !== projectId

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
  const [unsupportedStageNotice] = useState(false)
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
  draftDirty.current = planDirty || (route === 'new' && (uploadDirty || frames.length > 0 || !!pending || sending || validating || demoLoading))

  useEffect(() => {
    if (!projectId && route !== 'projects') return
    const controller = new AbortController()
    setProjectsError('')
    void siteRequest<{ projects: Project[] }>('/projects', 'GET', undefined, controller.signal).then(data => {
      if (!controller.signal.aborted) { setProjects(data.projects ?? []); setProjectsLoaded(true) }
    }).catch(() => { if (!controller.signal.aborted) setProjectsError('Не удалось загрузить проекты. Повторите попытку.') })
    return () => controller.abort()
  }, [projectsAttempt, projectId, route === 'projects'])
  useEffect(() => {
    setAnalysisProjectId(projectId); setAnalysisZones([]); setAnalysisZoneId(''); setAnalysisPlan(null)
    setHistoryRuns([]); setHistoryLoaded(false); setHistoryNextOffset(null); setHistoryPage(0); setHistoryTotal(null)
    setArea(''); setScenario(projectId ? 'Наблюдение за строительством' : '')
    setPlanPickerOpen(false); setPlanDirty(false); setUploadDirty(false)
  }, [projectId])

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine)
    history.replaceState({ ...history.state, workspacePosition: historyPosition.current }, '', location.href)
    const pop = () => {
      if (restoringHistory.current) { restoringHistory.current = false; return }
      const position = history.state?.workspacePosition ?? historyPosition.current - 1

      if (draftDirty.current && !window.confirm('Покинуть несохранённый черновик? Отправленный запрос останется доступен для восстановления.')) {
        restoringHistory.current = true
        history.go(historyPosition.current - position)
        return
      }
      historyPosition.current = position
      navigationGeneration.current++
      cancelTraining()
      cancelUpload()
      updateFrames([]); setRemoved(null); setCaptureTimes({}); setPlanDirty(false); setUploadDirty(false)
      closeCamera(); currentPath.current = location.pathname
      setProjectId(location.pathname.match(/^\/projects\/([0-9a-f-]{36})/i)?.[1] ?? '')
      routeRef.current = runIdFromPath(); focusAfterNavigation.current = true; setRunSnapshot(null); setRunChecked(false); setRunMissing(false); setRoute(routeRef.current)
    }
    const unload = (event: BeforeUnloadEvent) => { if (draftDirty.current) { event.preventDefault(); event.returnValue = '' } }
    addEventListener('beforeunload', unload)
    addEventListener('online', update)
    addEventListener('offline', update)
    addEventListener('popstate', pop)
    return () => { removeEventListener('online', update); removeEventListener('offline', update); removeEventListener('popstate', pop); removeEventListener('beforeunload', unload) }
  }, [])

  useEffect(() => {
    mounted.current = true
    const navigation = navigationGeneration.current
    void recoverPending().then(request => {
      if (mounted.current && request) {
        setPending(request)
        try {
          const saved = JSON.parse(request.body) as { project_id?: string }
          if (saved.project_id && navigation === navigationGeneration.current) {
            const path = `/projects/${saved.project_id}/new`
            history.replaceState({ ...history.state, workspacePosition: historyPosition.current }, '', path); currentPath.current = path
            setProjectId(saved.project_id); routeRef.current = 'new'; setRoute('new')
          }
        } catch { /* The unchanged saved request remains available for recovery. */ }
        if (navigation === navigationGeneration.current) setErrors(current => ({ ...current, submit: 'Предыдущая отправка требует проверки. Повторите её с сохранённым ключом.' }))
      }
    }).catch(() => {
      if (mounted.current && navigation === navigationGeneration.current) setErrors(current => ({ ...current, submit: 'Не удалось восстановить отправку. Сохраните вкладку и повторите попытку позже.' }))
    }).finally(() => { if (mounted.current) setRecovering(false) })
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    if (route !== 'new' || projectId || !planPickerOpen) return
    let active = true
    const controller = new AbortController()
    void siteRequest<{ projects: Project[] }>('/projects', 'GET', undefined, controller.signal).then(data => { if (active && Array.isArray(data.projects)) setAnalysisProjects(data.projects) }).catch(() => {})
    return () => { active = false; controller.abort() }
  }, [route, planPickerOpen])
  useEffect(() => {
    setAnalysisZones([]); setAnalysisZoneId(''); setAnalysisPlan(null); setWorkspaceReadError('')
    if (!analysisProjectId || route !== 'new') return
    let active = true
    const controller = new AbortController()
    void siteRequest<{ zones: Zone[] }>(`/projects/${analysisProjectId}/zones`, 'GET', undefined, controller.signal).then(data => { if (active && Array.isArray(data.zones)) { setAnalysisZones(data.zones); if (projectId) setAnalysisZoneId(data.zones[0]?.id ?? '') } }).catch(() => { if (active) setWorkspaceReadError('Не удалось загрузить участки. Повторите загрузку.') })
    return () => { active = false; controller.abort() }
  }, [analysisProjectId, workspaceReadAttempt, route])
  useEffect(() => {
    setAnalysisPlan(null)
    if (projectId) setPlanPickerOpen(false)
    if (!analysisZoneId || route !== 'new') return
    const chosenZone = analysisZones.find(zone => zone.id === analysisZoneId)
    if (chosenZone) setArea(chosenZone.name)
    let active = true
    const controller = new AbortController()
    void siteRequest<ZonePlan>(`/zones/${analysisZoneId}/plan`, 'GET', undefined, controller.signal).then(data => { if (active && data.revision_id) setAnalysisPlan(data) }).catch(() => { if (active) setWorkspaceReadError('Не удалось проверить план участка. Повторите загрузку.') })
    return () => { active = false; controller.abort() }
  }, [analysisZoneId, analysisZones, route])

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
    if (!route || route === 'about' || route === 'readiness' || route === 'provider-comparison' || route === 'history' || route === 'new' || route === 'stages' || route === 'plan' || route === 'signals' || route === 'projects' || route === 'overview') return
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
        const owner = data.project_id ?? data.context?.project_id ?? ''
        if (owner !== projectId || (owner && !location.pathname.startsWith(`/projects/${owner}/runs/`))) {
          const path = owner ? `/projects/${owner}/runs/${route}` : `/runs/${route}`
          history.replaceState({ ...history.state, workspacePosition: historyPosition.current }, '', path); currentPath.current = path; setProjectId(owner)
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
  }, [route, projectId, runReadAttempt])

  useEffect(() => {
    if (route !== 'history') return
    let active = true
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout>
    let refresh: ReturnType<typeof setTimeout>
    setHistoryLoading(true)
    void Promise.race([
      fetch(`/api/runs?${projectId ? `project_id=${projectId}` : 'unassigned=true'}`, { signal: controller.signal }),
      new Promise<Response>((_, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error('timeout')) }, 10000) }),
    ]).then(async response => {
      if (!response.ok) throw new Error('history_unavailable')
      const data = await response.json() as { runs: HistoryRun[]; next_offset?: number | null; total?: number }
      if (!active) return
      setHistoryRuns(current => historyAttempt && current.length
        ? [...current.map(old => data.runs.find(run => (run.id ?? run.run_id) === (old.id ?? old.run_id)) ?? old),
          ...data.runs.filter(run => !current.some(old => (old.id ?? old.run_id) === (run.id ?? run.run_id)))]
        : data.runs)
      if (historyPageRef.current === 0) setHistoryNextOffset(data.next_offset ?? null)
      setHistoryTotal(data.total ?? null)
      setHistoryLoaded(true)
      setHistoryError('')
    }).catch(() => { if (active) setHistoryError('Не удалось загрузить историю анализов.')
    }).finally(() => { clearTimeout(timeout); if (active) {
      setHistoryLoading(false)
      refresh = setTimeout(() => setHistoryAttempt(value => value + 1), 3000)
    } })
    return () => { active = false; controller.abort(); clearTimeout(timeout); clearTimeout(refresh) }
  }, [route, projectId, historyAttempt])

  useEffect(() => {
    if (route !== 'history' || historyPage === 0) return
    let active = true
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout>
    setHistoryPageLoading(true)
    void Promise.race([
      fetch(`/api/runs?offset=${historyPage}&${projectId ? `project_id=${projectId}` : 'unassigned=true'}`, { signal: controller.signal }),
      new Promise<Response>((_, reject) => { timeout = setTimeout(() => { controller.abort(); reject(new Error('timeout')) }, 10000) }),
    ]).then(async response => {
      if (!response.ok) throw new Error('history_unavailable')
      const data = await response.json() as { runs: HistoryRun[]; next_offset?: number | null; total?: number }
      if (!active) return
      setHistoryRuns(current => [...current, ...data.runs.filter(run => !current.some(item => (item.id ?? item.run_id) === (run.id ?? run.run_id)))])
      setHistoryNextOffset(data.next_offset ?? null)
      setHistoryError('')
    }).catch(() => { if (active) setHistoryError('Не удалось загрузить историю анализов.')
    }).finally(() => { clearTimeout(timeout); if (active) setHistoryPageLoading(false) })
    return () => { active = false; controller.abort(); clearTimeout(timeout) }
  }, [route, projectId, historyPage])

  async function retryRun() {
    if (!route || route === 'about' || route === 'readiness' || route === 'provider-comparison' || route === 'history' || route === 'new' || route === 'stages' || route === 'plan' || route === 'signals' || route === 'projects' || route === 'overview' || retrying) return
    const sourceRoute = route
    setRetrying(true)
    setRetryError('')
    try {
      const response = await fetch(`/api/runs/${route}/retry`, { method: 'POST', headers: attributionHeaders() })
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
    document.title = route === 'about' ? 'О проекте — Контроль строительства' : route === 'provider-comparison' ? 'Сравнение моделей ИИ — Контроль строительства' : route === 'readiness' ? 'Проверка качества — Контроль строительства' : route === 'history' ? 'История анализов — Контроль строительства' : route === 'stages' ? 'Этапы — Контроль строительства' : route === 'plan' ? 'План — Контроль строительства' : route === 'signals' ? 'Сигналы — Контроль строительства' : route === 'new' ? 'Новый анализ — Контроль строительства' : route ? 'Анализ — Контроль строительства' : 'Страница не найдена — Контроль строительства'
  }, [route, projectId])

  useEffect(() => () => { cameraGeneration.current++; cameraStream.current?.getTracks().forEach(track => track.stop()) }, [])

  useEffect(() => {
    if (cameraOpen && cameraVideo.current) cameraVideo.current.srcObject = cameraStream.current
  }, [cameraOpen])

  function cancelUpload() {
    demoGeneration.current++
    demoLoadingRef.current = false
    setDemoLoading(false); setValidating(false)
    validationQueue.current = Promise.resolve()
  }

  function navigate(path: string, accepted = false, useWorkspace = true, preparingTraining = false) {
    if (useWorkspace) path = scoped(path)
    if (path === location.pathname) return
    if (!accepted && draftDirty.current && !window.confirm('Покинуть несохранённый черновик? Отправленный запрос останется доступен для восстановления.')) return
    navigationGeneration.current++
    if (!preparingTraining) cancelTraining()
    const keepTrainingRun = accepted && !!trainingRun.current && path.endsWith(`/runs/${trainingRun.current}`)
    if (!keepTrainingRun) { trainingRun.current = ''; setTrainingRunId('') }
    if (route === 'new') { cancelUpload(); updateFrames([], keepTrainingRun); setRemoved(null); setCaptureTimes({}); setErrors({}); setUploadDirty(false) }
    setPlanDirty(false)
    currentPath.current = path
    setProjectId(path.match(/^\/projects\/([0-9a-f-]{36})/i)?.[1] ?? '')

    if (path === "/analyses" || path === "/history") historyPath.current = path
    closeCamera()
    historyPosition.current++
    history.pushState({ ...(path === '/about' ? { aboutFromApp: true, returnPath: location.pathname } : {}), workspacePosition: historyPosition.current }, '', path)
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

  function cancelTraining() {
    trainingGeneration.current++
    trainingRequest.current?.abort()
    trainingRequest.current = null
    setTrainingProject(''); setTrainingBusy(false)
  }

  useEffect(() => {
    const edited = (event: Event) => { if ((event.target as HTMLElement).closest('#main')) trainingEdits.current++ }
    document.addEventListener('input', edited)
    return () => { document.removeEventListener('input', edited); trainingRequest.current?.abort(); trainingGeneration.current++ }
  }, [])
  useEffect(() => {
    if (!trainingBusy) return
    const timer = setTimeout(() => { cancelTraining(); if (trainingLoading.current) { cancelUpload(); trainingLoading.current = false }; setTrainingError('Подготовка примера не завершилась. Текущая работа сохранена; повторите попытку.') }, 20000)
    return () => clearTimeout(timer)
  }, [trainingBusy])

  async function startTraining() {
    if (draftDirty.current || currentProjectDraft.current || pending || recovering || trainingBusy) return
    const generation = ++trainingGeneration.current
    const navigation = navigationGeneration.current
    const edits = trainingEdits.current
    const controller = new AbortController()
    trainingRequest.current = controller
    setTrainingBusy(true); setTrainingError('')
    let preparing = false
    try {
      let saved = sessionStorage.getItem('onboarding-training-request')
      if (!saved) {
        saved = JSON.stringify({ key: crypto.randomUUID(), body: { name: 'Учебный проект · знакомство с системой', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' } })
        sessionStorage.setItem('onboarding-training-request', saved)
      }
      const request = JSON.parse(saved) as { key: string; body: { name: string; timezone: string } }
      const created = await siteRequest<Project>('/projects', 'POST', request.body, controller.signal, request.key)
      if (!mounted.current || controller.signal.aborted || generation !== trainingGeneration.current || navigation !== navigationGeneration.current || edits !== trainingEdits.current || draftDirty.current || currentProjectDraft.current) throw new Error('training_canceled')
      setProjects(current => current.some(item => item.id === created.id) ? current : [...current, created])
      trainingOwner.current = created.id
      navigate(`/projects/${created.id}/new`, false, true, true)
      setTrainingProject(created.id)
      preparing = true
    } catch {
      if (generation === trainingGeneration.current) setTrainingError('Не удалось подготовить учебный проект. Повтор использует тот же ключ; текущая работа сохранена.')
      throw new Error('training_unavailable')
    } finally {
      if (generation === trainingGeneration.current && !preparing) setTrainingBusy(false)
    }
  }

  useEffect(() => {
    if (!trainingProject || projectId !== trainingProject || route !== 'new' || !analysisZoneId || recovering || choicesLoading) return
    const generation = trainingGeneration.current
    setTrainingProject('')
    trainingLoading.current = true
    void loadDemo('truck', true).finally(() => { trainingLoading.current = false; if (generation === trainingGeneration.current) setTrainingBusy(false) })
  }, [trainingProject, projectId, route, analysisZoneId, recovering, choicesLoading])

  function newAnalysis() { navigate(projectId ? '/new' : '/'); if (!projectId) requestAnimationFrame(() => { const field = document.getElementById('project-name'); const disclosure = field?.closest('details'); if (disclosure) disclosure.open = true; field?.focus() }) }

  function updateFrames(next: Frame[], keepTrainingRun = false) {
    trainingFrame.current = ''; setTrainingFrameId('')
    if (!keepTrainingRun) { trainingRun.current = ''; setTrainingRunId('') }
    framesRef.current = next
    setFrames(next)
    setSelectedDemo(null)
  }

  async function loadDemo(caseId: string, training = false) {
    const selected = demoCases.cases.find(item => item.id === caseId)
    if (!selected || pending || sending || recovering || busy.current || demoLoadingRef.current) return
    const generation = ++demoGeneration.current
    demoLoadingRef.current = true
    setDemoLoading(true)
    setDemoError('')
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout> | undefined
    try {
      await validationQueue.current
      const loaded = await Promise.race([Promise.all((training ? [selected.frames[1]] : selected.frames).map(async frame => {
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
      setScenario(training ? 'Учебный пример: техника на стройплощадке' : selected.scenario)
      if (!training) setArea(selected.observationArea)
      setPeriod(selected.period)
      setSelectedDemo(training ? null : selected)
      if (training) { trainingFrame.current = loaded[0].id; setTrainingFrameId(loaded[0].id) }
      setRemoved(null)
      setErrors({})
      setNotice(training ? 'Учебная фотография загружена. Время демонстрационное; запуск анализа требует отдельного нажатия.' : `Загружен демонстрационный пример: ${selected.label}. Три кадра можно изменить перед отправкой.`)
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
    const generation = demoGeneration.current
    const batch = Array.from(files)
    setValidating(true)
    const task = validationQueue.current.then(async () => {
      if (generation !== demoGeneration.current) return
      const next = [...framesRef.current]
      const originalCount = next.length
      const rejected: string[] = []
      for (const file of batch) {
        if (next.length >= MAX_FRAMES) { rejected.push('Можно добавить не более 8 кадров.'); break }
        const error = await validateImage(file)
        if (error) rejected.push(`${file.name}: ${error}`)
        else next.push({ id: crypto.randomUUID(), file })
      }
      if (!mounted.current || routeRef.current !== 'new' || generation !== demoGeneration.current) return
      updateFrames(next)
      if (next.length !== originalCount) setNotice(`Добавлено кадров: ${next.length - originalCount}. Всего ${next.length}.`)
      setErrors(current => ({ ...current, images: rejected.join(' ') || undefined }))
    }).catch(() => { if (generation !== demoGeneration.current) return; setErrors(current => ({ ...current, images: 'Не удалось проверить выбранные изображения. Повторите выбор файлов.' })) })
    validationQueue.current = task
    await task
    if (generation === demoGeneration.current && validationQueue.current === task) setValidating(false)
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
    if (!area.trim() || area.trim().length > 256) next.observation_area = 'Укажите участок наблюдения длиной до 256 символов.'
    if (!period || !validLocalPeriod(period)) next.period = 'Укажите существующие местные дату и время наблюдения.'
    if (!framesRef.current.length) next.images = 'Добавьте хотя бы один кадр JPEG или PNG.'
    if ((projectId && !analysisZoneId) || (planPickerOpen && (!analysisProjectId || !analysisZoneId || !analysisPlan?.revision_id))) next.submit = 'Выберите проект и участок с сохранённой ревизией плана либо отмените привязку.'
    if (analysisProjectId && framesRef.current.some(frame => !validLocalPeriod(captureTimes[frame.id] ?? period))) next.images = 'Укажите существующее время съёмки для каждого кадра.'
    return next
  }

  async function send(request: Pending) {
    if (busy.current || offline || foreignPending) return
    const navigation = navigationGeneration.current
    busy.current = true
    setSending(true)
    setErrors(current => ({ ...current, submit: undefined }))
    const controller = new AbortController()
    let timeout: ReturnType<typeof setTimeout> | undefined
    try {
      const { response, data } = await Promise.race([
        (async () => {
          const response = await fetch(request.endpoint.replace(/^\/runs\//, '/api/runs/'), {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': request.key, ...attributionHeaders() }, body: request.body,
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
      if (navigation !== navigationGeneration.current) return
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
        if (navigation !== navigationGeneration.current) return
        if (trainingFrame.current && framesRef.current.length === 1 && framesRef.current[0].id === trainingFrame.current && JSON.parse(request.body).project_id === trainingOwner.current) { trainingRun.current = data.run_id; setTrainingRunId(data.run_id) }
        navigate(JSON.parse(request.body).project_id ? `/projects/${JSON.parse(request.body).project_id}/runs/${data.run_id}` : `/runs/${data.run_id}`, true)
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
      if (navigation !== navigationGeneration.current) return
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
    if (busy.current || offline || recovering || demoLoading || foreignPending) return
    const generation = demoGeneration.current
    if (pending) { await send(pending); return }
    const approvedFrames = [...framesRef.current]
    busy.current = true
    await validationQueue.current
    if (generation !== demoGeneration.current) { busy.current = false; return }
    const framesChanged = approvedFrames.length !== framesRef.current.length
      || approvedFrames.some((frame, index) => frame.id !== framesRef.current[index].id)
    const next = validateForm()
    if (framesChanged) setCloudConsent(false)
    if (!cloudConsent || framesChanged) next.submit = 'Для анализа требуется согласие на обработку фотографий в Yandex AI Studio.'
    setErrors(next)
    if (Object.keys(next).length) { busy.current = false; queueMicrotask(() => summary.current?.focus()); return }
    setSending(true)
    try {
      const images: string[] = []
      for (const frame of approvedFrames) images.push(await base64(frame.file))
      if (generation !== demoGeneration.current) return
      const body = JSON.stringify({
        cloud_processing_consent: cloudConsent, intent, stage, ...(stage === "excavation" ? { stage_id: stage } : {}), scenario: scenario.trim(), observation_area: area.trim(),
        period: periodWithOffset(period), requested_classes: EQUIPMENT,
        ...(analysisProjectId && analysisZoneId ? { project_id: analysisProjectId, zone_id: analysisZoneId,
          ...(planPickerOpen && analysisPlan?.revision_id ? { plan_revision_id: analysisPlan.revision_id } : {}),
          capture_times: approvedFrames.map(frame => periodWithOffset(captureTimes[frame.id] ?? period)) } : {}),
        ...(images.length === 1 ? { image_base64: images[0] } : { images_base64: images }),
      })
      const request = { endpoint: images.length === 1 ? '/api/runs/single-image' : '/api/runs/series', body, key: crypto.randomUUID() }
      await storePending(request)
      setPending(request)
      if (generation !== demoGeneration.current) return
      busy.current = false
      await send(request)
    } catch {
      if (generation !== demoGeneration.current) return
      setErrors(current => ({ ...current, submit: 'Не удалось безопасно подготовить или сохранить запрос. Форма сохранена; повторите попытку.' }))
      queueMicrotask(() => summary.current?.focus())
    } finally {
      busy.current = false
      setSending(false)
    }
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main">К основному содержимому</a>
    <AppHeader projectId={projectId} projects={projects} projectName={project?.name} route={route} historyPath={historyPath.current} navigate={navigate} onNewAnalysis={newAnalysis} />
    <PublicSupport safe={!recovering && !pending && !draftDirty.current && !projectDraft} projectId={projectId} analysisId={route && /^[0-9a-f-]{36}$/i.test(route) ? route : undefined} start={newAnalysis} training={{ start: startTraining, busy: trainingBusy, ready: trainingReady && projectId === trainingOwner.current, allowed: !draftDirty.current && !projectDraft && !pending && !recovering, error: trainingError || (trainingReady ? '' : demoError), runId: projectId === trainingOwner.current && route === trainingRunId ? trainingRunId : undefined }} />
    <main id="main" className="page">
      {trainingReady && projectId === trainingOwner.current && route === 'new' && <p className="attention">Учебный пример: проверенная фотография из демонстрационного набора. Дата и время съёмки демонстрационные; их можно уточнить. Анализ запускается только кнопкой «Запустить анализ».</p>}
      {pending && route !== 'new' && <p className="attention">Сохранённая отправка требует восстановления. <a href={pendingProject ? `/projects/${pendingProject}/new` : '/new'} onClick={event => { event.preventDefault(); navigate(pendingProject ? `/projects/${pendingProject}/new` : '/new', false, false) }}>Вернуться к отправке</a></p>}
      {projectsError && <div className="error" role="alert">{projectsError} <button type="button" onClick={() => setProjectsAttempt(value => value + 1)}>Повторить загрузку проектов</button></div>}
      {projectId && projectsLoaded && !project ? <section className="panel"><h1 ref={pageHeading} tabIndex={-1}>Проект не найден</h1><a href="/" onClick={event => { event.preventDefault(); navigate('/') }}>Все проекты</a></section> : route === 'projects' ? <ProjectList onDraft={setProjectDraft} heading={pageHeading} projects={projects} loaded={projectsLoaded} navigate={navigate} onCreated={created => { setProjects(current => [...current, created]); navigate(`/projects/${created.id}`) }} /> : route === 'overview' ? <ProjectOverview key={projectId} projectId={projectId} projectName={project?.name} heading={pageHeading} navigate={navigate} /> : route === 'plan' ? <SiteWorkspace key={projectId} projectId={projectId} heading={pageHeading} onDirty={setPlanDirty} /> : route === 'signals' ? <SignalsPage key={projectId} projectId={projectId} heading={pageHeading} onOpenRun={id => navigate(`/runs/${id}`)} /> : route === 'history' ? <section className="history" aria-labelledby="history-heading" aria-busy={historyLoading || historyPageLoading}>
        <div className="page-intro"><p className="eyebrow">История</p><h1 ref={pageHeading} tabIndex={-1} id="history-heading">{projectId ? "Анализы проекта" : "Архив без проекта"}</h1>{historyTotal !== null && <p>Всего анализов: {historyTotal}.</p>}<p>Сохранённые анализы и их исходные данные.</p></div>
        {historyError && <div className="panel attention" role="alert">{historyError} <button type="button" className="secondary" onClick={() => setHistoryAttempt(value => value + 1)}>Повторить загрузку</button></div>}
        {historyLoading && !historyLoaded && <p role="status">Загружаем историю…</p>}
        {historyLoaded && !historyRuns.length && !historyError && <div className="panel"><p>Анализов пока нет.</p><a href="/new" onClick={event => { event.preventDefault(); navigate('/new') }}>Новый анализ</a></div>}
        {historyRuns.length > 0 && <ol className="history-list">{historyRuns.map(run => {
          const id = run.id ?? run.run_id
          const predecessor = run.retry_predecessor_id ?? run.retry_of_run_id
          const successor = run.retry_successor_id ?? run.successor_run_id
          return <li className="panel history-row" key={id}>
            <a className="history-link" href={`/runs/${id}`} onClick={event => { event.preventDefault(); navigate(`/runs/${id}`) }}>Открыть анализ</a>
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
      </section> : route === 'readiness' ? <ReadinessPage heading={pageHeading} onOpen={navigate} /> : route === 'provider-comparison' ? <ProviderComparisonPage heading={pageHeading} onOpen={navigate} /> : route === 'about' ? <About heading={pageHeading} returnPath={history.state?.aboutFromApp ? history.state.returnPath : '/'} onReturn={returnFromAbout} /> : route === null ? <section className="panel" aria-labelledby="not-found-heading"><h1 ref={pageHeading} tabIndex={-1} id="not-found-heading">Страница не найдена</h1><p>Проверьте адрес или откройте обзор этапов.</p></section> : route !== 'new' ? <section className="run-workspace" aria-labelledby="run-heading" aria-busy={runReading}>{visibleRunSnapshot && visibleRunSnapshot.state !== 'succeeded' && <RunPipeline run={visibleRunSnapshot} runId={route!} disconnected={offline || !!runError} />}{visibleRunSnapshot?.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome && <ObservationResult onOpen={navigate} run={visibleRunSnapshot} runId={route!} pageHeading={pageHeading} />}{visibleRunSnapshot?.state === 'succeeded' && <RunPipeline run={visibleRunSnapshot} runId={route!} disconnected={offline || !!runError} />}{visibleRunSnapshot && <StageConfirmation key={route} run={visibleRunSnapshot} runId={route!} />}{visibleRunSnapshot && <section className="panel"><h2>Этап по сохранённому плану</h2>{visibleRunSnapshot.plan_binding ? (visibleRunSnapshot.planned_works?.length ? <ul>{visibleRunSnapshot.planned_works.map((work, index) => <li key={index}>{work.title}: {work.stage_key ? STAGE_NAMES[work.stage_key] ?? work.stage_key : 'этап не указан'}; {new Date(work.starts_at).toLocaleString('ru-RU')} — {new Date(work.ends_at).toLocaleString('ru-RU')}</li>)}</ul> : <p>В выбранной версии плана нет работ.</p>) : <p>Этот анализ выполнен без сопоставления с планом. Добавленный позже план не меняет сохранённый результат.</p>}</section>}{visibleRunSnapshot?.plan_binding && <details className="panel run-plan-binding"><summary>Привязка к плану</summary><p>Участок <code>{visibleRunSnapshot.plan_binding.zone_id}</code>, ревизия <code>{visibleRunSnapshot.plan_binding.revision_id}</code>. Время кадров: {visibleRunSnapshot.plan_binding.capture_times.join(', ')}.</p></details>}<div className="panel run-header"><details className="run-meta" open={visibleRunSnapshot?.state !== 'succeeded' || !visibleRunSnapshot?.result_projection?.outcome || !!runError}><summary>{visibleRunSnapshot?.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome ? 'Технические сведения' : 'Данные анализа'}</summary><p className="eyebrow">{visibleRunSnapshot?.purpose === "comparison_campaign" ? "Доказательство сравнительной кампании" : "Анализ"}</p>{visibleRunSnapshot?.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome ? <h2 id="run-status-heading">Анализ завершён</h2> : <h1 ref={pageHeading} tabIndex={-1} id="run-heading">{runMissing ? 'Анализ не найден' : visibleRunSnapshot ? RUN_HEADINGS[visibleRunSnapshot.state] ?? 'Статус анализа неизвестен' : runChecked ? 'Статус анализа неизвестен' : 'Проверяем анализ…'}</h1>}<p>Номер анализа: <code>{route}</code></p>{(visibleRunSnapshot?.stage ?? visibleRunSnapshot?.context?.stage_id) === 'excavation' && <p>Этап строительства: <strong>Земляные работы котлована</strong></p>}{visibleRunSnapshot && <p>Состояние сервера: <strong>{RUN_STATES[visibleRunSnapshot.state] ?? 'Состояние доступно на сервере'}</strong></p>}{runError && <div className="attention"><p>{runError}</p><button type="button" className="secondary" disabled={runReading} onClick={() => { if (!runReading) { setRunReading(true); setRunReadAttempt(value => value + 1) } }}>{runReading ? 'Проверяем статус…' : 'Проверить статус'}</button></div>}<p role="status" className="sr-only">{runError || runAnnouncement}</p>{(visibleRunSnapshot?.retry_predecessor_id ?? visibleRunSnapshot?.retry_of_run_id) && <p>Повтор анализа <a href={`/runs/${(visibleRunSnapshot.retry_predecessor_id ?? visibleRunSnapshot.retry_of_run_id)}`} onClick={event => { event.preventDefault(); navigate(`/runs/${(visibleRunSnapshot.retry_predecessor_id ?? visibleRunSnapshot.retry_of_run_id)}`) }}>{(visibleRunSnapshot.retry_predecessor_id ?? visibleRunSnapshot.retry_of_run_id)}</a></p>}{(visibleRunSnapshot?.retry_successor_id ?? visibleRunSnapshot?.successor_run_id) && <p>Следующий анализ <a href={`/runs/${(visibleRunSnapshot.retry_successor_id ?? visibleRunSnapshot.successor_run_id)}`} onClick={event => { event.preventDefault(); navigate(`/runs/${(visibleRunSnapshot.retry_successor_id ?? visibleRunSnapshot.successor_run_id)}`) }}>{(visibleRunSnapshot.retry_successor_id ?? visibleRunSnapshot.successor_run_id)}</a></p>}{visibleRunSnapshot?.retry_eligible && <p>Повтор использует текущий профиль <code>{visibleRunSnapshot.retry_profile_id}</code>, ревизия допуска {visibleRunSnapshot.retry_authorization_revision}.{visibleRunSnapshot.profile_id !== visibleRunSnapshot.retry_profile_id && <> Исходный анализ использовал профиль <code>{visibleRunSnapshot.profile_id}</code>.</>}</p>}{visibleRunSnapshot?.retry_eligible && <button type="button" className="primary" disabled={retrying || offline} onClick={() => void retryRun()}>{retrying ? 'Создаём повтор…' : 'Повторить анализ'}</button>}{retryError && <p className="error" role="alert">{retryError}</p>}</details></div>{visibleRunSnapshot && !(visibleRunSnapshot.state === 'succeeded' && visibleRunSnapshot.result_projection?.outcome) && <ObservationResult onOpen={navigate} run={visibleRunSnapshot} runId={route!} />}</section> : <NewAnalysisPage>
        <div className="page-intro new-analysis-intro"><h1 ref={pageHeading} tabIndex={-1}>Новый анализ</h1><p>Подготовьте наблюдение за техникой: выберите цель, укажите контекст и добавьте кадры в порядке съёмки. Привязка сохранится в анализе и его повторе.</p>{unsupportedStageNotice && <p className="attention">Выбранный этап не настроен в прототипе. Выберите доступный этап и цель анализа.</p>}</div>
        <details className="demo-examples panel" aria-busy={demoLoading}>
          <summary id="demo-heading">Включённые примеры</summary>
          <p>Загрузите три кадра в редактируемую форму. Это примеры разработки из архива организаторов, не оценка готовности распознавания.</p>
          <div className="upload-actions">{demoCases.cases.map(item => <button key={item.id} type="button" className="secondary" disabled={!!pending || recovering || sending || validating || demoLoading || choicesLoading} onClick={() => void loadDemo(item.id)}>{item.label}</button>)}</div>
          {demoLoading && <p role="status">Загружаем и проверяем кадры примера…</p>}
          {demoError && <p role="alert" className="error">{demoError}</p>}
          {pending && <p>Пока предыдущая отправка требует восстановления, загрузка примера недоступна. Сохранённые данные и ключ отправки не изменены.</p>}
          {selectedDemo && <div className="rule-context"><p>Источник: архив организаторов, группа <code>{selectedDemo.sourceGroup}</code>; порядок кадров соответствует архиву.</p><p>Отмеченная на кадрах дата: {selectedDemo.frames.map(frame => frame.displayedDate ?? 'не указана').join(', ')}. В исходном примере время 12:00 условное; проверьте период перед отправкой.</p><p>Участок наблюдения заявлена для этой серии; изображения не подтверждают её границы или отсутствие техники на всей площадке.</p></div>}
        </details>
        <div>{workspaceReadError && <p role="alert" className="error">{workspaceReadError} <button type="button" onClick={() => setWorkspaceReadAttempt(value => value + 1)}>Повторить загрузку участка</button></p>}</div><form className="new-analysis-form" onChange={() => setUploadDirty(true)} onSubmit={submit} noValidate aria-busy={sending}>
          <div className="form-grid"><section className="panel" aria-labelledby="images-heading"><h2 id="images-heading">Кадры наблюдения</h2><p className="muted">Выберите одно изображение JPEG или PNG либо серию из 2–8 изображений. Каждый файл — до 16 МБ и 40 миллионов пикселей. Порядок кадров влияет на анализ.</p><UploadZone onFiles={files => void addFiles(files)} onCamera={() => void openCamera()} disabled={!!pending || sending || validating || demoLoading} cameraDisabled={!!pending || sending || validating || demoLoading || cameraOpen || cameraDenied} invalid={!!errors.images} describedBy={errors.images ? 'images-error' : undefined} />{errors.images && <p id="images-error" className="error" role="alert">{errors.images}</p>}{cameraOpen && <div className="camera"><video ref={cameraVideo} autoPlay playsInline muted aria-label="Изображение с камеры" /><div className="upload-actions"><button type="button" onClick={capture}>Сделать снимок</button><button className="secondary" type="button" onClick={closeCamera}>Закрыть камеру</button></div></div>}
          <h3>Порядок кадров</h3>{frames.length ? <ol className="manifest">{frames.map((frame, index) => <li key={frame.id} className="frame"><FramePreview file={frame.file} ordinal={index + 1} /><div><strong>Кадр {index + 1}</strong><span className="file-name">{frame.file.name}</span><small>{(frame.file.size / 1_000_000).toFixed(1)} МБ</small>{analysisProjectId && <label>Время съёмки<input disabled={!!pending || sending || validating} type="datetime-local" value={captureTimes[frame.id] ?? period} onChange={event => setCaptureTimes(current => ({ ...current, [frame.id]: event.target.value }))} /></label>}</div><div className="frame-actions"><button type="button" className="secondary" onClick={() => move(index, -1)} disabled={index === 0 || !!pending || sending || validating || demoLoading} aria-label={`Выше: ${frame.file.name}, кадр ${index + 1}`}>Выше</button><button type="button" className="secondary" onClick={() => move(index, 1)} disabled={index === frames.length - 1 || !!pending || sending || validating || demoLoading} aria-label={`Ниже: ${frame.file.name}, кадр ${index + 1}`}>Ниже</button><button type="button" className="secondary" onClick={() => remove(index)} disabled={!!pending || sending || validating || demoLoading} aria-label={`Удалить: ${frame.file.name}, кадр ${index + 1}`}>Удалить</button></div></li>)}</ol> : <p className="empty">Кадры ещё не выбраны.</p>}{removed && <div className="undo"><span>{removed.frame.file.name} удалён.</span><button className="secondary" type="button" onClick={restore} disabled={!!pending || sending || validating || demoLoading || frames.length >= MAX_FRAMES}>Вернуть</button></div>}<p role="status" className="sr-only">{notice}</p></section><section className="panel" aria-labelledby="context-heading"><h2 id="context-heading">Фотографии участка</h2>{projectId ? <fieldset disabled={!!pending || sending || validating || demoLoading}><p>Проект: <strong>{project?.name ?? 'Загрузка…'}</strong></p><label className="field" htmlFor="analysis-zone">Участок<select aria-label="Участок" id="analysis-zone" value={analysisZoneId} onChange={event => setAnalysisZoneId(event.target.value)}>{analysisZones.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><p>Дополнительный участок можно добавить в разделе «План».</p><label className="field" htmlFor="period">Дата и время наблюдения<input id="period" type="datetime-local" value={period} onChange={event => setPeriod(event.target.value)} aria-invalid={!!errors.period} aria-describedby={errors.period ? 'period-error' : undefined} /></label>{errors.period && <p id="period-error" className="error">{errors.period}</p>}<p>Для каждого кадра можно уточнить время съёмки. Время вводится по часовому поясу устройства.</p>{analysisPlan?.revision_id ? <label><input type="checkbox" checked={planPickerOpen} onChange={event => setPlanPickerOpen(event.target.checked)} /> Сопоставить с сохранённым планом</label> : <p>Плана пока нет. Можно анализировать фотографии и добавить план позже.</p>}</fieldset> : <><h2 id="context-heading">Контекст наблюдения</h2><fieldset disabled={!!pending || sending || validating || choicesLoading || demoLoading}><div className="field"><label htmlFor="stage">Этап</label><select id="stage" value={stage} onChange={event => { const selected = event.target.value; setStage(selected);  }}>{choices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}</select></div><p>DeepSeek распознаёт технику и анализирует контекст. Исторические правила доступны только в сохранённых результатах.</p>{!choicesLoading && !choices.length && <p className="error">Не удалось загрузить настройки этапов. <button type="button" className="secondary" onClick={() => setChoicesAttempt(value => value + 1)}>Повторить загрузку настроек</button></p>}<div className="field"><label htmlFor="scenario">Сценарий</label><input id="scenario" value={scenario} onChange={event => setScenario(event.target.value)} aria-invalid={!!errors.scenario} aria-describedby={errors.scenario ? 'scenario-error' : undefined} maxLength={256} /><p className="hint">Например, наблюдение за земляными работами.</p>{errors.scenario && <p id="scenario-error" className="error">{errors.scenario}</p>}</div><div className="field"><label htmlFor="area">Участок наблюдения</label><input id="area" value={area} readOnly={!!analysisZoneId} onChange={event => setArea(event.target.value)} aria-invalid={!!errors.observation_area} aria-describedby={errors.observation_area ? 'area-error' : undefined} maxLength={256} /><p className="hint">{analysisZoneId ? 'Используется название выбранного участка плана.' : 'Укажите конкретный участок, к которому относятся кадры.'}</p>{errors.observation_area && <p id="area-error" className="error">{errors.observation_area}</p>}</div><div className="field"><label htmlFor="period">Дата и время наблюдения</label><input id="period" type="datetime-local" value={period} onChange={event => setPeriod(event.target.value)} aria-invalid={!!errors.period} aria-describedby={errors.period ? 'period-error' : undefined} />{errors.period && <p id="period-error" className="error">{errors.period}</p>}</div>{!planPickerOpen ? <button type="button" className="secondary" onClick={() => setPlanPickerOpen(true)}>Привязать к плану</button> : <><div className="field"><label htmlFor="analysis-project">Проект плана</label><select id="analysis-project" value={analysisProjectId} onChange={event => setAnalysisProjectId(event.target.value)}><option value="">Без привязки к плану</option>{analysisProjects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>{analysisProjectId && <div className="field"><label htmlFor="analysis-zone">Участок плана</label><select aria-label="Участок" id="analysis-zone" value={analysisZoneId} onChange={event => setAnalysisZoneId(event.target.value)}><option value="">Выберите участок</option>{analysisZones.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>}{analysisZoneId && <p>Ревизия плана: {analysisPlan?.revision_number ?? 'не создана'}. {analysisPlan?.revision_id && <code>{analysisPlan.revision_id}</code>}</p>}<button type="button" className="secondary" onClick={() => { setPlanPickerOpen(false); setAnalysisProjectId('') }}>Без привязки к плану</button></>}</fieldset><p className="context-summary">Участок: {area || 'не указана'}. Период: {period || 'не указан'}.</p></>}</section>
          </div>
          <section className="submit-panel"><label><input id="cloud-consent" type="checkbox" checked={cloudConsent} disabled={!!pending || sending || validating} onChange={event => setCloudConsent(event.target.checked)} /> Разрешаю отправить эти фотографии и контекст анализа в Yandex AI Studio (DeepSeek) для облачной обработки.</label><p>Фотографии передаются после запуска. Модель не подтверждает нарушения; результат требует проверки человеком.</p><div ref={summary} tabIndex={-1} className="error-summary" role={Object.values(errors).some(Boolean) ? 'alert' : undefined}>{Object.values(errors).some(Boolean) && <><strong>Проверьте данные</strong><ul>{Object.entries(errors).filter(([, message]) => message).map(([key, message]) => <li key={key}><a href={`#${key === 'observation_area' ? 'area' : key === 'images' ? 'images-heading' : key === 'submit' ? 'submit-action' : key}`}>{message}</a></li>)}</ul></>}</div>{offline && <p className="offline" role="status">Нет соединения. Изображения останутся на этом устройстве до обновления страницы.</p>}{foreignPending && <p className="attention">Сначала восстановите отправку в исходном проекте. <a href={pendingProject ? `/projects/${pendingProject}/new` : '/new'} onClick={event => { event.preventDefault(); navigate(pendingProject ? `/projects/${pendingProject}/new` : '/new', false, false) }}>Вернуться к отправке</a></p>}{pending && !foreignPending && <p className="attention">Результат предыдущей отправки неизвестен. Повторный запрос использует те же данные и ключ.</p>}<button id="submit-action" className="primary" type="submit" disabled={foreignPending || sending || offline || recovering || demoLoading || (!pending && (choicesLoading || !choices.length))}>{sending ? 'Создаём анализ…' : pending && !foreignPending ? 'Повторить отправку' : 'Запустить анализ'}</button></section>
        </form>
      </NewAnalysisPage>}
    </main>
  </div>
}
