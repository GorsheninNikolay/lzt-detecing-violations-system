import { EvidenceViewer, SourceImage, makeResultFrames, type Input, type Observation, type DetectedObject, type NativeEvidence, type ProfileSnapshot } from './EvidenceViewer'
import { useEffect, useState, type RefObject } from 'react'
import './signals.css'

type SignalState = 'new' | 'in_progress' | 'closed'
type Signal = {
  id: string
  run_id: string | null
  zone_id: string
  revision_id: string | null
  work_entry_id: string | null
  kind: string
  state: SignalState
  basis: Record<string, unknown>
  comment: string
  created_at: string
  project_name?: string | null
  zone_name?: string | null
  plan_revision_number?: number | null
  work_title?: string | null
  preview?: { input_id: string; ordinal: number; artifact_id: string | null } | null
}
type PlanEntry = {
  id: string
  starts_at: string
  ends_at: string
  state: 'planned' | 'active' | 'completed'
  stage_key: string | null
  expected_equipment: string[]
  allowed_equipment: string[]
  excluded_equipment: string[]
}
type ZonePlan = { revision_id?: string; revision_number: number; entries: PlanEntry[] }
type Run = { state: string; inputs?: Input[]; observations?: Observation[]; objects?: DetectedObject[]; native_evidence_by_frame?: NativeEvidence[]; context?: {period?:string}; profile_snapshot?: ProfileSnapshot; result_projection?: { outcome?: string; recommendation?: string | null; frames?:Observation[]; series?:{usable_input_ids?:string[]}; context?:{period?:string} } | null }
type SignalContext = { signalId?: string; run?: Run; plan?: ZonePlan; runError?: string; planError?: string }
type Draft = { state: SignalState; comment: string }

