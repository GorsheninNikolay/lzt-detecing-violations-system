import { useId, useState, type InputHTMLAttributes } from 'react'
import './PasswordField.css'

export default function PasswordField(props: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>) {
  const [visible, setVisible] = useState(false)
  const generatedId = useId()
  const id = props.id ?? generatedId
  return <span className="password-input">
    <input {...props} id={id} type={visible ? 'text' : 'password'} />
    <button className="password-visibility" type="button" disabled={props.disabled} aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'} aria-pressed={visible} aria-controls={id} onClick={() => setVisible(value => !value)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />{visible && <path d="m3 3 18 18" />}</svg>
    </button>
  </span>
}
