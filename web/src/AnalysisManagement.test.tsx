import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Deletable, StageRetry } from './AnalysisManagement'
import { AccountIdentity } from './AccountIdentity'

const json = (data: object, status = 200) => ({ ok: status < 400, status, json: async () => data })
beforeEach(() => {
  localStorage.clear()
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })
function stage(onAccepted = vi.fn(), attempt = '22222222-2222-4222-8222-222222222222') {
  return <AccountIdentity.Provider value="account"><StageRetry runId="run" stage="equipment_observation" attemptId={attempt} onAccepted={onAccepted} /></AccountIdentity.Provider>
}
function deletion(kind: 'projects' | 'runs' = 'runs', done = vi.fn(), allowed = true, id = 'target') {
  return <AccountIdentity.Provider value="account"><Deletable key={id} kind={kind} id={id} name="Объект" allowed={allowed} onCompleted={done}><p>Содержимое объекта</p></Deletable></AccountIdentity.Provider>
}
it('reuses the persisted stage key after unknown acceptance and reload, without automatic POST', async () => {
  const fetcher = vi.fn().mockRejectedValue(new Error('network secret'))
  vi.stubGlobal('fetch', fetcher)
  const view = render(stage())
  expect(fetcher).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Перезапустить этап' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('alert').textContent).toBe('Обратитесь к администратору')
  const key = fetcher.mock.calls[0][1].headers['Idempotency-Key']
  view.unmount()
  const accepted = vi.fn()
  fetcher.mockResolvedValue(json({ run_id: 'run', attempt_id: '33333333-3333-4333-8333-333333333333' }, 202))
  render(stage(accepted))
  expect(fetcher).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Перезапустить этап' }))
  await waitFor(() => expect(accepted).toHaveBeenCalledTimes(1))
  expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe(key)
  expect(fetcher.mock.calls[1][0]).toBe('/api/runs/run/stages/equipment_observation/retry')
})
it('bounds JSON acceptance at 180 seconds and blocks rapid double clicks', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn(async () => ({ ok: true, json: () => new Promise(() => {}) }))
  vi.stubGlobal('fetch', fetcher)
  render(stage())
  const button = screen.getByRole('button', { name: 'Перезапустить этап' })
  fireEvent.click(button); fireEvent.click(button)
  expect(fetcher).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(180000) })
  expect(screen.getByRole('alert').textContent).toBe('Обратитесь к администратору')
  expect(localStorage.getItem('stage-recovery:account:run:equipment_observation')).toBeTruthy()
})
it('ignores accepted stage responses after leaving the run', async () => {
  let finish!: (value: object) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { finish = resolve })))
  const accepted = vi.fn(), view = render(stage(accepted))
  fireEvent.click(screen.getByRole('button', { name: 'Перезапустить этап' }))
  view.unmount()
  await act(async () => { finish(json({ run_id: 'run', attempt_id: '33333333-3333-4333-8333-333333333333' }, 202)) })
  expect(accepted).not.toHaveBeenCalled()
})
it.each(['projects', 'runs'] as const)('confirms irreversible %s deletion and waits for cleanup GET', async kind => {
  const done = vi.fn(), fetcher = vi.fn().mockResolvedValueOnce(json({ deletion_id: '11111111-1111-4111-8111-111111111111', status: 'cleaning' }, 202)).mockResolvedValue(json({ deletion_id: '11111111-1111-4111-8111-111111111111', status: 'completed' }))
  vi.stubGlobal('fetch', fetcher)
  render(deletion(kind, done))
  fireEvent.click(screen.getByRole('button', { name: kind === 'projects' ? 'Удалить проект' : 'Удалить анализ' }))
  expect(screen.getByRole('dialog').textContent).toContain('Объект')
  expect(screen.getByRole('dialog').textContent).toContain('необратимо')
  fireEvent.click(screen.getByRole('button', { name: 'Удалить безвозвратно' }))
  await screen.findByText(/Файлы удаляются/)
  expect(screen.queryByText('Содержимое объекта')).toBeNull()
  expect(done).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Проверить статус удаления' }))
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1))
  expect(fetcher.mock.calls.map(call => call[0])).toEqual([`/api/${kind}/target`, '/api/deletions/11111111-1111-4111-8111-111111111111'])
})
it.each([['deletion_active_work', 'Дождитесь завершения обработки перед удалением.'], ['owner_required', 'Это действие доступно владельцу проекта.']])('keeps object visible after definitive rejection %s', async (detail, message) => {
  vi.stubGlobal('fetch', vi.fn(async () => json({ detail }, 409)))
  render(deletion())
  fireEvent.click(screen.getByRole('button', { name: 'Удалить анализ' }))
  fireEvent.click(screen.getByRole('button', { name: 'Удалить безвозвратно' }))
  await screen.findByText(message)
  expect(screen.getByText('Содержимое объекта')).toBeTruthy()
  expect(localStorage.getItem('pending-deletion:account:runs:target')).toBeNull()
})
it('recovers unknown DELETE acceptance after reload using the same target and preserves other caches', async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error('secret')).mockResolvedValue(json({ deletion_id: '11111111-1111-4111-8111-111111111111', status: 'completed' }, 202))
  vi.stubGlobal('fetch', fetcher)
  localStorage.setItem('stage-recovery:account:target:equipment_observation', '{}')
  localStorage.setItem('stage-recovery:account:other:equipment_observation', '{}')
  const first = render(deletion())
  fireEvent.click(screen.getByRole('button', { name: 'Удалить анализ' }))
  fireEvent.click(screen.getByRole('button', { name: 'Удалить безвозвратно' }))
  await screen.findByRole('alert')
  first.unmount()
  const done = vi.fn(); render(deletion('runs', done))
  expect(fetcher).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Проверить статус удаления' }))
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1))
  expect(fetcher.mock.calls[1][0]).toBe(fetcher.mock.calls[0][0])
  expect(localStorage.getItem('stage-recovery:account:target:equipment_observation')).toBeNull()
  expect(localStorage.getItem('stage-recovery:account:other:equipment_observation')).toBe('{}')
})
it('automatically reads a known operation after reload, but never deletes a new navigation target', async () => {
  localStorage.setItem('pending-deletion:account:runs:target', JSON.stringify({ deletion_id: '11111111-1111-4111-8111-111111111111', status: 'cleaning' }))
  const fetcher = vi.fn(async (_url: string) => json({ deletion_id: '11111111-1111-4111-8111-111111111111', status: 'completed' }))
  vi.stubGlobal('fetch', fetcher)
  const done = vi.fn(), view = render(deletion('runs', done))
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1), { timeout: 2500 })
  expect(fetcher.mock.calls[0][0]).toBe('/api/deletions/11111111-1111-4111-8111-111111111111')
  view.rerender(deletion('runs', done, true, 'other'))
  expect(screen.getByText('Содержимое объекта')).toBeTruthy()
  expect(fetcher).toHaveBeenCalledTimes(1)
})
it('does not offer destructive actions to viewers', () => {
  render(deletion('runs', vi.fn(), false))
  expect(screen.queryByRole('button', { name: 'Удалить анализ' })).toBeNull()
})