const STATES: Record<SignalState, string> = { new: 'Новый', in_progress: 'В работе', closed: 'Закрыт' }
const KINDS: Record<string, string> = {
  possible_idle: 'Возможный простой', visible_process_risk: 'Возможный риск организации работ', visible_safety_risk: 'Возможный риск безопасности',
  expected_equipment_missing: 'Ожидаемая техника не обнаружена',
  equipment_not_planned: 'Техника не предусмотрена текущей операцией',
  stage_plan_mismatch: 'Этап расходится с планом',
  completion_unconfirmed: 'Завершение не подтверждено',
  insufficient_observations: 'Недостаточно наблюдений',
}
const EQUIPMENT: Record<string, string> = { excavator: 'Экскаватор', dump_truck: 'Самосвал', road_roller: 'Каток', truck_mounted_crane: 'Кран-манипулятор', concrete_mixer_truck: 'Автобетоносмеситель', bulldozer: 'Бульдозер', truck: 'Грузовик', mobile_crane: 'Автокран' }
const STAGES: Record<string, string> = { excavation: 'Земляные работы', concreting: 'Бетонные работы', roadwork: 'Дорожные работы' }
const OUTCOMES: Record<string, string> = { observations_only: 'Только наблюдения', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось', no_check: 'Проверка не запрошена', check_requested: 'Рекомендована проверка человеком' }
const PLAN_STATES: Record<PlanEntry['state'], string> = { planned: 'Запланирована', active: 'Активна', completed: 'Завершена' }
const REASONS: Record<string, string> = {
  'Expected equipment was not detected in the assessable series.': 'Ожидаемая техника не обнаружена на пригодных кадрах серии.',
  'All concurrent active operations explicitly exclude this equipment.': 'Все одновременно активные работы явно исключают эту технику.',
  'At least three assessable frames of the active zone are required.': 'Для сопоставления нужны минимум три пригодных кадра активного участка.',
}
const RECOMMENDATIONS: Record<string, string> = {
  'Check completion with the site team.': 'Проверьте завершение работы с командой площадки.',
  'Review the active zone plan.': 'Проверьте план активных работ участка.',
}

const ACTIONS: Record<string, {explanation:string;action:string}> = {
  expected_equipment_missing: {explanation:'Ожидаемая по плану техника не обнаружена на пригодных кадрах. Это не доказывает её отсутствие на участке.',action:'Сверьте технику с текущей работой и проверьте участок или добавьте свежие кадры.'},
  equipment_not_planned: {explanation:'Обнаруженная техника явно исключена всеми активными работами сохранённого плана.',action:'Уточните назначение техники у команды площадки и проверьте актуальность плана.'},
  stage_plan_mismatch: {explanation:'Этап, подтверждённый человеком, расходится с этапами активных работ сохранённого плана.',action:'Сверьте фактическую работу с планом и уточните расхождение с командой.'},
  completion_unconfirmed: {explanation:'Плановый срок прошёл, но завершение работы не подтверждено. Это не доказательство просрочки.',action:'Уточните завершение у команды площадки и обновите состояние работы в плане.'},
  insufficient_observations: {explanation:'Пригодных наблюдений недостаточно для сопоставления с планом.',action:'Добавьте минимум три пригодных кадра одного участка с достоверным временем съёмки.'},
}
function signalTitle(signal:Signal){return `${KINDS[signal.kind] ?? signal.kind}${signal.basis?.class_name ? `: ${EQUIPMENT[String(signal.basis.class_name)] ?? signal.basis.class_name}` : ''}`}

function SignalPhoto({signal,run,loading,error,onRetry}:{signal:Signal;run?:Run;loading:boolean;error?:string;onRetry:()=>void}){
  const complete=run?.state==='succeeded' && !!run.result_projection?.outcome
  const projection=run?.result_projection
  const frames=makeResultFrames(complete?projection?.frames??[]:run?.observations??[],(run?.inputs??[]).map(input=>input.input_id===signal.preview?.input_id?{...signal.preview,...input,artifact_id:input.artifact_id??signal.preview.artifact_id}:input),complete?projection?.series?.usable_input_ids:undefined,complete)
  if(!frames.length && signal.preview)frames.push({ ...signal.preview,sha256:null,usable:null,observations:[] })
  const [activeId,setActiveId]=useState<string|null>(signal.preview?.input_id??null)
  const [viewer,setViewer]=useState(false)
  const selected=Math.max(0,frames.findIndex(frame=>frame.input_id===activeId)),frame=frames[selected]
  const supporting=Array.isArray(signal.basis.supporting_input_ids)?signal.basis.supporting_input_ids:[]
  const readState=signal.run_id&&(error?<p role="alert">Фотографии анализа не удалось загрузить. <button className="secondary" onClick={onRetry}>Повторить загрузку фотографий</button></p>:loading?<p role="status">Загружаем фотографии анализа…</p>:null)
  if(!signal.run_id || !frame)return readState || <p>Связанных фотографий нет. Основание — сохранённая ревизия плана ниже.</p>
  return <section className="signal-photo" aria-label="Фотографии сигнала">{readState}<SourceImage runId={signal.run_id} artifactId={frame.artifact_id} label={`Кадр ${frame.ordinal+1}`} description={supporting.includes(frame.input_id)?'Поддерживающий кадр':'Кадр анализа'} objects={run?.objects?.filter(item=>item.input_id===frame.input_id)} showBoxes />
    <button className="secondary" onClick={()=>setViewer(true)}>Открыть фото</button><p>{supporting.includes(frame.input_id)?'Поддерживающий кадр':'Кадр анализа'} · {frame.ordinal+1} из {frames.length}</p>
    {frames.length>1&&<div className="signal-frame-switcher">{frames.map(frame=><button key={frame.input_id} className="secondary" aria-pressed={frame.input_id===frames[selected].input_id} onClick={()=>setActiveId(frame.input_id)}>Кадр {frame.ordinal+1}{supporting.includes(frame.input_id)?' · поддерживающий':''}</button>)}</div>}
    {viewer&&<EvidenceViewer runId={signal.run_id} frames={frames} native={run?.native_evidence_by_frame??[]} objects={run?.objects??[]} profile={run?.profile_snapshot} context={complete?projection?.context??run?.context:run?.context} showBoxes selected={selected} onSelect={index=>setActiveId(frames[index].input_id)} onClose={()=>setViewer(false)}/>}
  </section>
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
}

async function readJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error('request_failed')
  return response.json() as Promise<T>
}

function useCompactLayout() {
  const [compact, setCompact] = useState(() => window.innerWidth < 768)
  useEffect(() => {
    const update = () => setCompact(window.innerWidth < 768)
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])
  return compact
}

