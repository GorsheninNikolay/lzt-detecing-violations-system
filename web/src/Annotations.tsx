import { useEffect, useRef, useState, type PointerEvent } from 'react'
import './annotations.css'

export type AnnotationObject = { id: string; class_name: string; box: [number, number, number, number] }
const labels: Record<string, string> = { excavator: 'Экскаватор', dump_truck: 'Самосвал', road_roller: 'Каток', truck_mounted_crane: 'Кран-манипулятор', concrete_mixer_truck: 'Автобетоносмеситель', bulldozer: 'Бульдозер', truck: 'Грузовик', mobile_crane: 'Автокран' }
type Pending = { body: string; key: string }
type Draft = { history: AnnotationObject[][]; cursor: number; pending: Pending | null; verified: boolean; reason: string; reviewRevision?: number; binding: string; geometry: Record<string,string[]>; completed: boolean }
type Proposal = { id: string; run_id: string; input_id: string; input_sha256: string; artifact_id: string; original_objects: AnnotationObject[]; objects: AnnotationObject[]; revision: number; status: string; version_id: string; whole_frame_verified: boolean; reason: string; reviewRevision?: number }

export function validObjects(value: unknown): value is AnnotationObject[] {
  return Array.isArray(value) && value.length <= 300 && value.every(item => item && typeof item.id === 'string' && Object.hasOwn(labels,item.class_name) && Array.isArray(item.box) && item.box.length === 4 && item.box.every((n: unknown) => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 1) && item.box[0] < item.box[2] && item.box[1] < item.box[3]) && new Set(value.map(item => item.id)).size === value.length
}

export function shiftBox(box: AnnotationObject['box'], dx: number, dy: number, resize = false): AnnotationObject['box'] {
  const [x1,y1,x2,y2] = box
  if (resize) return [x1,y1,Math.max(x1 + Math.min(.001,(1-x1)/2),Math.min(1,x2 + dx)),Math.max(y1 + Math.min(.001,(1-y1)/2),Math.min(1,y2 + dy))]
  dx = Math.max(-x1,Math.min(1-x2,dx)); dy = Math.max(-y1,Math.min(1-y2,dy))
  return [x1+dx,y1+dy,x2+dx,y2+dy]
}

function restoreDraft(raw: string | null, binding: string, checksum: string, owner: boolean): Draft | null {
  try {
    const saved = JSON.parse(raw ?? 'null')
    if (!saved || saved.binding !== binding || !Array.isArray(saved.history) || !saved.history.length || saved.history.length > 100 || !saved.history.every(validObjects) || !Number.isInteger(saved.cursor) || !saved.history[saved.cursor] || typeof saved.verified !== 'boolean' || typeof saved.reason !== 'string' || saved.reason.length > 3000 || typeof saved.completed !== 'boolean' || (owner && (!Number.isInteger(saved.reviewRevision) || saved.reviewRevision < 1)) || (!owner && saved.reviewRevision !== undefined) || !saved.geometry || typeof saved.geometry !== 'object' || Array.isArray(saved.geometry)) return null
    if (!Object.entries(saved.geometry).every(([id,values]) => saved.history[saved.cursor].some((item:AnnotationObject)=>item.id===id) && Array.isArray(values) && values.length===4 && values.every(value=>typeof value==='string' && value.length<=100))) return null
    if (saved.pending !== null) {
      if (!saved.pending || typeof saved.pending.body !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(saved.pending.key)) return null
      const value = JSON.parse(saved.pending.body)
      if (!validObjects(value.objects) || JSON.stringify(value.objects) !== JSON.stringify(saved.history[saved.cursor]) || Object.keys(saved.geometry).length || saved.completed) return null
      if (owner ? value.expected_revision !== saved.reviewRevision || value.whole_frame_verified !== saved.verified || value.reason !== saved.reason || !['pending','approved','rejected'].includes(value.status) || (value.status==='approved'&&!value.whole_frame_verified) || (value.status==='rejected'&&!value.reason.trim()) : value.input_sha256 !== checksum) return null
    }
    return saved
  } catch { return null }
}

