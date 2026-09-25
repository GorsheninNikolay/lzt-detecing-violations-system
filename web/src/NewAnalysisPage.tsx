import { useRef, useState, type ChangeEvent, type DragEvent, type ReactNode } from 'react'

export function UploadZone({ onFiles, onCamera, disabled, cameraDisabled, invalid, describedBy }: {
  onFiles: (files: File[]) => void
  onCamera: () => void
  disabled: boolean
  cameraDisabled: boolean
  invalid: boolean
  describedBy?: string
}) {
  const dragDepth = useRef(0)
  const [dragging, setDragging] = useState(false)

  function select(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length) onFiles(files)
  }

  function enter(event: DragEvent<HTMLDivElement>) {
    if (disabled) return
    event.preventDefault()
    dragDepth.current += 1
    setDragging(true)
  }

  function leave(event: DragEvent<HTMLDivElement>) {
    if (disabled) return
    event.preventDefault()
    dragDepth.current = Math.max(0, dragDepth.current - 1)
    if (!dragDepth.current) setDragging(false)
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    dragDepth.current = 0
    setDragging(false)
    if (!disabled && event.dataTransfer.files.length) onFiles(Array.from(event.dataTransfer.files))
  }

  return <div className="upload-zone" role="group" aria-label="Загрузка кадров" data-dragging={dragging} onDragEnter={enter} onDragOver={event => { if (!disabled) event.preventDefault() }} onDragLeave={leave} onDrop={drop}>
    <p className="upload-zone-title">Перетащите кадры сюда</p>
    <p className="muted">или выберите файлы с устройства</p>
    <div className="upload-actions">
      <label className="file-button secondary" htmlFor="images">Выбрать изображение</label>
      <input id="images" type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" multiple onChange={select} disabled={disabled} aria-invalid={invalid} aria-describedby={describedBy} />
      <button className="secondary" type="button" onClick={onCamera} disabled={cameraDisabled}>Снять камерой</button>
    </div>
  </div>
}

export default function NewAnalysisPage({ children }: { children: ReactNode }) {
  return <section className="new-analysis-page">{children}</section>
}
