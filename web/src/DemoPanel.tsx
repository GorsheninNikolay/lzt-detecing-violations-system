import { useState } from 'react'
const states = { empty: 'Пустой проект', upload: 'Загрузка', analyzing: 'Анализ', result: 'Результат', error: 'Ошибка', recovery: 'Восстановление' }
export default function DemoPanel() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function reset(state: string) {
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/__demo/state', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state }) })
      if (!response.ok) throw new Error()
      for (const key of ['observation-pending', 'observation-pending-id', 'onboarding-training-request']) sessionStorage.removeItem(key)
      for (const key of Object.keys(localStorage)) if (key.startsWith('annotation:')) localStorage.removeItem(key)
      await new Promise<void>((resolve, reject) => { const request = indexedDB.deleteDatabase('observation-recovery'); request.onsuccess = () => resolve(); request.onerror = () => reject(request.error); request.onblocked = () => reject(new Error('storage_busy')) })
      location.href = state === 'empty' || state === 'result' ? '/' : state === 'upload' || state === 'recovery' ? '/projects/11111111-1111-4111-8111-111111111111/new' : '/projects/11111111-1111-4111-8111-111111111111/runs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    } catch { setError('Сброс не выполнен. Повторите.'); setBusy(false) }
  }
  return <aside className="demo-panel" aria-label="Демонстрационные состояния"><details><summary>Демонстрация · локальные данные</summary><p>Фотографии, рамки и выводы подготовлены для сравнения интерфейсов. Это не оценка качества модели. Загрузка и изменения сохраняются только в памяти этого сервера.</p><div>{Object.entries(states).map(([state, label]) => <button key={state} disabled={busy} onClick={() => void reset(state)}>{label}</button>)}</div><p>Выбор состояния сбрасывает демонстрационные изменения. «Восстановление» возвращает временную ошибку первой отправки.</p>{error && <p role="alert">{error}</p>}</details></aside>
}
