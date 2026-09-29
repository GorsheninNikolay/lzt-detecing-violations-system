import { afterEach, expect, it, vi } from 'vitest'
import { randomUUID } from './randomUUID'

afterEach(() => vi.unstubAllGlobals())

it('creates an RFC 4122 version 4 UUID with getRandomValues when randomUUID is unavailable', () => {
  vi.stubGlobal('crypto', { getRandomValues: (bytes: Uint8Array) => { bytes.fill(0xff); return bytes } })
  expect(randomUUID()).toBe('ffffffff-ffff-4fff-bfff-ffffffffffff')
})
