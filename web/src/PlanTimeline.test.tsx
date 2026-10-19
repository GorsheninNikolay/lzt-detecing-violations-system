import { render, screen, fireEvent } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import PlanTimeline from './PlanTimeline'
it('connects only the nearest finished works and opens the selected work', () => {
  const select = vi.fn()
  render(<PlanTimeline entries={[{ starts_at:'2026-01-01', ends_at:'2026-01-02' }, { starts_at:'2026-01-02', ends_at:'2026-01-04' }, { starts_at:'2026-01-03', ends_at:'2026-01-05' }, { starts_at:'2026-01-06', ends_at:'2026-01-07' }]} title={index => `Работа ${index + 1}`} selected={0} select={select} />)
  const last = screen.getByRole('button', { name: /4\. Работа 4/ })
  expect(last.textContent).toContain('После: 3')
  expect(last.textContent).not.toContain('После: 2')
  fireEvent.click(last)
  expect(select).toHaveBeenCalledWith(3)
})
