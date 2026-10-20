import { useState } from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import CaptureDateTime from './CaptureDateTime'
import { validLocalPeriod } from './localPeriod'

afterEach(cleanup)
function Field() {
  const [value, setValue] = useState('')
  return <><CaptureDateTime label="Съёмка" value={value} onChange={setValue} /><output data-testid="value">{value}</output></>
}
it('retains partial local values until both fields are complete and shows the readable caption', () => {
  render(<Field />)
  fireEvent.change(screen.getByLabelText('Съёмка: дата'), { target: { value: '2026-10-20' } })
  expect(screen.getByTestId('value').textContent).toBe('2026-10-20T')
  expect(validLocalPeriod(screen.getByTestId('value').textContent!)).toBe(false)
  fireEvent.change(screen.getByLabelText('Съёмка: время'), { target: { value: '16:14' } })
  expect(screen.getByTestId('value').textContent).toBe('2026-10-20T16:14')
  expect(screen.getByText(/20 октября 2026, 16:14/)).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Съёмка: дата'), { target: { value: '' } })
  expect(screen.getByTestId('value').textContent).toBe('T16:14')
  expect(validLocalPeriod(screen.getByTestId('value').textContent!)).toBe(false)
})
it('connects both disabled controls to the validation error', () => {
  render(<CaptureDateTime id="capture" label="Съёмка" value="2026-10-20T" onChange={() => {}} disabled error="Укажите время" />)
  for (const label of ['Съёмка: дата', 'Съёмка: время']) {
    const input = screen.getByLabelText(label)
    expect(input).toHaveProperty('disabled', true)
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(input.getAttribute('aria-describedby')).toContain('capture-error')
  }
})
