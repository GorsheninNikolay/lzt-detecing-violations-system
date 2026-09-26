import { useEffect, useRef, useState, type ReactNode } from 'react'
import { startActivity, track } from './engagement'
import OnboardingTour, { type Training } from './OnboardingTour'

export function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const closeRef = useRef(close)
  closeRef.current = close
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const element = dialog.current!
    element.showModal?.()
    const cancel = (event: Event) => { event.preventDefault(); closeRef.current() }
    element.addEventListener('cancel', cancel)
    return () => { element.removeEventListener('cancel', cancel); element.close?.(); previous?.focus() }
  }, [])
  return <dialog ref={dialog} className="support-dialog" aria-labelledby="support-title"><div className="support-dialog-head"><h2 id="support-title">{title}</h2><button type="button" className="secondary" onClick={close} aria-label="Закрыть">Закрыть</button></div>{children}</dialog>
}


function remembered() {
  try { return !!localStorage.getItem('construction-onboarding') } catch { return true }
}

type Picture = { name: string; media: string; data: string; size: number }
type Draft = { category: string; message: string; includeContext: boolean; pictures: Picture[]; frozen?: { body: string; key: string } }
const emptyDraft = (): Draft => ({ category: '', message: '', includeContext: true, pictures: [] })
let draftIdentity: Promise<string> | undefined
function tabKey(): Promise<string> {
  if (!draftIdentity) draftIdentity = new Promise((resolve, reject) => {
    try {
      const claim = (key: string) => {
        if (!navigator.locks) { sessionStorage.setItem('feedback-tab', key); resolve(key); return }
        void navigator.locks.request(`feedback-tab:${key}`, { ifAvailable: true }, async lock => {
          if (!lock) { claim(crypto.randomUUID()); return }
          sessionStorage.setItem('feedback-tab', key)
          resolve(key)
          await new Promise(() => {})
        }).catch(reject)
      }
      claim(sessionStorage.getItem('feedback-tab') ?? crypto.randomUUID())
    } catch (error) { reject(error) }
  })
  return draftIdentity
}
async function draftStore(value?: Draft): Promise<Draft | undefined> {
  const key = await tabKey()
  const db = await new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open('construction-feedback', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('drafts')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction('drafts', value ? 'readwrite' : 'readonly')
      const store = transaction.objectStore('drafts')
      const request = value ? store.put(value, key) : store.get(key)
      transaction.oncomplete = () => resolve(value ?? request.result)
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  } finally { db.close() }
}

let draftOperations: Promise<unknown> = Promise.resolve()
function serializeDraft<T>(operation: () => Promise<T>): Promise<T> {
  const result = draftOperations.then(operation)
  draftOperations = result.catch(() => {})
  return result
}

