import { useEffect, useRef, useState } from 'react'
export type Input = { input_id: string; ordinal: number; sha256: string; artifact_id: string | null }
export type Observation = { input_id: string; ordinal: number; class_name: string; state: string; reason?: string | null; source_artifact_id: string | null; input_sha256?: string; invocation_id?: string | null }
export type NativeEvidence = { artifact_id: string; input_id: string; ordinal: number; sha256: string; invocation_id: string; profile_id: string; profile_revision: number; preprocessing_revision?: string | null }
export type DetectedObject = { id?: string; input_id: string; class_name: string; score: number | null; box: [number, number, number, number] | null; details?: { type_ru: string; type_en: string; evidence: string; status: string; missing_localization_reason?: string | null }; image_size: [number, number]; invocation_id: string }
export type ProfileSnapshot = { kind?: string; observation_contract?: string; adapter?: { code?: string } }
export type ResultFrame = { input_id: string; ordinal: number; artifact_id: string | null; sha256: string | null; usable: boolean | null; observations: Observation[] }
const CLASS_LABELS: Record<string, string> = { excavator: 'Экскаватор', dump_truck: 'Самосвал', road_roller: 'Каток', truck_mounted_crane: 'Кран-манипулятор', concrete_mixer_truck: 'Автобетоносмеситель', bulldozer: 'Бульдозер', truck: 'Грузовик', mobile_crane: 'Автокран' }
const OBSERVATION_STATES: Record<string, string> = { detected: 'Обнаружен', not_detected_in_frame: 'Не обнаружен в кадре', insufficient_data: 'Недостаточно данных', not_analyzed: 'Не анализировалось' }
const OBSERVATION_REASONS: Record<string, string> = { frame_unassessable: 'Кадр непригоден для распознавания.', unsupported_class: 'Класс не поддерживается профилем распознавания.', observer_unavailable: 'Распознавание недоступно.' }
function artifactUrl(runId: string, artifactId: string) { return `/api/runs/${runId}/artifacts/${artifactId}` }

function useArtifact(runId: string, artifactId: string | null, thumbnail = false) {
  const [attempt, retry] = useState(0)
  const [loaded, setLoaded] = useState<{ id: string; url: string } | null>(null)
  const [failure, setFailure] = useState<{ id: string; code: string } | null>(null)
  useEffect(() => {
    if (!artifactId) return
    const controller = new AbortController()
    let url: string | null = null
    void fetch(artifactUrl(runId, artifactId) + (thumbnail ? '/thumbnail' : ''), { signal: controller.signal }).then(async response => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { code?: string }
        throw new Error(body.code === 'artifact_integrity_failed' ? 'integrity' : 'unavailable')
      }
      url = URL.createObjectURL(await response.blob())
      if (!controller.signal.aborted) { setLoaded({ id: artifactId, url }); setFailure(null) }
      else URL.revokeObjectURL(url)
    }).catch(error => { if (!controller.signal.aborted) setFailure({ id: artifactId, code: error.message === 'integrity' ? 'integrity' : 'unavailable' }) })
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [runId, artifactId, attempt, thumbnail])
  return { url: loaded && loaded.id === artifactId && failure?.id !== artifactId ? loaded.url : null,
    error: failure && failure.id === artifactId ? failure.code : null,
    imageFailed: () => { if(artifactId)setFailure({id:artifactId,code:'decode'}) },
    retry: () => { setLoaded(null); setFailure(null); retry(value => value + 1) } }
}

export function SourceImage({ runId, artifactId, label, description, objects = [], showBoxes = false, selectedObject, onSelectObject, thumbnail = false }: { runId: string; artifactId: string | null; label: string; description: string; objects?: DetectedObject[]; showBoxes?: boolean; selectedObject?: number | null; onSelectObject?: (index: number) => void; thumbnail?: boolean }) {
  const artifact = useArtifact(runId, artifactId, thumbnail)
  return <div className="source-image">{!artifactId ? <p className="error">Исходное изображение недоступно для этого кадра.</p> : artifact.url ? <div className="annotated-image"><img src={artifact.url} onError={artifact.imageFailed} alt={`Исходное изображение: ${label}. ${description}`} />{showBoxes && objects.map((object, index) => {
    if (!object.box) return null
    const [x1, y1, x2, y2] = object.box
    if (!(x1 >= 0 && y1 >= 0 && x2 <= 1 && y2 <= 1 && x2 > x1 && y2 > y1 && [x1, y1, x2, y2].every(Number.isFinite))) return null
    const Overlay = onSelectObject ? 'button' : 'div'
    return <Overlay key={`${object.invocation_id}-${index}`} aria-hidden={!onSelectObject} className={`object-box ${selectedObject === index ? 'selected' : ''}`} aria-label={`Объект ${index + 1}: ${CLASS_LABELS[object.class_name] ?? object.class_name}`} aria-pressed={selectedObject === index} onClick={() => onSelectObject?.(index)} style={{ pointerEvents: onSelectObject ? 'auto' : 'none', left: `${100 * x1}%`, top: `${100 * y1}%`, width: `${100 * (x2 - x1)}%`, height: `${100 * (y2 - y1)}%` }}><span>{index + 1}</span></Overlay>
  })}</div> :
    artifact.error ? <p className="error">{artifact.error === 'integrity' ? 'Целостность артефакта не подтверждена' : artifact.error === 'decode' ? 'Не удалось прочитать изображение' : 'Не удалось открыть исходное изображение'} <button type="button" className="secondary" onClick={artifact.retry}>Повторить</button></p> :
      <p className="muted">Загружаем изображение…</p>}</div>
}

