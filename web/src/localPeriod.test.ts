import { describe, expect, it } from 'vitest'
import { validLocalPeriod } from './localPeriod'

describe('local capture times', () => {
  it('rejects normalized calendar dates', () => {
    expect(validLocalPeriod('2026-02-30T12:00')).toBe(false)
    expect(validLocalPeriod('2026-10-20T12:00')).toBe(true)
    expect(validLocalPeriod('invalid')).toBe(false)
  })
  it.skipIf(Intl.DateTimeFormat().resolvedOptions().timeZone !== 'Europe/Berlin')('rejects the daylight-saving gap in Europe/Berlin', () => {
    const gap = '2026-03-29T02:30'
    const date = new Date(gap)
    expect(date.getHours()).toBe(3)
    expect(validLocalPeriod(gap)).toBe(false)
  })
})