function GeometryFields({ item, disabled, pending, onInput, onCommit, onRevert }: {item:AnnotationObject;disabled:boolean;pending?:string[];onInput:(values:string[])=>void;onCommit:(box:AnnotationObject['box'])=>void;onRevert:()=>void}) {
  const values = pending ?? item.box.map(String)
  const box = values.map(Number) as AnnotationObject['box']
  const invalid = !!pending && (values.some(value=>!value.trim()) || !validObjects([{...item,box}]))
  const commit=()=>{if(pending&&!invalid)onCommit(box)}
  return <fieldset className="geometry-control" disabled={disabled}><legend>Границы объекта</legend>{['Слева','Сверху','Справа','Снизу'].map((label,i)=><label key={label}>{label}<input type="number" min={0} max={1} step={.01} value={values[i]} aria-invalid={invalid} aria-describedby={invalid?`geometry-${item.id}-error`:undefined} onChange={event=>onInput(values.map((value,index)=>index===i?event.target.value:value))} onBlur={commit} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();commit()}}} /></label>)}{invalid&&<p id={`geometry-${item.id}-error`} role="alert">Введите границы от 0 до 1: справа больше, чем слева, снизу больше, чем сверху.</p>}{pending&&<button type="button" onMouseDown={event=>event.preventDefault()} onClick={onRevert}>Вернуть сохранённые границы</button>}</fieldset>
}

