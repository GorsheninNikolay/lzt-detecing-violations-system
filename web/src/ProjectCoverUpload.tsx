import { useEffect, useState } from 'react'
import { attributionHeaders } from './engagement'
import type { ProjectVisual } from './VariantDesign'

type PendingCover = { body: string; key: string }

const MAX_COVER_BYTES = 5_000_000
const DATABASE_NAME = 'project-cover-recovery'

function pendingKey(projectId: string) {
  return `project-cover-pending:${projectId}`
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore('requests')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function savePending(projectId: string, pending: PendingCover): Promise<void> {
  let saved = false
  try { sessionStorage.setItem(pendingKey(projectId), JSON.stringify(pending)); saved = true } catch { /* IndexedDB can hold larger photographs. */ }
  if (typeof indexedDB === 'undefined') {
    if (!saved) throw new Error('storage_unavailable')
    return
  }
  try {
    const db = await openDatabase()
    try {
      await new Promise<void>((resolve, reject) => {
        const transaction = db.transaction('requests', 'readwrite')
        transaction.objectStore('requests').put(pending, projectId)
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => reject(transaction.error)
      })
    } finally { db.close() }
  } catch (error) { if (!saved) throw error }
}

async function recoverPending(projectId: string): Promise<PendingCover | null> {
  const saved = sessionStorage.getItem(pendingKey(projectId))
  if (saved) {
    try { return JSON.parse(saved) as PendingCover } catch { sessionStorage.removeItem(pendingKey(projectId)) }
  }
  if (typeof indexedDB === 'undefined') return null
  const db = await openDatabase()
  try {
    return await new Promise<PendingCover | null>((resolve, reject) => {
      const transaction = db.transaction('requests', 'readonly')
      const request = transaction.objectStore('requests').get(projectId)
      request.onsuccess = () => resolve((request.result as PendingCover | undefined) ?? null)
      request.onerror = () => reject(request.error)
    })
  } finally { db.close() }
}

async function clearPending(projectId: string): Promise<void> {
  sessionStorage.removeItem(pendingKey(projectId))
  if (typeof indexedDB === 'undefined') return
  const db = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('requests', 'readwrite')
      transaction.objectStore('requests').delete(projectId)
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
    })
  } finally { db.close() }
}

async function normalizeCover(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  try {
    if (!bitmap.width || !bitmap.height || bitmap.width * bitmap.height > 25_000_000) throw new Error('invalid_image')
    const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(bitmap.width * scale))
    canvas.height = Math.max(1, Math.round(bitmap.height * scale))
    const context = canvas.getContext('2d')
    if (!context) throw new Error('canvas_unavailable')
    context.imageSmoothingQuality = 'high'
    context.fillStyle = '#fff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const output = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('canvas_unavailable')), 'image/jpeg', 0.82)
    })
    if (output.type !== 'image/jpeg' || !output.size) throw new Error('invalid_output')
    if (output.size > MAX_COVER_BYTES) throw new Error('output_too_large')
    return output
  } finally { bitmap.close() }
}

function readBase64(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const data = reader.result
      if (typeof data !== 'string' || !data.includes(',')) reject(new Error('invalid_file'))
      else resolve(data.slice(data.indexOf(',') + 1))
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export default function ProjectCoverUpload({ project, onUpdated }: { project: ProjectVisual; onUpdated: (sha: string) => void }) {
  const [pending, setPending] = useState<PendingCover | null>(null)
  const [restoring, setRestoring] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    void recoverPending(project.id).then(saved => {
      if (!active) return
      setPending(saved)
      if (saved) setError('Предыдущая отправка не завершена. Можно повторить её без смены фотографии.')
    }).catch(() => { if (active) setError('Не удалось восстановить прежнюю отправку. Выберите фотографию снова.') }).finally(() => { if (active) setRestoring(false) })
    return () => { active = false }
  }, [project.id])

  async function submit(request: PendingCover) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch(`/api/projects/${project.id}/cover`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': request.key, ...attributionHeaders() },
        body: request.body,
      })
      if (!response.ok) {
        setError(response.status >= 500 ? 'Не удалось подтвердить сохранение обложки. Повторите отправку без смены фотографии.' : 'Сервер отклонил обложку. Повторите отправку или выберите другую фотографию.')
        return
      }
      const data = await response.json() as { cover_sha256?: string }
      if (!data.cover_sha256) {
        setError('Не удалось подтвердить сохранение обложки. Повторите отправку.')
        return
      }
      await clearPending(project.id).catch(() => {})
      setPending(null)
      try {
        const currentResponse = await fetch('/api/projects')
        if (!currentResponse.ok) throw new Error('current_cover_unavailable')
        const current = (await currentResponse.json() as { projects: ProjectVisual[] }).projects.find(item => item.id === project.id)
        if (!current?.cover_sha256) throw new Error('current_cover_unavailable')
        onUpdated(current.cover_sha256)
        setNotice(current.cover_sha256 === data.cover_sha256
          ? 'Обложка обновлена.'
          : 'Другой посетитель уже заменил обложку. Показана актуальная фотография.')
      } catch {
        setError('Обложка сохранена, но текущую версию проверить не удалось. Обновите страницу.')
      }
    } catch {
      setError('Ответ сервера не получен. Возможно, обложка сохранилась. Повторите отправку без смены фотографии.')
    } finally { setBusy(false) }
  }

  async function choose(file: File) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('Выберите фотографию JPEG, PNG или WEBP.')
      return
    }
    if (!file.size || file.size > MAX_COVER_BYTES) {
      setError('Размер фотографии должен быть не больше 5 МБ.')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      let body: string
      try { body = JSON.stringify({ data: await readBase64(await normalizeCover(file)) }) }
      catch (cause) {
        setError(cause instanceof Error && cause.message === 'output_too_large' ? 'После подготовки фотография больше 5 МБ. Выберите другое изображение.' : 'Не удалось прочитать фотографию. Выберите другой файл JPEG, PNG или WEBP.')
        return
      }
      const request = { body, key: crypto.randomUUID() }
      try { await savePending(project.id, request) }
      catch {
        setError('Новая обложка не отправлена: браузер не смог сохранить запрос для безопасного повтора. Разрешите хранение данных сайта или освободите место, затем выберите фотографию снова.')
        return
      }
      setPending(request)
      await submit(request)
    } finally { setBusy(false) }
  }

  return <div className="project-cover-upload">
    <label className={`project-cover-picker${busy || restoring ? ' is-disabled' : ''}`}>
      <span>{project.cover_sha256 ? 'Заменить обложку' : 'Добавить обложку'}</span>
      <input type="file" accept="image/jpeg,image/png,image/webp" aria-label={`Загрузить обложку проекта ${project.name}`} disabled={busy || restoring} onChange={event => {
        const file = event.currentTarget.files?.[0]
        event.currentTarget.value = ''
        if (file) void choose(file)
      }} />
    </label>
    <p className="project-cover-formats">JPEG, PNG или WEBP, до 5 МБ.</p>
    {busy && <p role="status">{pending ? 'Сохраняем обложку…' : 'Подготавливаем фотографию…'}</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {pending && !busy && <button type="button" className="secondary" onClick={() => void submit(pending)}>Повторить отправку обложки</button>}
  </div>
}