it('cancels confirmation without sending DELETE', () => {
 const fetcher=vi.fn(); vi.stubGlobal('fetch',fetcher)
 render(deletion())
 fireEvent.click(screen.getByRole('button',{name:'Удалить анализ'}))
 fireEvent.click(screen.getByRole('button',{name:'Отмена'}))
 expect(screen.queryByRole('dialog')).toBeNull()
 expect(fetcher).not.toHaveBeenCalled()
 expect(screen.getByText('Содержимое объекта')).toBeTruthy()
})
it('shows the exact safe message after server 503', async () => {
 vi.stubGlobal('fetch',vi.fn(async()=>json({detail:'private-provider-error'},503)))
 render(stage())
 fireEvent.click(screen.getByRole('button',{name:'Перезапустить этап'}))
 expect((await screen.findByRole('alert')).textContent).toBe('Обратитесь к администратору')
})

it('does not apply a late deletion response to another run', async () => {
 let finish!: (value:object)=>void
 const fetcher=vi.fn(()=>new Promise(resolve=>{finish=resolve}));vi.stubGlobal('fetch',fetcher)
 const done=vi.fn(), view=render(deletion('runs',done))
 fireEvent.click(screen.getByRole('button',{name:'Удалить анализ'}))
 fireEvent.click(screen.getByRole('button',{name:'Удалить безвозвратно'}))
 view.rerender(deletion('runs',done,true,'other'))
 await act(async()=>finish(json({deletion_id:'11111111-1111-4111-8111-111111111111',status:'completed'},202)))
 expect(done).not.toHaveBeenCalled()
 expect(screen.getByText('Содержимое объекта')).toBeTruthy()
 expect(localStorage.getItem('pending-deletion:account:runs:target')).toBe('{}')
 expect(localStorage.getItem('pending-deletion:account:runs:other')).toBeNull()
})
it('keeps pending deletion identities isolated between accounts', () => {
 localStorage.setItem('pending-deletion:someone-else:runs:target','{}')
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher)
 render(deletion())
 expect(screen.getByText('Содержимое объекта')).toBeTruthy()
 expect(fetcher).not.toHaveBeenCalled()
})
it('clears stage recovery only for analyses belonging to the deleted project', async () => {
 localStorage.setItem('stage-recovery:account:run:equipment_observation',JSON.stringify({key:'44444444-4444-4444-8444-444444444444',parent:'22222222-2222-4222-8222-222222222222',projectId:'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa'}))
 localStorage.setItem('stage-recovery:account:other:equipment_observation',JSON.stringify({key:'55555555-5555-4555-8555-555555555555',parent:'22222222-2222-4222-8222-222222222222',projectId:'bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb'}))
 vi.stubGlobal('fetch',vi.fn(async()=>json({deletion_id:'11111111-1111-4111-8111-111111111111',status:'completed'},202)))
 const done=vi.fn();render(deletion('projects',done,true,'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa'))
 fireEvent.click(screen.getByRole('button',{name:'Удалить проект'}))
 fireEvent.click(screen.getByRole('button',{name:'Удалить безвозвратно'}))
 await waitFor(()=>expect(done).toHaveBeenCalledTimes(1))
 expect(localStorage.getItem('stage-recovery:account:run:equipment_observation')).toBeNull()
 expect(localStorage.getItem('stage-recovery:account:other:equipment_observation')).toBeTruthy()
})

