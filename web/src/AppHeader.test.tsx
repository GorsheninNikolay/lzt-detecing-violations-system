import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import AppHeader from './AppHeader'

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
it('shows secondary links inline until the measured row runs out of space', () => {
  let width = 1000
  let resized = () => {}
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function (this: HTMLElement) { return this.classList.contains('topbar-inner') ? width : 0 })
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    const measured = this.classList.contains('project-switcher') ? 180 : this.classList.contains('primary-nav') ? 160 : this.classList.contains('new-analysis-link') ? 150 : this.classList.contains('secondary-nav-measure') ? 170 : 0
    return { width: measured, height: 44, top: 0, left: 0, bottom: 44, right: measured, x: 0, y: 0, toJSON() {} }
  })
  vi.stubGlobal('ResizeObserver', class { constructor(callback: () => void) { resized = callback } observe() {} disconnect() {} })
  render(<AppHeader route="projects" historyPath="/archive" navigate={vi.fn()} onNewAnalysis={vi.fn()} />)
  const details = document.querySelector('.more-menu') as HTMLDetailsElement
  expect(details.open).toBe(true)
  expect((details.querySelector('summary') as HTMLElement).hidden).toBe(true)
  expect(screen.getByRole('link', { name: 'Документация API' })).toBeTruthy()
  expect(screen.queryByText('Архив анализов без проекта')).toBeNull()
  expect(screen.queryByRole('link', { name: 'О системе' })).toBeNull()
  expect(screen.queryByRole('button', { name: /Движение/ })).toBeNull()
  act(() => { width = 600; resized() })
  expect(details.open).toBe(false)
  expect((details.querySelector('summary') as HTMLElement).hidden).toBe(false)
  act(() => { width = 1000; resized() })
  expect(details.open).toBe(true)
  expect((details.querySelector('summary') as HTMLElement).hidden).toBe(true)
})