export function AnnotationEditor({ runId, inputId, checksum, artifactId, initial, review, csrf, onSaved }: {
  runId: string; inputId: string; checksum: string; artifactId: string; initial: AnnotationObject[];
  review?: Proposal; csrf?: string; onSaved?: () => void
}) {
  const storage = `annotation:${runId}:${inputId}:${checksum}:${review ? review.id : 'visitor'}`
  const [draft, setDraft] = useState<Draft>(() => {
    try { const saved = restoreDraft(localStorage.getItem(storage),storage,checksum,!!review); if(saved)return saved } catch { /* Storage may be unavailable. */ }
    return { history: [initial], cursor: 0, pending: null, verified: false, reason: '', reviewRevision:review?.revision, binding:storage, geometry:{}, completed:false }
  })
  const [selected, select] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [stale, setStale] = useState(!!review && draft.reviewRevision !== review.revision)
  const [serverVersion, setServerVersion] = useState<Proposal | null>(null)
  const [storageError, setStorageError] = useState(false)
  const [imageError, setImageError] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [preview, setPreview] = useState<{id:string;box:AnnotationObject['box']} | null>(null)
  const surface = useRef<HTMLDivElement>(null)
  const drag = useRef<{ id: string; x: number; y: number; box: AnnotationObject['box']; resize: boolean; start: AnnotationObject[] } | null>(null)
  const current = draft.history[draft.cursor]
  const locked = busy || !!draft.pending
  const geometryPending = Object.keys(draft.geometry).length > 0
  const persist = (next: Draft) => {
    setDraft(next)
    try { localStorage.setItem(storage, JSON.stringify(next)); setStorageError(false) } catch { setStorageError(true) }
  }
  useEffect(() => { try { localStorage.setItem(storage, JSON.stringify(draft)) } catch { setStorageError(true) } }, [])
  const edit = (next: AnnotationObject[]) => { if (!locked && validObjects(next)) persist({ ...draft, history: [...draft.history.slice(0,draft.cursor + 1), next].slice(-100), cursor: Math.min(draft.cursor + 1,99), verified: false, geometry:Object.fromEntries(Object.entries(draft.geometry).filter(([id])=>next.some(item=>item.id===id && JSON.stringify(item.box)===JSON.stringify(current.find(old=>old.id===id)?.box)))), completed:false }) }
  const change = (id: string, patch: Partial<AnnotationObject>) => edit(current.map(item => item.id === id ? { ...item, ...patch } : item))
  function begin(event: PointerEvent<HTMLButtonElement>, item: AnnotationObject, resize: boolean) {
    select(item.id)
    if (locked || !window.matchMedia('(min-width: 769px)').matches) return
    event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = { id: item.id, x: event.clientX, y: event.clientY, box: item.box, resize, start: current }
  }
  function move(event: PointerEvent<HTMLButtonElement>) {
    const start = drag.current, bounds = surface.current?.getBoundingClientRect()
    if(start && bounds?.width && bounds.height) setPreview({id:start.id,box:shiftBox(start.box,(event.clientX-start.x)/bounds.width,(event.clientY-start.y)/bounds.height,start.resize)})
  }
  function finish(event: PointerEvent<HTMLButtonElement>) {
    const start = drag.current, bounds = surface.current?.getBoundingClientRect()
    if (!start || !bounds?.width || !bounds.height) return
    drag.current = null
    setPreview(null)
    const box = shiftBox(start.box,(event.clientX-start.x)/bounds.width,(event.clientY-start.y)/bounds.height,start.resize)
    if (JSON.stringify(box) !== JSON.stringify(start.box)) change(start.id,{ box })
  }
  async function submit(status: string) {
    if (geometryPending || (!draft.pending && status === 'approved' && (!imageLoaded || imageError || !draft.verified))) return
    const pending = draft.pending ?? { key: crypto.randomUUID(), body: JSON.stringify(review ? { expected_revision: draft.reviewRevision ?? review.revision, objects: current, status, whole_frame_verified: draft.verified, reason: draft.reason } : { input_sha256: checksum, objects: current }) }
    const next = { ...draft, pending, completed:false }
    try { localStorage.setItem(storage,JSON.stringify(next)) } catch { setStorageError(true); setMessage('Не удалось сохранить запрос перед отправкой. Освободите локальное хранилище и повторите.'); return }
    setDraft(next); setBusy(true); setMessage('')
    try {
      const response = await fetch(review ? `/api/admin/annotations/${review.id}/review` : `/api/runs/${runId}/frames/${inputId}/annotations`, { method:'POST', headers:{ 'Content-Type':'application/json', 'Idempotency-Key':pending.key, ...(csrf ? {'X-CSRF-Token':csrf} : {}) }, body:pending.body, signal:AbortSignal.timeout(15000) })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        if (data.detail === 'stale_revision') setStale(true)
        if (response.status < 500 && response.status !== 408 && response.status !== 429) persist({ ...next, pending:null })
        throw new Error(data.detail === 'stale_revision' ? 'Версия на сервере изменилась. Правки сохранены. Обновите очередь, сравните новую версию и перенесите нужные изменения из этого черновика.' : 'Не удалось сохранить. Правки сохранены; повторите запрос.')
      }
      const result = await response.json()
      persist({ ...next, history:[current],cursor:0,pending:null,verified:false,geometry:{},completed:true,reviewRevision:review ? result.revision ?? draft.reviewRevision : undefined })
      setMessage(review ? 'Версия сохранена. Одобрение не меняет модель автоматически.' : 'Поправки отправлены на проверку. Исходный анализ не изменён.')
      onSaved?.()
    } catch (error) { setMessage(error instanceof DOMException || error instanceof TypeError ? 'Ответ неизвестен. Правки сохранены. Повторите тот же запрос.' : (error as Error).message) } finally { setBusy(false) }
  }
  return <section className="annotation-editor" aria-label={review ? 'Проверка разметки' : 'Исправление разметки'}>
    <p>Редактируется отдельная копия. Исходные наблюдения и выводы сохраняются.</p>
    {storageError && <p role="alert" className="error">Локальное сохранение недоступно. Не закрывайте страницу до успешной отправки.</p>}
    <div className="annotation-tools"><button disabled={locked || draft.cursor === 0} onClick={() => persist({ ...draft, cursor:draft.cursor-1, verified:false,geometry:{},completed:false })}>Отменить</button><button disabled={locked || draft.cursor === draft.history.length-1} onClick={() => persist({ ...draft, cursor:draft.cursor+1, verified:false,geometry:{},completed:false })}>Повторить правку</button><button className="geometry-control" disabled={locked || current.length >= 300} onClick={() => { const id = crypto.randomUUID(); edit([...current,{id,class_name:'excavator',box:[.25,.25,.5,.5]}]); select(id) }}>Добавить объект</button></div>
    <p className="geometry-control">Выберите рамку. Перемещайте мышью или стрелками; Shift + стрелки изменяют размер. Координаты — доли ширины и высоты.</p><p className="phone-editor-note">На телефоне можно изменить класс или удалить объект. Геометрия доступна на большом экране.</p>
    <div className="annotation-layout"><div>{imageError ? <p role="alert">Изображение недоступно. <button onClick={() => {setImageError(false);setAttempt(v=>v+1)}}>Повторить изображение</button></p> : <div className="annotation-canvas" ref={surface}><img key={attempt} src={`/api/runs/${runId}/artifacts/${artifactId}`} alt="Кадр для исправления объектов" onLoad={event=>setImageLoaded(event.currentTarget.naturalWidth>0 && event.currentTarget.naturalHeight>0)} onError={() => {setImageError(true);setImageLoaded(false);if(!draft.pending)persist({...draft,verified:false})}} />{current.map((saved,index) => { const item = preview?.id === saved.id ? { ...saved, box:preview.box } : saved; return <button key={item.id} className={`annotation-box ${selected === item.id ? 'selected' : ''}`} aria-label={`Объект ${index+1}: ${labels[item.class_name]}`} aria-pressed={selected === item.id} style={{left:`${item.box[0]*100}%`,top:`${item.box[1]*100}%`,width:`${(item.box[2]-item.box[0])*100}%`,height:`${(item.box[3]-item.box[1])*100}%`}} onClick={() => select(item.id)} onPointerDown={event=>begin(event,item,false)} onPointerMove={move} onPointerUp={finish} onPointerCancel={()=>{drag.current=null;setPreview(null)}} onKeyDown={event => { if (locked || !window.matchMedia('(min-width: 769px)').matches) return; const vector:Record<string,[number,number]> = {ArrowLeft:[-.01,0],ArrowRight:[.01,0],ArrowUp:[0,-.01],ArrowDown:[0,.01]}; if (vector[event.key]) { event.preventDefault(); change(item.id,{box:shiftBox(item.box,...vector[event.key],event.shiftKey)}) } }}><span>{index+1}</span></button>})}{current.filter(item=>item.id===selected).map(item=><button key={`resize-${item.id}`} disabled={locked} className="annotation-resize geometry-control" aria-label="Изменить размер выбранного объекта" style={{left:`${(preview?.id===item.id?preview.box:item.box)[2]*100}%`,top:`${(preview?.id===item.id?preview.box:item.box)[3]*100}%`}} onPointerDown={event=>begin(event,item,true)} onPointerMove={move} onPointerUp={finish} onPointerCancel={()=>{drag.current=null;setPreview(null)}}>↔</button>)}</div>}</div>
    <ol className="annotation-objects">{current.map((item,index) => <li key={item.id} className={selected===item.id?'selected':''}><button aria-pressed={selected===item.id} onClick={()=>select(item.id)}>Объект {index+1}</button><label>Класс<select disabled={locked} value={item.class_name} onChange={event=>change(item.id,{class_name:event.target.value})}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><GeometryFields item={item} disabled={locked} pending={draft.geometry[item.id]} onInput={values=>persist({...draft,geometry:{...draft.geometry,[item.id]:values},verified:false,completed:false})} onRevert={()=>{const geometry={...draft.geometry};delete geometry[item.id];persist({...draft,geometry,verified:false})}} onCommit={box=>{const geometry={...draft.geometry};delete geometry[item.id];if(JSON.stringify(box)!==JSON.stringify(item.box))change(item.id,{box});else persist({...draft,geometry})}} /><button disabled={locked} onClick={()=>edit(current.filter(value=>value.id!==item.id))}>Удалить объект {index+1}</button></li>)}</ol></div>
    {!current.length && <p>В копии нет объектов. Пустой кадр тоже можно отправить на проверку.</p>}
    {review && <><label className="annotation-verification"><input type="checkbox" disabled={locked || geometryPending || !imageLoaded || imageError} checked={draft.verified && imageLoaded && !imageError} onChange={event=>persist({...draft,verified:event.target.checked,completed:false})} /> Проверил весь кадр: все объекты и их границы</label><label className="field annotation-reason">Причина решения<textarea disabled={locked} maxLength={3000} value={draft.reason} onChange={event=>persist({...draft,reason:event.target.value,completed:false})} /></label></>}
    {draft.pending ? <button className="primary" disabled={busy || geometryPending} onClick={()=>void submit('pending')}>{busy?'Отправляем…':'Повторить сохранённый запрос'}</button> : <div className="annotation-tools"><button className="primary" disabled={busy || geometryPending} onClick={()=>void submit('pending')}>{review?'Сохранить правки':'Отправить поправки на проверку'}</button>{review && <><button className="primary" disabled={busy || geometryPending || !draft.verified || !imageLoaded || imageError} onClick={()=>void submit('approved')}>Одобрить весь кадр</button><button disabled={busy || geometryPending || !draft.reason.trim()} onClick={()=>void submit('rejected')}>Отклонить с причиной</button></>}</div>}
    {stale && review && <button disabled={busy || !!draft.pending} onClick={async () => { setBusy(true); try { const response = await fetch(`/api/admin/annotations/${review.id}`, { signal:AbortSignal.timeout(10000) }); if(!response.ok) throw new Error(); const latest = await response.json() as Proposal; setServerVersion(latest); persist({...draft,reviewRevision:latest.revision,verified:false,completed:false});setStale(false);setMessage('Новая версия загружена для сравнения. Ваши правки сохранены. Сверьте объекты и проверьте весь кадр повторно перед решением.') } catch {setMessage('Не удалось загрузить новую версию. Правки сохранены.')} finally {setBusy(false)} }}>Загрузить новую версию для сравнения</button>}
    {serverVersion && <details open><summary>Серверная версия {serverVersion.revision} для сравнения</summary><ol>{serverVersion.objects.map(item=><li key={item.id}>{labels[item.class_name]}: {item.box.join(', ')}</li>)}</ol>{!serverVersion.objects.length && <p>На сервере список объектов пуст.</p>}</details>}
    {geometryPending && <p>Завершите ввод границ или верните сохранённые границы перед отправкой.</p>}
    {draft.completed && !draft.pending && !geometryPending && <button onClick={()=>{try{localStorage.removeItem(storage);setDraft({...draft,completed:false});setMessage('Завершённый локальный черновик удалён. Сохранённая версия остаётся на сервере.')}catch{setStorageError(true)}}}>Удалить завершённый локальный черновик</button>}
    {message && <p role="status">{message}</p>}
  </section>
}

