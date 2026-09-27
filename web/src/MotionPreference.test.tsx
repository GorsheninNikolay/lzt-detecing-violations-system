import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
const reduced = vi.hoisted(() => ({ value: false }))
vi.stubGlobal('matchMedia', () => ({ matches: reduced.value, addEventListener: () => {}, removeEventListener: () => {} }))
vi.mock('motion/react', () => ({ MotionConfig: ({ children }: { children: React.ReactNode }) => children, useReducedMotion: () => reduced.value }))
import { MotionPreference, MotionToggle } from './MotionPreference'
afterEach(() => { cleanup(); localStorage.clear(); reduced.value = false })
it('persists an explicit motion choice and respects OS reduction', () => {
  const first = render(<MotionPreference><MotionToggle /></MotionPreference>)
  fireEvent.click(screen.getByRole('button', { name: 'Движение: включено' }))
  expect(localStorage.getItem('analysis-motion')).toBe('off')
  expect(document.documentElement.dataset.motion).toBe('off')
  first.unmount()
  const second = render(<MotionPreference><MotionToggle /></MotionPreference>)
  expect(screen.getByRole('button', { name: 'Движение: выключено' })).toBeTruthy()
  second.unmount(); localStorage.setItem('analysis-motion', 'on'); reduced.value = true
  render(<MotionPreference><MotionToggle /></MotionPreference>)
  expect(document.documentElement.dataset.motion).toBe('off')
  const systemToggle = screen.getByRole('button', { name: 'Движение: выключено системой' })
  expect(systemToggle).toHaveProperty('disabled', true)
  fireEvent.click(systemToggle)
  expect(localStorage.getItem('analysis-motion')).toBe('on')
})
