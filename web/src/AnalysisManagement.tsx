import { useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { AccountIdentity } from './AccountIdentity'
import { accountError } from './AccountShell'
import { randomUUID } from './randomUUID'

class RequestFailure extends Error {
  constructor(message: string, readonly definitive = false) { super(message) }
}
const failure = 'Обратитесь к администратору'
async function request(path: string, method = 'GET', key?: string) {
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([
      (async () => {
        const response = await fetch(`/api${path}`, { method, signal: controller.signal, credentials: 'same-origin', headers: key ? { 'Idempotency-Key': key } : undefined })
        const data = await response.json()
        if (!response.ok) throw new RequestFailure(response.status >= 500 ? failure : accountError(data), response.status >= 400 && response.status < 500)
        return data
      })(),
      new Promise<never>((_, reject) => { timer = setTimeout(() => { controller.abort(); reject(new Error(failure)) }, 180000) }),
    ])
  } catch (error) { throw error instanceof RequestFailure ? error : new RequestFailure(failure) }
  finally { clearTimeout(timer) }
}
type StageIdentity = { key: string; parent: string; attempt?: string; projectId?: string | null }
type Deletion = { deletion_id?: string; status?: 'cleaning' | 'completed' }
function isUuid(value: unknown): value is string { return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function isStageIdentity(value: unknown): value is StageIdentity {
  return isRecord(value) && isUuid(value.key) && isUuid(value.parent)
    && (value.attempt === undefined || isUuid(value.attempt))
    && (value.projectId === undefined || value.projectId === null || isUuid(value.projectId))
    && Object.keys(value).every(key => ['key', 'parent', 'attempt', 'projectId'].includes(key))
}
function isDeletionOperation(value: unknown): value is Required<Deletion> {
  return isRecord(value) && isUuid(value.deletion_id) && (value.status === 'cleaning' || value.status === 'completed')
    && Object.keys(value).every(key => ['deletion_id', 'status'].includes(key))
}
function isDeletion(value: unknown): value is Deletion { return isRecord(value) && (Object.keys(value).length === 0 || isDeletionOperation(value)) }
function saved<T>(key: string, valid: (value: unknown) => value is T): T | null {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) return null
    const value: unknown = JSON.parse(raw)
    if (valid(value)) return value
  } catch { /* A malformed cache entry cannot authorize a request. */ }
  try { localStorage.removeItem(key) } catch { /* Storage can be unavailable. */ }
  return null
}

export function StageRetry({ runId, stage, attemptId, cost, onAccepted, projectId }: { projectId?: string | null; runId: string; stage: string; attemptId?: string; cost?: boolean; onAccepted: () => void }) {
  const account = useContext(AccountIdentity)
  const storage = `stage-recovery:${account}:${runId}:${stage}`
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [pending, setPending] = useState(() => saved(storage, isStageIdentity))
  const live = useRef(true), lock = useRef(false)
  useEffect(() => { live.current = true; return () => { live.current = false } }, [])
  useEffect(() => {
    if (pending && attemptId && attemptId !== pending.parent) {
      localStorage.removeItem(storage); setPending(null)
    }
  }, [attemptId, pending, storage])
  async function retry() {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try {
      const identity = pending ?? { key: randomUUID(), parent: attemptId, projectId }
      if (!isStageIdentity(identity)) throw new Error(failure)
      localStorage.setItem(storage, JSON.stringify(identity)); setPending(identity)
      const data = await request(`/runs/${runId}/stages/${stage}/retry`, 'POST', identity.key)
      if (!isUuid(data.attempt_id) || data.run_id !== runId) throw new Error(failure)
      localStorage.setItem(storage, JSON.stringify({ ...identity, attempt: data.attempt_id }))
      if (live.current) { setPending({ ...identity, attempt: data.attempt_id }); onAccepted() }
    } catch { if (live.current) setError(failure) }
    finally { lock.current = false; if (live.current) setBusy(false) }
  }
  return <div className="stage-recovery">{cost && <p>Этот этап может повторно расходовать средства.</p>}{pending?.attempt && !busy && <p role="status">Перезапуск принят. Обновляем состояние…</p>}<button type="button" className="secondary" disabled={busy} aria-busy={busy} onClick={() => void retry()}>{busy ? 'Перезапускаем этап…' : 'Перезапустить этап'}</button>{error && <p role="alert" className="error">{error}</p>}</div>
}