export function frameDescription(observations: Observation[]): string {
  return observations.map(item =>
    `${CLASS_LABELS[item.class_name] ?? item.class_name}: ${OBSERVATION_STATES[item.state] ?? item.state}${item.reason ? `; ${OBSERVATION_REASONS[item.reason] ?? item.reason}` : ''}`).join('. ')
}

export function makeResultFrames(observations: Observation[], inputs: Input[], usableInputIds?: string[], projected = false): ResultFrame[] {
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

export function EvidenceViewer({ runId, frames, native, objects, showBoxes, profile, context, selected, onClose, onSelect }: {
  runId: string; frames: ResultFrame[]; native: NativeEvidence[]; objects: DetectedObject[]; showBoxes: boolean; profile?: ProfileSnapshot; context?: {period?:string}; selected: number;
  onClose: () => void; onSelect: (index: number) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const handledClose = useRef(false)
  const [zoom, setZoom] = useState(1)
  const [boxesVisible,setBoxesVisible] = useState(showBoxes)
  useEffect(()=>setBoxesVisible(showBoxes),[showBoxes])
  const pan = useRef<{x:number;y:number;left:number;top:number}|null>(null)
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
    const opener=document.activeElement as HTMLElement | null
    dialog.current?.showModal()
    return () => { if (dialog.current?.open) dialog.current.close(); opener?.focus() }
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
    <div className="viewer-toolbar"><label><input type="checkbox" checked={boxesVisible} onChange={event=>setBoxesVisible(event.target.checked)}/> Рамки объектов</label><button type="button" className="secondary" onClick={() => dialog.current?.close()}>Закрыть</button><button type="button" className="secondary" disabled={selected === 0} onClick={() => { onSelect(selected - 1); setZoom(1) }}>Предыдущий кадр</button><button type="button" className="secondary" disabled={selected === frames.length - 1} onClick={() => { onSelect(selected + 1); setZoom(1) }}>Следующий кадр</button><button type="button" className="secondary" onClick={() => setZoom(value => Math.min(4, value + .5))}>Увеличить</button><button type="button" className="secondary" onClick={() => setZoom(value => Math.max(1, value - .5))}>Уменьшить</button><button type="button" className="secondary" onClick={() => setZoom(1)}>Сбросить масштаб</button></div>
    <p role="status">Кадр {selected + 1} из {frames.length}. Масштаб {Math.round(zoom * 100)}%.</p>
    <p>Номер кадра: {frame.ordinal + 1}. Пригодность: {frame.usable === null ? 'не указана' : frame.usable ? 'пригоден' : 'не пригоден'}.</p>
    <p>Наблюдения: {frameDescription(frame.observations) || 'не указаны'}.</p>
    <p>Период: {context?.period ?? 'не указан'}.</p>
    <div className="viewer-image" tabIndex={0} aria-label="Фотография: прокрутка для перемещения" onPointerDown={event=>{if(event.button!==0 || (event.target as Element).closest('button,a,input,select,textarea,summary'))return;event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);pan.current={x:event.clientX,y:event.clientY,left:event.currentTarget.scrollLeft,top:event.currentTarget.scrollTop}}} onPointerMove={event=>{if(pan.current){event.currentTarget.scrollLeft=pan.current.left+pan.current.x-event.clientX;event.currentTarget.scrollTop=pan.current.top+pan.current.y-event.clientY}}} onPointerUp={()=>{pan.current=null}} onPointerCancel={()=>{pan.current=null}}><div style={{ width: `${zoom * 100}%` }}><SourceImage key={frame.input_id} runId={runId} artifactId={frame.artifact_id} label={`Кадр ${frame.ordinal + 1}`} description={frameDescription(frame.observations)} objects={objects.filter(item => item.input_id === frame.input_id)} showBoxes={boxesVisible} /></div></div>
    <details><summary>Подробности кадра</summary><p>Входной ID: <code>{frame.input_id}</code>.</p><p>Исходный артефакт ID: <code>{frame.artifact_id ?? 'не указан'}</code>. SHA-256 исходного кадра: <code>{frame.sha256 ?? 'не указан'}</code>.</p></details>
    {evidence && <details><summary>Технические данные наблюдателя</summary><p>Данные конкретного наблюдателя. Не используются правилом этапа.</p><p>Адаптер: <code>{profile?.adapter?.code ?? 'не указан'}</code>. Профиль <code>{evidence.profile_id}</code>, ревизия допуска: {evidence.profile_revision}. Вызов <code>{evidence.invocation_id}</code>. Входной ID <code>{evidence.input_id}</code>. Предобработка: {evidence.preprocessing_revision ? <code>{evidence.preprocessing_revision}</code> : 'не указана'}. Артефакт <code>{evidence.artifact_id}</code>, SHA-256 <code>{evidence.sha256}</code>.</p>{nativeError?.id === evidence.artifact_id ? <p className="error">{nativeError.code === 'integrity' ? 'Целостность артефакта не подтверждена' : 'Не удалось открыть технические данные'} <button type="button" className="secondary" onClick={() => { setNativeResult(null); setNativeError(null); retryNative(value => value + 1) }}>Повторить</button></p> : nativeResult?.id === evidence.artifact_id ? <pre>{nativeResult.text}</pre> : <p>Загружаем технические данные…</p>}</details>}
  </dialog>
}