function Feedback({ projectId, analysisId, close }: { projectId?: string; analysisId?: string; close: () => void }) {
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [storageError, setStorageError] = useState(false)
  const [success, setSuccess] = useState(false)
  const lifecycle = useRef(0)
  const active = useRef(false)
  const context = { pathname: location.pathname, ...(projectId ? { project_id: projectId } : {}), ...(analysisId ? { analysis_id: analysisId } : {}) }
  const shownContext: Record<string, string> = draft.frozen ? JSON.parse(draft.frozen.body).context : context
  useEffect(() => {
    active.current = true
    const generation = ++lifecycle.current
    void serializeDraft(() => draftStore()).then(value => { if (active.current && generation === lifecycle.current && value) setDraft(value) }).catch(() => { if (active.current) setStorageError(true) }).finally(() => { if (active.current && generation === lifecycle.current) setLoaded(true) })
    return () => { active.current = false; lifecycle.current++ }
  }, [])
  const update = (next: Draft) => {
    setDraft(next)
    void serializeDraft(() => draftStore(next)).then(() => { if (active.current) setStorageError(false) }).catch(() => { if (active.current) setStorageError(true) })
  }
  async function add(files: File[]) {
    const generation = lifecycle.current
    setBusy(true); setError('')
    try {
      if (draft.pictures.length + files.length > 5 || draft.pictures.reduce((n, item) => n + item.size, 0) + files.reduce((n, file) => n + file.size, 0) > 15_000_000 || files.some(file => file.size > 5_000_000 || !['image/jpeg','image/png','image/webp'].includes(file.type))) throw new Error('Выберите до пяти JPEG, PNG или WebP: до 5 МБ каждый и 15 МБ вместе.')
      const pictures = await Promise.all(files.map(file => new Promise<Picture>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve({ name: file.name, media: file.type, size: file.size, data: String(reader.result).split(',')[1] })
        reader.onerror = () => reject(new Error('Не удалось прочитать изображение.'))
        reader.readAsDataURL(file)
      })))
      if (!active.current || generation !== lifecycle.current) return
      update({ ...draft, pictures: [...draft.pictures, ...pictures] })
    } catch (error) { if (active.current && generation === lifecycle.current) setError((error as Error).message) } finally { if (active.current && generation === lifecycle.current) setBusy(false) }
  }
  async function send() {
    setBusy(true); setError('')
    const generation = lifecycle.current
    const current = () => active.current && generation === lifecycle.current
    const frozen = draft.frozen ?? { key: crypto.randomUUID(), body: JSON.stringify({ category: draft.category, message: draft.message, context: draft.includeContext ? context : {}, attachments: draft.pictures.map(({ data }) => ({ data })) }) }
    const next = { ...draft, frozen }
    setDraft(next)
    try {
      await serializeDraft(async () => {
        await draftStore(next)
        const response = await fetch('/api/feedback', { method: 'POST', headers: { 'Content-Type':'application/json', 'Idempotency-Key':frozen.key }, body:frozen.body, signal:AbortSignal.timeout(30000) })
        if (!response.ok) {
          if (response.status === 400 || response.status === 413) {
            const editable = { ...next, frozen: undefined }
            await draftStore(editable)
            if (current()) setDraft(editable)
          }
          throw new Error(response.status === 429 ? 'Слишком много отправок. Попробуйте позже.' : 'Не удалось сохранить отзыв. Черновик сохранён, повторите отправку.')
        }
        await draftStore(emptyDraft())
      })
      if (current()) setSuccess(true)
    } catch (error) { if (current()) setError((error as Error).name === 'Error' ? (error as Error).message : 'Ответ не получен. Повторите отправку с теми же данными.') }
    finally { if (current()) setBusy(false) }
  }
  return <Modal title="Обратная связь" close={close}>{success ? <p role="status">Спасибо, отзыв сохранён</p> : <form onSubmit={event => { event.preventDefault(); void send() }}>
    <p>Расскажите о проблеме, предложите идею или поделитесь впечатлением.</p>
    {storageError && <p className="error" role="alert">Хранилище браузера недоступно. Отправка требует сохранения черновика; разрешите локальное хранение и повторите.</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {draft.frozen && <p className="attention">Данные отправки закреплены. Повтор использует прежний ключ и не создаст второй отзыв.</p>}
    <fieldset disabled={!loaded || busy || !!draft.frozen}><label className="field">Категория<select aria-label="Категория" required value={draft.category} onChange={event => update({ ...draft, category: event.target.value })}><option value="">Выберите категорию</option><option value="problem">Проблема</option><option value="idea">Идея</option><option value="praise">Понравилось</option><option value="other">Другое</option></select></label>
    <label className="field">Сообщение<textarea aria-label="Сообщение" required maxLength={5000} rows={6} value={draft.message} onChange={event => update({ ...draft, message: event.target.value })} /></label><p>{draft.message.length} / 5000</p>
    <label className="field">Изображения<input aria-label="Изображения" type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={event => { void add(Array.from(event.target.files ?? [])); event.target.value = '' }} /></label><p>До 5 изображений, 5 МБ каждое, 15 МБ вместе. Фотографии анализа автоматически не прикладываются.</p>
    <div className="feedback-previews">{draft.pictures.map((picture, index) => <figure key={`${index}-${picture.name}`}><img src={`data:${picture.media};base64,${picture.data}`} alt={picture.name} /><figcaption>{picture.name}</figcaption><button type="button" className="secondary" aria-label={`Удалить ${picture.name}`} onClick={() => update({ ...draft, pictures: draft.pictures.filter((_, i) => i !== index) })}>Удалить</button></figure>)}</div>
    <label><input type="checkbox" checked={draft.includeContext} onChange={event => update({ ...draft, includeContext: event.target.checked })} /> Приложить контекст</label><dl><dt>Страница</dt><dd>{shownContext.pathname ?? 'Не приложена'}</dd>{shownContext.project_id && <><dt>Проект</dt><dd>{shownContext.project_id}</dd></>}{shownContext.analysis_id && <><dt>Анализ</dt><dd>{shownContext.analysis_id}</dd></>}</dl></fieldset>
    <button className="primary" type="submit" disabled={!loaded || busy || !draft.category || !draft.message.trim()}>{busy ? 'Сохраняем…' : draft.frozen ? 'Повторить отправку' : 'Отправить отзыв'}</button>
  </form>}</Modal>
}

export default function PublicSupport({ safe, projectId, analysisId, start, training }: { safe: boolean; projectId?: string; analysisId?: string; start: () => void; training?: Training }) {
  const [mode, setMode] = useState<'wizard' | 'feedback' | null>(null)
  const autoChecked = useRef(false)
  useEffect(startActivity, [])
  useEffect(() => { const editing = () => { autoChecked.current = true }; document.addEventListener('input', editing); return () => document.removeEventListener('input', editing) }, [])
  function openWizard() { autoChecked.current = true; setMode('wizard'); void track('wizard_started') }
  useEffect(() => {
    if (!safe || autoChecked.current) return
    autoChecked.current = true
    if (!remembered()) openWizard()
  }, [safe])
  function finish(completed: boolean) {
    try { localStorage.setItem('construction-onboarding', completed ? 'completed' : 'skipped') } catch { /* Manual reopening remains available. */ }
    void track(completed ? 'wizard_completed' : 'wizard_skipped')
    setMode(null)
  }
  return <><div className="public-support"><button type="button" onClick={openWizard}>Как пользоваться</button><button type="button" onClick={() => { autoChecked.current = true; setMode('feedback') }}>Обратная связь</button></div>
    {mode === 'wizard' && <OnboardingTour projectId={projectId} finish={finish} start={start} training={training} />}
    {mode === 'feedback' && <Feedback projectId={projectId} analysisId={analysisId} close={() => setMode(null)} />}
  </>
}
