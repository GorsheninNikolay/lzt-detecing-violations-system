import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import PasswordField from './PasswordField'

afterEach(cleanup)
it('shows and hides the entered password without submitting or changing it', () => {
  const submit = vi.fn(event => event.preventDefault())
  render(<form onSubmit={submit}><label>Пароль<PasswordField name="password" defaultValue="demo-pass" /></label></form>)
  const input = screen.getByLabelText('Пароль') as HTMLInputElement
  expect(input.type).toBe('password')
  fireEvent.click(screen.getByRole('button', { name: 'Показать пароль' }))
  expect(input.type).toBe('text')
  expect(input.value).toBe('demo-pass')
  fireEvent.click(screen.getByRole('button', { name: 'Скрыть пароль' }))
  expect(input.type).toBe('password')
  expect(input.value).toBe('demo-pass')
  expect(submit).not.toHaveBeenCalled()
})
