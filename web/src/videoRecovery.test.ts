// @vitest-environment node
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearPendingVideo, hasPendingVideo, restorePendingVideo, savePendingVideo, videoScope, type PendingVideo } from './videoRecovery'

beforeEach(() => {
  vi.stubGlobal('indexedDB', new IDBFactory())
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value) },
    removeItem: (key: string) => { data.delete(key) },
  })
})
afterEach(() => vi.unstubAllGlobals())
const pending = (key: string): PendingVideo => ({
  key, query: `project_id=project&zone_id=zone&cloud_provider=deepseek&token=${key}`,
  file: new File([new Uint8Array([0, 255, 7, 42])], `${key}.mov`, { type: 'video/quicktime', lastModified: 1234 }),
})
describe('durable IndexedDB video recovery', () => {
  it('reopens the stored File bytes, identity and original query through a fresh module', async () => {
    const scope = videoScope('alice', 'project')
    const original = pending('original')
    await savePendingVideo(scope, original)
    expect(hasPendingVideo(scope)).toBe(true)
    vi.resetModules()
    const reopened = await import('./videoRecovery')
    const restored = await reopened.restorePendingVideo(scope)
    expect(restored?.key).toBe(original.key)
    expect(restored?.query).toBe(original.query)
    expect(restored?.file).toBeInstanceOf(File)
    expect(restored?.file.name).toBe('original.mov')
    expect(restored?.file.type).toBe('video/quicktime')
    expect(restored?.file.lastModified).toBe(1234)
    expect(new Uint8Array(await restored!.file.arrayBuffer())).toEqual(new Uint8Array([0, 255, 7, 42]))
    expect(await reopened.restorePendingVideo(videoScope('bob', 'project'))).toBe(null)
    expect(await reopened.restorePendingVideo(videoScope('alice', 'other-project'))).toBe(null)
  })
  it('serializes concurrent tabs and keeps the first request without replacing its file', async () => {
    const scope = videoScope('alice', 'project')
    const [first, second] = await Promise.all([savePendingVideo(scope, pending('first')), savePendingVideo(scope, pending('second'))])
    expect(second.key).toBe(first.key)
    const restored = await restorePendingVideo(scope)
    expect(restored?.key).toBe(first.key)
    expect(restored?.file.name).toBe(first.file.name)
    expect(restored?.query).toBe(first.query)
  })
  it('conditionally clears only the acknowledged key and preserves a newer request', async () => {
    const scope = videoScope('alice', 'project')
    await savePendingVideo(scope, pending('old'))
    expect(await clearPendingVideo(scope, 'other-tab')).toBe(false)
    expect((await restorePendingVideo(scope))?.key).toBe('old')
    expect(await clearPendingVideo(scope, 'old')).toBe(true)
    await savePendingVideo(scope, pending('new'))
    expect(await clearPendingVideo(scope, 'old')).toBe(false)
    expect((await restorePendingVideo(scope))?.key).toBe('new')
    expect(hasPendingVideo(scope)).toBe(true)
    expect(await clearPendingVideo(scope, 'new')).toBe(true)
    expect(await restorePendingVideo(scope)).toBe(null)
    expect(hasPendingVideo(scope)).toBe(false)
  })
})