it.each([
 '{}', 'null', '[]', '"text"', '{broken',
 JSON.stringify({key:'bad',parent:'22222222-2222-4222-8222-222222222222'}),
 JSON.stringify({key:'44444444-4444-4444-8444-444444444444',parent:'bad'}),
 JSON.stringify({key:'44444444-4444-4444-8444-444444444444',parent:'22222222-2222-4222-8222-222222222222',attempt:'bad'}),
 JSON.stringify({key:'44444444-4444-4444-8444-444444444444',parent:'22222222-2222-4222-8222-222222222222',projectId:'../other'}),
])('discards malformed stage identity %s before a manual UUID request', async raw => {
 const storage='stage-recovery:account:run:equipment_observation'
 localStorage.setItem(storage,raw)
 const fetcher=vi.fn().mockRejectedValue(new Error('network'));vi.stubGlobal('fetch',fetcher)
 render(stage())
 expect(localStorage.getItem(storage)).toBeNull()
 expect(fetcher).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'Перезапустить этап'}))
 await screen.findByRole('alert')
 expect(fetcher.mock.calls[0][1].headers['Idempotency-Key']).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)
})
it.each([
 'null', '[]', '"text"', '{broken',
 JSON.stringify({deletion_id:'../../projects/other',status:'cleaning'}),
 JSON.stringify({deletion_id:'11111111-1111-4111-8111-111111111111',status:'unknown'}),
 JSON.stringify({deletion_id:'11111111-1111-4111-8111-111111111111'}),
 JSON.stringify({status:'cleaning'}),
])('discards malformed deletion identity %s without issuing requests', raw => {
 const storage='pending-deletion:account:runs:target'
 localStorage.setItem(storage,raw)
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher)
 render(deletion())
 expect(screen.getByText('Содержимое объекта')).toBeTruthy()
 expect(localStorage.getItem(storage)).toBeNull()
 expect(fetcher).not.toHaveBeenCalled()
})
it.each(['cleaning','completed'])('rejects invalid API deletion UUID in %s state without GET or persistence', async status => {
 const fetcher=vi.fn(async()=>json({deletion_id:'../../projects/other',status},202));vi.stubGlobal('fetch',fetcher)
 render(deletion())
 fireEvent.click(screen.getByRole('button',{name:'Удалить анализ'}))
 fireEvent.click(screen.getByRole('button',{name:'Удалить безвозвратно'}))
 expect((await screen.findByRole('alert')).textContent).toBe('Обратитесь к администратору')
 expect(fetcher).toHaveBeenCalledTimes(1)
 expect(localStorage.getItem('pending-deletion:account:runs:target')).toBe('{}')
})
it('preserves the same valid stage identity after a definitive 4xx rejection', async () => {
 const storage='stage-recovery:account:run:equipment_observation'
 const identity={key:'44444444-4444-4444-8444-444444444444',parent:'22222222-2222-4222-8222-222222222222'}
 const exact=JSON.stringify(identity);localStorage.setItem(storage,exact)
 const fetcher=vi.fn(async()=>json({detail:'profile_unauthorized'},409));vi.stubGlobal('fetch',fetcher)
 render(stage())
 expect(fetcher).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'Перезапустить этап'}))
 await screen.findByRole('alert')
 expect(localStorage.getItem(storage)).toBe(exact)
})
