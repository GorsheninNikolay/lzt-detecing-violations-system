import './PlanExcelImport.css'
import { useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

type ImportedEntry = { catalog_work_id: string; title: string; start_at: string; end_at: string; state: string; stage_key: string | null; expected_equipment: string[]; allowed_equipment: string[]; excluded_equipment: string[] }
type Preview = { entries: ImportedEntry[]; errors: { row: number | null; message: string }[]; timezone: string; date_note: string; expected_revision: number }
export default function PlanExcelImport({ zoneId, disabled, dirty, projectId, saved, onBusyChange, onDraftChange }: { zoneId: string; disabled: boolean; dirty: boolean; projectId: string; saved: () => Promise<void>; onBusyChange?: (busy: boolean) => void; onDraftChange?: (dirty: boolean) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const live = useRef(true)
  useEffect(() => { live.current = true; return () => { live.current = false } }, [])
  useEffect(() => { onBusyChange?.(busy); return () => onBusyChange?.(false) }, [busy, onBusyChange])
  useEffect(() => { onDraftChange?.(!!preview); return () => onDraftChange?.(false) }, [preview, onDraftChange])
  async function upload(file?: File) {
    if (!file || disabled || busy) return
    setPreview(null); setError('')
    if (!file.name.toLowerCase().endsWith('.xlsx') || file.size > 5 * 1024 * 1024) { setError('Выберите XLSX размером до 5 МБ.'); return }
    setBusy(true)
    try {
      const response = await fetch(`/api/zones/${zoneId}/plan/import-preview`, { method: 'POST', headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }, body: file })
      if (!response.ok) throw new Error('Не удалось прочитать файл. Проверьте доступ к проекту и повторите загрузку.')
      const parsed = await response.json() as Preview
      if (live.current) setPreview(parsed)
    } catch (cause) { if (live.current) setError(cause instanceof Error ? cause.message : 'Ошибка загрузки') } finally { if (live.current) { setBusy(false); if (input.current) input.current.value = '' } }
  }
  async function apply() {
    if (!preview || preview.errors.length || disabled || busy) return
    if (dirty && !window.confirm('Заменить несохранённый черновик планом из Excel?')) return
    setBusy(true); setError('')
    try {
      const response = await fetch(`/api/zones/${zoneId}/plan`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: preview.expected_revision, entries: preview.entries.map(({ title: _title, ...entry }) => entry) }) })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({})) as { code?: string }
        throw new Error(detail.code === 'plan_revision_conflict' ? 'План изменился. Загрузите Excel заново, чтобы проверить текущую версию.' : 'Не удалось сохранить план. Проверьте текущую версию перед повтором.')
      }
      const result = await response.json() as { revision_number: number }
      const readback = await fetch(`/api/zones/${zoneId}/plan?revision=${result.revision_number}`)
      if (!readback.ok || (await readback.json() as { revision_number: number }).revision_number !== result.revision_number) throw new Error('План сохранён, но чтение новой версии не подтверждено. Обновите страницу.')
      if (!live.current) return
      await saved()
      if (!live.current) return
      // Clear the workspace navigation guard before enabling the next lesson.
      flushSync(() => { setPreview(null); setBusy(false); onDraftChange?.(false); onBusyChange?.(false) })
      dispatchEvent(new CustomEvent('tutorial-plan-imported', { detail: { id: projectId } }))
    } catch (cause) { if (live.current) setError(cause instanceof Error ? cause.message : 'Ошибка сохранения') } finally { if (live.current) setBusy(false) }
  }
  return <section className="plan-excel-import" aria-label="Импорт плана из Excel">
    <div className="plan-actions"><a href={`/api/zones/${zoneId}/plan/template.xlsx`} download>Скачать шаблон Excel</a><a data-tutorial="plan-example" href={`/api/zones/${zoneId}/plan/template.xlsx?tutorial=true`} download>Скачать учебный Excel</a></div>
    <div className="plan-excel-drop" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); void upload(event.dataTransfer.files[0]) }}><p>Перетащите план XLSX сюда или выберите файл. До 5 МБ и 1000 работ.</p><input ref={input} type="file" accept=".xlsx" aria-label="План Excel" disabled={disabled || busy} onChange={event => void upload(event.target.files?.[0])} /></div>
    {busy && <p role="status">Обрабатываем план…</p>}{error && <p role="alert" className="error">{error}</p>}
    {preview && <div><h3>Предпросмотр замены плана</h3><p>Часовой пояс: {preview.timezone}. {preview.date_note} Замена создаст новую версию; предыдущие версии сохранятся.</p>{preview.errors.length > 0 && <ul role="alert">{preview.errors.map((item, index) => <li key={index}>{item.row ? `Строка ${item.row}: ` : ''}{item.message}</li>)}</ul>}{preview.entries.length > 0 && <table><thead><tr><th>Работа</th><th>Начало</th><th>Окончание</th></tr></thead><tbody>{preview.entries.map((entry,index) => <tr key={index}><td>{entry.title}</td><td>{entry.start_at}</td><td>{entry.end_at}</td></tr>)}</tbody></table>}<button type="button" className="primary" data-tutorial="plan-import" disabled={disabled || busy || !!preview.errors.length || !preview.entries.length} onClick={() => void apply()}>Заменить план</button><button type="button" className="secondary" disabled={busy} onClick={() => setPreview(null)}>Отмена</button></div>}
  </section>
}
