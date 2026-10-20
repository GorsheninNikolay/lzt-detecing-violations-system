import { useId } from 'react'
import { validLocalPeriod } from './localPeriod'

export default function CaptureDateTime({ id, label, value, onChange, disabled, error }: { id?: string; label: string; value: string; onChange: (value: string) => void; disabled?: boolean; error?: string }) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const [date = '', time = ''] = value.split('T')
  const captionId = `${inputId}-caption`
  const describedBy = `${captionId}${error ? ` ${inputId}-error` : ''}`
  const caption = validLocalPeriod(value) ? `${new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).replace(/ г\.$/, '')}, ${new Date(value).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}` : value ? 'Укажите существующие местные дату и время.' : 'Дата и время не указаны.'
  const update = (nextDate: string, nextTime: string) => onChange(nextDate || nextTime ? `${nextDate}T${nextTime}` : '')
  return <div className="field capture-date-time" role="group" aria-label={label}><span>{label}</span><div className="capture-date-time-fields"><label htmlFor={inputId}>Дата<input id={inputId} type="date" aria-label={`${label}: дата`} value={date} disabled={disabled} onChange={event => update(event.target.value, time)} aria-invalid={!!error} aria-describedby={describedBy} /></label><label htmlFor={`${inputId}-time`}>Время<input id={`${inputId}-time`} type="time" aria-label={`${label}: время`} value={time} disabled={disabled} onChange={event => update(date, event.target.value)} aria-invalid={!!error} aria-describedby={describedBy} /></label></div><span id={captionId} className="hint">{caption} Время по часовому поясу устройства.</span></div>
}