function SignalPreview({ signal }: { signal: Signal }) {
  const artifactId = signal.preview?.artifact_id
  const [loaded, setLoaded] = useState<{ id: string; url: string } | null>(null)
  useEffect(() => {
    if (!signal.run_id || !artifactId) return
    const controller = new AbortController()
    let objectUrl: string | null = null
    void fetch(`/api/runs/${signal.run_id}/artifacts/${artifactId}`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('artifact_unavailable')
        const blob = await response.blob()
        if (controller.signal.aborted) return
        objectUrl = URL.createObjectURL(blob)
        setLoaded({ id: artifactId, url: objectUrl })
      }).catch(() => { if (!controller.signal.aborted) setLoaded(null) })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [signal.run_id, artifactId])
  const supporting = Array.isArray(signal.basis?.supporting_input_ids) && signal.basis.supporting_input_ids.includes(signal.preview?.input_id)
  const caption = supporting ? 'Поддерживающий кадр' : 'Кадр анализа'
  return <span className="signals-preview">{loaded && loaded.id === artifactId ? <img src={loaded.url} alt={`${caption} ${Number(signal.preview?.ordinal ?? 0) + 1}`} /> : <span aria-hidden="true" className="signals-preview-empty">{signal.run_id ? 'Нет кадра' : 'План'}</span>}{signal.preview && <span className="signals-preview-caption">{caption}</span>}</span>
}

function SignalBasis({ signal }: { signal: Signal }) {
  const basis = signal.basis ?? {}
  const risk = basis.risk as { text?: string; impact?: string; recommended_check?: string; limitations?: string[] } | undefined
  const supporting = Array.isArray(basis.supporting_input_ids) ? basis.supporting_input_ids : []
  return <section className="signals-detail-section" aria-labelledby={`signal-basis-${signal.id}`}>
    <h3 id={`signal-basis-${signal.id}`}>Основание</h3>
    {risk && <><p>{risk.text}</p><p>Возможное влияние: {risk.impact}</p><p>Проверить: {risk.recommended_check}</p>{risk.limitations?.map((item, index) => <p key={index}>{item}</p>)}</>}
    {Boolean(basis.class_name) && <p>Техника: <strong>{EQUIPMENT[String(basis.class_name)] ?? String(basis.class_name)}</strong>.</p>}
    {Boolean(basis.due_at) && <p>Плановый срок: <time dateTime={String(basis.due_at)}>{formatTime(String(basis.due_at))}</time>.</p>}
    {Boolean(basis.confirmed_stage) && <p>Подтверждённый этап: {STAGES[String(basis.confirmed_stage)] ?? String(basis.confirmed_stage)}.</p>}
    {Array.isArray(basis.planned_stages) && <p>Этапы активных работ в плане: {basis.planned_stages.map(value => STAGES[String(value)] ?? String(value)).join(', ') || 'не указаны'}.</p>}
    {Boolean(basis.reason) && <p>{REASONS[String(basis.reason)] ?? String(basis.reason)}</p>}
    {supporting.length > 0 && <p>Поддерживающих кадров в серии: {supporting.length}.</p>}
    {Boolean(basis.recommendation) && <p className="signals-recommendation"><strong>Рекомендация:</strong> {RECOMMENDATIONS[String(basis.recommendation)] ?? String(basis.recommendation)}</p>}
    {!signal.run_id && <p>Сигнал сформирован по сроку плана. Связанных кадров нет.</p>}
    <details><summary>Технические сведения основания</summary><pre>{JSON.stringify(basis, null, 2)}</pre></details>
  </section>
}