export function Deletable({ kind, id, name, allowed, onCompleted, children }: { kind: 'projects' | 'runs'; id: string; name: string; allowed: boolean; onCompleted: () => void; children: ReactNode }) {
  const account = useContext(AccountIdentity)
  const storage = `pending-deletion:${account}:${kind}:${id}`
  const [pending, setPending] = useState<Deletion | null>(() => saved(storage, isDeletion))
  const [confirm, setConfirm] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const live = useRef(true), lock = useRef(false), completed = useRef(onCompleted)
  completed.current = onCompleted
  const dialog = useRef<HTMLDialogElement>(null), opener = useRef<HTMLButtonElement>(null)
  useEffect(() => { live.current = true; return () => { live.current = false } }, [])
  useEffect(() => { if (confirm) dialog.current?.showModal(); else dialog.current?.close() }, [confirm])
  function accept(data: Deletion) {
    if (!isDeletionOperation(data)) throw new Error(failure)
    if (!live.current) return
    localStorage.setItem(storage, JSON.stringify(data)); setPending(data)
    if (data.status === 'completed') {
      localStorage.removeItem(storage)
      for (const key of Object.keys(localStorage)) {
        if (kind === 'runs' && key.startsWith(`stage-recovery:${account}:${id}:`) || kind === 'projects' && key.startsWith(`stage-recovery:${account}:`) && saved(key, isStageIdentity)?.projectId === id) localStorage.removeItem(key)
      }
      completed.current()
    }
  }
  async function recover() {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try {
      if (!pending) { localStorage.setItem(storage, '{}'); setPending({}) }
      setConfirm(false)
      const data = await request(pending?.deletion_id ? `/deletions/${pending.deletion_id}` : `/${kind}/${id}`, pending?.deletion_id ? 'GET' : 'DELETE')
      if (!live.current) return
      if (!isDeletionOperation(data)) throw new Error(failure)
      if (!pending?.deletion_id && data.status === 'completed' && typeof data.deletion_id === 'string') {
        localStorage.setItem(storage, JSON.stringify({ deletion_id: data.deletion_id, status: 'cleaning' })); if (live.current) setPending({ deletion_id: data.deletion_id, status: 'cleaning' })
        accept(await request(`/deletions/${data.deletion_id}`))
      } else accept(data)
      if (live.current) setConfirm(false)
    } catch (reason) { if (live.current) { if (reason instanceof RequestFailure && reason.definitive && !pending?.deletion_id) { localStorage.removeItem(storage); setPending(null) } setError(reason instanceof RequestFailure ? reason.message : failure) } }
    finally { lock.current = false; if (live.current) setBusy(false) }
  }
  useEffect(() => {
    if (!pending?.deletion_id || pending.status === 'completed' || error) return
    const timer = setTimeout(() => { void recover() }, 1500)
    return () => clearTimeout(timer)
  }, [pending, error, busy])
  return <>{!pending && children}{!pending && error && <p role="alert" className="error">{error}</p>}{pending ? <section className="panel" aria-label="Удаление"><h2>Удаление {kind === 'projects' ? 'проекта' : 'анализа'}</h2><p role="status">{pending.deletion_id ? 'Файлы удаляются. Дождитесь подтверждения завершения.' : 'Результат запроса пока не подтверждён.'}</p>{error && <p className="error" role="alert">{error}</p>}<button type="button" disabled={busy} onClick={() => void recover()}>{busy ? 'Проверяем…' : 'Проверить статус удаления'}</button></section> : allowed && <button ref={opener} type="button" className="secondary danger-action" onClick={() => setConfirm(true)}>Удалить {kind === 'projects' ? 'проект' : 'анализ'}</button>}{confirm && <dialog ref={dialog} aria-labelledby="deletion-title" onCancel={event => { event.preventDefault(); if (!busy) { dialog.current?.close(); setConfirm(false); opener.current?.focus() } }}><h2 id="deletion-title">Удалить «{name}»?</h2><p>Это действие необратимо. {kind === 'projects' ? 'Все анализы и файлы проекта будут удалены.' : 'Анализ и его файлы будут удалены.'}</p><button type="button" disabled={busy} onClick={() => { dialog.current?.close(); setConfirm(false); opener.current?.focus() }}>Отмена</button><button type="button" className="danger-action" disabled={busy} onClick={() => void recover()}>{busy ? 'Удаляем…' : 'Удалить безвозвратно'}</button></dialog>}</>
}
