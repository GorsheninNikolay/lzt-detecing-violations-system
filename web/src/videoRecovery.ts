export type PendingVideo = { key: string; query: string; file: File }
const marker = (scope: string) => `video-pending:${scope}`
export const videoScope = (accountId: string, projectId: string) => JSON.stringify([accountId, projectId])
export function hasPendingVideo(scope: string) { try { return !!localStorage.getItem(marker(scope)) } catch { return false } }
async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('video-recovery', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('requests')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}
async function transaction<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore, result: (value: T) => void) => void): Promise<T> {
  const db = await database()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction('requests', mode)
      let result: T
      action(tx.objectStore('requests'), value => { result = value })
      tx.oncomplete = () => resolve(result)
      tx.onerror = () => reject(tx.error)
      tx.onabort = () => reject(tx.error ?? new Error('video_recovery_storage_failed'))
    })
  } finally { db.close() }
}
export async function savePendingVideo(scope: string, pending: PendingVideo): Promise<PendingVideo> {
  const saved = await transaction<PendingVideo>('readwrite', (store, result) => {
    const request = store.get(scope)
    request.onsuccess = () => {
      const existing = request.result as PendingVideo | undefined
      if (existing) result(existing)
      else {
        store.add(pending, scope)
        result(pending)
      }
    }
  })
  try { localStorage.setItem(marker(scope), saved.key) } catch { /* IndexedDB remains the source of recovery data. */ }
  return saved
}
export async function restorePendingVideo(scope: string): Promise<PendingVideo | null> {
  return transaction<PendingVideo | null>('readonly', (store, result) => {
    const request = store.get(scope)
    request.onsuccess = () => result(request.result ?? null)
  })
}
export async function clearPendingVideo(scope: string, expectedKey: string): Promise<boolean> {
  const cleared = await transaction<boolean>('readwrite', (store, result) => {
    const request = store.get(scope)
    request.onsuccess = () => {
      if ((request.result as PendingVideo | undefined)?.key !== expectedKey) { result(false); return }
      store.delete(scope)
      result(true)
    }
  })
  try { if (cleared && localStorage.getItem(marker(scope)) === expectedKey) localStorage.removeItem(marker(scope)) } catch { /* A stale marker only opens an empty video form. */ }
  return cleared
}