function SignalDetail({ signal, context, contextLoading, draft, busy, saveError, onDraft, onSave, onOpenRun, onRetry }: {
  signal: Signal
  context: SignalContext
  contextLoading: boolean
  draft: Draft
  busy: boolean
  saveError: string
  onDraft: (draft: Draft) => void
  onSave: () => void
  onOpenRun: (id: string) => void
  onRetry: () => void
}) {
  const currentComment = signal.comment ?? ''
  return <article className="signals-detail" id={`signal-detail-${signal.id}`} aria-labelledby={`signal-title-${signal.id}`} aria-busy={contextLoading}>
    <div className="signals-detail-title"><h2 id={`signal-title-${signal.id}`}>{signalTitle(signal)}</h2><span className={`signals-state signals-state-${signal.state}`}>{STATES[signal.state]}</span></div>
    <p className="signals-detail-place">{[signal.project_name, signal.zone_name].filter(Boolean).join(' · ') || `Участок ${signal.zone_id}`}</p>
    <p className="signals-detail-date"><time dateTime={signal.created_at}>{formatTime(signal.created_at)}</time></p>
    <p>{ACTIONS[signal.kind]?.explanation}</p><p className="signals-recommendation"><strong>Следующее действие:</strong> {ACTIONS[signal.kind]?.action ?? 'Проверьте основание сигнала.'}</p>
    <SignalPhoto key={signal.id} signal={signal} run={context.run} loading={contextLoading} error={context.runError} onRetry={onRetry}/>
    {(context.planError||context.runError)&&<button className="secondary" onClick={onRetry}>Повторить загрузку плана и анализа</button>}
    <details><summary>Полное основание сигнала</summary><SignalBasis signal={signal} /></details>
    <section className="signals-detail-section" aria-labelledby={`signal-plan-${signal.id}`}>
      <h3 id={`signal-plan-${signal.id}`}>План на момент сигнала</h3>
      <p>{!signal.revision_id ? 'План не привязан. ' : ''}Ревизия {signal.plan_revision_number ?? 'не указана в списке'}{signal.work_title ? ` · ${signal.work_title}` : ''}</p>
      {contextLoading && <p role="status">Загружаем план и анализ…</p>}
      {context.planError && <p className="error" role="alert">{context.planError}</p>}
      {context.plan && <p>{signal.work_title ?? 'Активные работы'}: {context.plan.entries.filter(entry=>!signal.work_entry_id||entry.id===signal.work_entry_id).map(entry=>`${PLAN_STATES[entry.state]} · ${entry.stage_key?STAGES[entry.stage_key]??entry.stage_key:'этап не указан'} · ${formatTime(entry.starts_at)} — ${formatTime(entry.ends_at)}${entry.expected_equipment?.length ? ` · ожидается ${entry.expected_equipment.map(value=>EQUIPMENT[value]??value).join(', ')}`:''}${entry.excluded_equipment?.length ? ` · явно не предусмотрено ${entry.excluded_equipment.map(value=>EQUIPMENT[value]??value).join(', ')}`:''}`).join('; ')||'Работа в сохранённой ревизии отсутствует.'}</p>}
      {context.plan && <details><summary>Полная сохранённая ревизия плана</summary><div className="signals-plan-entries">{context.plan.entries.length ? context.plan.entries.map((entry, index) => <div key={entry.id} className="signals-plan-entry"><strong>{entry.id === signal.work_entry_id && signal.work_title ? signal.work_title : `Работа ${index + 1}`}</strong><span>{PLAN_STATES[entry.state] ?? entry.state}{entry.stage_key ? ` · ${STAGES[entry.stage_key] ?? entry.stage_key}` : ''}</span><span><time dateTime={entry.starts_at}>{formatTime(entry.starts_at)}</time> — <time dateTime={entry.ends_at}>{formatTime(entry.ends_at)}</time></span>{([['expected_equipment','Ожидается'],['allowed_equipment','Допускается'],['excluded_equipment','Явно не предусмотрено']] as const).map(([field,label])=><span key={field}>{label}: {entry[field]?.map(value=>EQUIPMENT[value]??value).join(', ')||'не указано'}</span>)}</div>) : <p>В сохранённой ревизии нет работ.</p>}</div></details>}
    </section>
    <details className="signals-detail-section"><summary>Связанный анализ</summary>
      <h3 id={`signal-run-${signal.id}`}>Связанный анализ</h3>
      {signal.run_id ? <><a href={`/runs/${signal.run_id}`} onClick={event => { event.preventDefault(); onOpenRun(signal.run_id!) }}>Открыть анализ и исходные кадры</a>{context.runError && <p className="error" role="alert">{context.runError}</p>}{context.run && <p>Итог: {context.run.result_projection?.outcome ? OUTCOMES[context.run.result_projection.outcome] ?? context.run.result_projection.outcome : 'анализ не завершён'}. Кадров: {context.run.inputs?.length ?? 0}.</p>}</> : <p>Анализ не связан. Кадров нет.</p>}
    </details>
    <section className="signals-detail-section signals-review" aria-labelledby={`signal-review-${signal.id}`}>
      <h3 id={`signal-review-${signal.id}`}>Ручная обработка</h3>
      {signal.state === 'closed' && <p className="signals-caution">Закрыт означает завершение ручной обработки, а не подтверждение безопасности.</p>}
      <div className="field"><label htmlFor={`signal-state-${signal.id}`}>Состояние</label><select id={`signal-state-${signal.id}`} value={draft.state} disabled={busy} onChange={event => onDraft({ ...draft, state: event.target.value as SignalState })}>{Object.entries(STATES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
      <div className="field"><label htmlFor={`signal-comment-${signal.id}`}>Комментарий</label><textarea id={`signal-comment-${signal.id}`} maxLength={2000} value={draft.comment} disabled={busy} onChange={event => onDraft({ ...draft, comment: event.target.value })} /></div>
      <button type="button" className="primary" disabled={busy || (draft.state === signal.state && draft.comment === currentComment)} onClick={onSave}>{busy ? 'Сохраняем…' : 'Сохранить'}</button>
      {saveError && <p className="error" role="alert">{saveError}</p>}
    </section>
    <details className="signals-ids"><summary>Идентификаторы</summary><p>Сигнал: <code>{signal.id}</code></p><p>Участок: <code>{signal.zone_id}</code></p><p>Ревизия: <code>{signal.revision_id}</code></p></details>
  </article>
}

export default function SignalsPage({ heading, onOpenRun, projectId }: { projectId?: string; heading: RefObject<HTMLHeadingElement | null>; onOpenRun: (id: string) => void }) {
  const [filter, setFilter] = useState('')
  const [signals, setSignals] = useState<Signal[] | null>(null)
  const [newCount, setNewCount] = useState(0)
  const [summary,setSummary]=useState<{open_count:number;attention_count:number;insufficient_data_count:number}|null>(null)
  const [contextAttempt,setContextAttempt]=useState(0)
  const [visibleCount, setVisibleCount] = useState(20)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [refresh, setRefresh] = useState(0)
  const [listError, setListError] = useState('')
  const [listLoading, setListLoading] = useState(false)
  const [context, setContext] = useState<SignalContext>({})
  const [contextLoading, setContextLoading] = useState(false)
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [saveErrors, setSaveErrors] = useState<Record<string, string>>({})
  const compact = useCompactLayout()
  const selected = signals?.find(item => item.id === selectedId) ?? null

  useEffect(() => {
    const controller = new AbortController()
    setListLoading(true)
    void readJson<{ new_count: number; summary?: {open_count:number;attention_count:number;insufficient_data_count:number}; signals: Signal[] }>(`/api/signals${projectId ? `?project_id=${projectId}${filter ? `&state=${filter}` : ''}` : filter ? `?state=${filter}` : ''}`, controller.signal)
      .then(data => {
        if (controller.signal.aborted) return
        setSignals(data.signals)
        setNewCount(data.new_count)
        setSummary(data.summary ?? null)
        setSelectedId(current => data.signals.some(item => item.id === current) ? current : data.signals[0]?.id ?? null)
        setListError('')
      }).catch(() => { if (!controller.signal.aborted) setListError('Не удалось загрузить сигналы.') })
      .finally(() => { if (!controller.signal.aborted) setListLoading(false) })
    return () => controller.abort()
  }, [filter, refresh, projectId])

  useEffect(() => {
    if (!selected) { setContext({}); setContextLoading(false); return }
    const controller = new AbortController()
    setContext({ signalId: selected.id })
    setContextLoading(true)
    const runRead = selected.run_id
      ? readJson<Run>(`/api/runs/${selected.run_id}`, controller.signal)
      : Promise.resolve(undefined)
    const planRead = Number.isInteger(selected.plan_revision_number) && Number(selected.plan_revision_number) > 0
      ? readJson<ZonePlan>(`/api/zones/${selected.zone_id}/plan?revision=${selected.plan_revision_number}`, controller.signal)
      : Promise.resolve(undefined)
    void Promise.allSettled([runRead, planRead]).then(([runResult, planResult]) => {
      if (controller.signal.aborted) return
      const plan = planResult.status === 'fulfilled' ? planResult.value : undefined
      setContext({
        signalId: selected.id,
        run: runResult.status === 'fulfilled' ? runResult.value : undefined,
        runError: runResult.status === 'rejected' ? 'Не удалось загрузить связанный анализ.' : undefined,
        plan: plan?.revision_id === selected.revision_id ? plan : undefined,
        planError: !selected.revision_id ? undefined : planResult.status === 'rejected' ? 'Не удалось загрузить сохранённую ревизию плана.'
          : !selected.plan_revision_number ? 'Номер сохранённой ревизии недоступен.'
            : plan?.revision_id !== selected.revision_id ? 'Полученная ревизия плана не совпадает с сигналом.' : undefined,
      })
      setContextLoading(false)
    })
    return () => controller.abort()
  }, [selected?.id, selected?.run_id, selected?.revision_id, selected?.plan_revision_number, selected?.zone_id, contextAttempt])

  const save = (signal: Signal) => {
    const draft = drafts[signal.id] ?? { state: signal.state, comment: signal.comment ?? '' }
    setSaving(current => ({ ...current, [signal.id]: true }))
    setSaveErrors(current => ({ ...current, [signal.id]: '' }))
    void fetch(`/api/signals/${signal.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft) })
      .then(async response => {
        if (!response.ok) throw new Error('save_failed')
        const saved = await response.json() as Draft
        setDrafts(current => ({ ...current, [signal.id]: { state: saved.state, comment: saved.comment } }))
        setRefresh(value => value + 1)
      }).catch(() => setSaveErrors(current => ({ ...current, [signal.id]: 'Не удалось сохранить сигнал. Комментарий остался в черновике.' })))
      .finally(() => setSaving(current => ({ ...current, [signal.id]: false })))
  }

  const detail = selected && <SignalDetail signal={selected} context={context.signalId === selected.id ? context : {}} contextLoading={contextLoading || context.signalId !== selected.id}
    draft={drafts[selected.id] ?? { state: selected.state, comment: selected.comment ?? '' }}
    busy={!!saving[selected.id]} saveError={saveErrors[selected.id] ?? ''}
    onDraft={draft => setDrafts(current => ({ ...current, [selected.id]: draft }))}
    onSave={() => save(selected)} onOpenRun={onOpenRun} onRetry={()=>setContextAttempt(value=>value+1)} />

  return <section className="signals-page" aria-labelledby="signals-heading">
    <div className="page-intro"><h1 ref={heading} tabIndex={-1} id="signals-heading">Сигналы</h1>{summary ? <div className="signals-summary" aria-label="Сводка открытых сигналов"><span>Требуют проверки: <strong>{summary.attention_count}</strong></span><span>Недостаточно данных: <strong>{summary.insufficient_data_count}</strong></span><span>Всего открытых: <strong>{summary.open_count}</strong></span>{summary.open_count===0&&<p>Открытых сигналов нет</p>}</div> : <p>Сводка открытых сигналов недоступна.</p>}<p>Новых: <strong>{newCount}</strong>. Каждый сигнал требует проверки человеком.</p></div>
    <div className="signals-toolbar"><label className="field" htmlFor="signals-filter">Показать<select id="signals-filter" value={filter} onChange={event => { setFilter(event.target.value); setVisibleCount(20); setSignals(null); setSelectedId(null); setListError('') }}><option value="">Все</option><option value="new">Новые</option><option value="in_progress">В работе</option><option value="closed">Закрытые</option></select></label><button type="button" className="secondary" disabled={listLoading} onClick={() => setRefresh(value => value + 1)}>Обновить</button></div>
    {listError && <p className="error" role="alert">{listError} <button className="secondary" onClick={()=>setRefresh(value=>value+1)}>Повторить загрузку сигналов</button></p>}
    {listLoading && !signals && <p role="status">Загружаем сигналы…</p>}
    {signals && <div className="signals-workspace">
      <div className="signals-list-column"><ol className="signals-list">{signals.slice(0, visibleCount).map(signal => <li key={signal.id} className="signals-list-item"><button className="signals-row" type="button" aria-expanded={selectedId === signal.id} aria-controls={selectedId === signal.id ? `signal-detail-${signal.id}` : undefined} onClick={() => setSelectedId(signal.id)}><SignalPreview signal={signal} /><span className="signals-row-copy"><strong>{signalTitle(signal)}</strong><span>{signal.zone_name ?? `Участок ${signal.zone_id}`}{signal.work_title ? ` · ${signal.work_title}` : ''}</span><time dateTime={signal.created_at}>{formatTime(signal.created_at)}</time></span><span className={`signals-state signals-state-${signal.state}`}>{STATES[signal.state]}</span></button>{compact && selectedId === signal.id && detail}</li>)}</ol>
        {signals.length > visibleCount && <button type="button" className="secondary signals-more" onClick={() => setVisibleCount(count => count + 20)}>Показать ещё</button>}
        {!signals.length && <p className="panel">Сигналов по выбранному фильтру нет.</p>}
      </div>
      {!compact && detail}
    </div>}
  </section>
}