export function AnnotationQueue({ csrf }: {csrf:string}) {
  const [rows,setRows]=useState<Proposal[]>([])
  const [selected,setSelected]=useState<Proposal|null>(null)
  const [checked,setChecked]=useState<{id:string;revision:number;inputId:string}[]>([])
  const [error,setError]=useState(''), [busy,setBusy]=useState(false), [reading,setReading]=useState(false)
  const [offset,setOffset]=useState<number|null>(null)
  const heading=useRef<HTMLHeadingElement>(null)
  const activeRead=useRef<AbortController|null>(null)
  const pagesLoaded=useRef(1)
  const merge=(items:Proposal[])=>[...new Map(items.map(row=>[row.id,row])).values()]
  async function load(append=false, savedId?:string) {
    if(activeRead.current){if(!savedId)return;activeRead.current.abort();activeRead.current=null}
    const controller=new AbortController();activeRead.current=controller;setReading(true)
    const read=async(path:string)=>{const response=await fetch(`/api/admin/annotations${path}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])});if(!response.ok)throw new Error();return response.json()}
    try {
      if(savedId){
        const row=await read(`/${savedId}`) as Proposal
        if(controller.signal.aborted)return
        setRows(current=>merge([...current,row]));setSelected(current=>current?.id===row.id?row:current)
      }else{
        let nextOffset=append?offset:0
        const collected:Proposal[]=[]
        const pages=append?1:pagesLoaded.current
        for(let page=0;page<pages&&nextOffset!==null;page++){
          const data=await read(`?offset=${nextOffset}`);collected.push(...data.annotations);nextOffset=data.next_offset
        }
        if(controller.signal.aborted)return
        setRows(current=>merge([...(append?current:[]),...collected,...(selected&&!collected.some(row=>row.id===selected.id)&&!append?[selected]:[])]))
        setOffset(nextOffset);if(append)pagesLoaded.current+=1
      }
      setError('')
    }catch{if(!controller.signal.aborted)setError('Не удалось загрузить очередь. Черновики сохранены.')}
    finally{if(activeRead.current===controller){activeRead.current=null;setReading(false)}}
  }
  useEffect(()=>{void load();return()=>{activeRead.current?.abort();activeRead.current=null}},[])
  useEffect(()=>{if(selected)heading.current?.focus()},[selected?.id,selected?.revision])
  async function download() {
    if(!checked.length||checked.length>32)return
    setBusy(true);setError('')
    try{
      const response=await fetch('/api/admin/annotations/export',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({version_ids:checked.map(item=>item.id)}),signal:AbortSignal.timeout(60000)})
      if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail==='exclusion_evidence_unavailable'?'Экспорт остановлен: недоступны данные для проверки исключения оценочных кадров.':data.detail==='duplicate_frame_versions'?'Выбраны конфликтующие версии одного кадра. Оставьте одну версию.':'Экспорт остановлен: проверьте одобрение и допустимость выбранных версий.')}
      const url=URL.createObjectURL(await response.blob());const anchor=document.createElement('a');anchor.href=url;anchor.download='annotations.zip';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
    }catch(error){setError((error as Error).message)}finally{setBusy(false)}
  }
  return <section><h2>Поправки к разметке</h2><p>В коллекцию входят только выбранные версии после проверки всего кадра. Одобрение не обучает модель автоматически.</p>{error&&<p role="alert" className="error">{error}</p>}
    <div className="annotation-tools"><button disabled={reading} onClick={()=>void load()}>Обновить очередь</button><button disabled={busy||!checked.length} onClick={()=>void download()}>Скачать выбранные версии ({checked.length})</button></div>
    <section aria-label="Выбранные версии для экспорта"><p>Можно выбрать не более 32 версий. Выбор сохраняет точные версии после обновления очереди.</p><ul>{checked.map(item=><li key={item.id}>Кадр {item.inputId.slice(0,8)} · Версия {item.revision} · <code>{item.id}</code> <button className="secondary" onClick={()=>setChecked(values=>values.filter(value=>value.id!==item.id))}>Убрать версию {item.revision} кадра {item.inputId.slice(0,8)} из экспорта</button></li>)}</ul></section>
    <div className={`annotation-review-layout ${selected?'has-detail':''}`}><div>{rows.map(row=><article key={row.id}><button disabled={reading} id={`proposal-${row.id}`} onClick={()=>setSelected(row)}>Кадр {row.input_id.slice(0,8)} · Версия {row.revision} · {({pending:'На проверке',approved:'Одобрено',rejected:'Отклонено'} as Record<string,string>)[row.status]}</button>{row.status==='approved'&&<label><input type="checkbox" checked={checked.some(item=>item.id===row.version_id)} disabled={checked.length>=32&&!checked.some(item=>item.id===row.version_id)} onChange={event=>setChecked(values=>event.target.checked?values.length<32&&!values.some(item=>item.id===row.version_id)?[...values,{id:row.version_id,revision:row.revision,inputId:row.input_id}]:values:values.filter(item=>item.id!==row.version_id))}/> В экспорт</label>}</article>)}{!rows.length&&!reading&&<p>Поправок пока нет.</p>}{offset!==null&&<button disabled={reading} onClick={()=>void load(true)}>Показать ещё</button>}</div>
    {selected&&<article><button onClick={()=>{const id=selected.id;setSelected(null);requestAnimationFrame(()=>document.getElementById(`proposal-${id}`)?.focus())}}>Вернуться к очереди</button><h3 ref={heading} tabIndex={-1}>Проверка кадра · версия {selected.revision}</h3><details><summary>Исходная разметка модели</summary><div className="annotation-canvas"><img src={`/api/runs/${selected.run_id}/artifacts/${selected.artifact_id}`} alt="Исходный кадр с разметкой модели"/>{selected.original_objects.map((item,index)=><span className="annotation-box" key={item.id} style={{left:`${item.box[0]*100}%`,top:`${item.box[1]*100}%`,width:`${(item.box[2]-item.box[0])*100}%`,height:`${(item.box[3]-item.box[1])*100}%`}}>{index+1}</span>)}</div><ol>{selected.original_objects.map(item=><li key={item.id}>{labels[item.class_name]} · {item.box.join(', ')}</li>)}</ol></details><AnnotationEditor key={`${selected.id}:${selected.revision}`} runId={selected.run_id} inputId={selected.input_id} checksum={selected.input_sha256} artifactId={selected.artifact_id} initial={selected.objects} review={selected} csrf={csrf} onSaved={()=>void load(false,selected.id)}/></article>}
    </div>
  </section>
}
