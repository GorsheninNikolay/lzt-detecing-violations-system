import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PublicSupport from './PublicSupport'
import Admin from './Admin'

vi.mock('./engagement', () => ({ startActivity: () => () => {}, track: vi.fn(async () => {}) }))
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); history.replaceState({}, '', '/')
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('waits for recovery and dirty drafts, remembers skip, and supports manual reopening', async () => {
  const view = render(<PublicSupport safe={false} start={() => {}} />)
  expect(screen.queryByRole('dialog')).toBeNull()
  view.rerender(<PublicSupport safe start={() => {}} />)
  expect(await screen.findByRole('dialog')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Пропустить'}))
  expect(localStorage.getItem('construction-onboarding')).toBe('skipped')
  expect(screen.queryByRole('dialog')).toBeNull()
  view.unmount()
  render(<PublicSupport safe start={() => {}} />)
  expect(screen.queryByRole('dialog')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  expect(screen.getByRole('dialog')).toBeTruthy()
})

it('walks all five steps without creating data and restores trigger focus on Escape', async () => {
  localStorage.setItem('construction-onboarding','completed')
  const start = vi.fn(), user = userEvent.setup()
  render(<PublicSupport safe projectId="project" start={start} />)
  const trigger = screen.getByRole('button',{name:'Как пользоваться'})
  await user.click(trigger)
  for (let step=0;step<4;step++) await user.click(screen.getByRole('button',{name:'Далее'}))
  expect(start).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'Назад'}))
  expect(screen.getByText('Шаг 4 из 5')).toBeTruthy()
  fireEvent.keyDown(document,{key:'Escape'})
  expect(document.activeElement).toBe(trigger)
  await user.click(trigger)
  for (let step=0;step<4;step++) await user.click(screen.getByRole('button',{name:'Далее'}))
  await user.click(screen.getByRole('button',{name:'Перейти к загрузке фото'}))
  expect(start).toHaveBeenCalledOnce()
  expect(localStorage.getItem('construction-onboarding')).toBe('completed')
})

it('keeps manual help available when local storage refuses access', async () => {
  vi.spyOn(Storage.prototype,'getItem').mockImplementation(() => { throw new Error('denied') })
  render(<PublicSupport safe start={() => {}} />)
  expect(screen.queryByRole('dialog')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  expect(await screen.findByRole('dialog')).toBeTruthy()
})

it('preserves the feedback form when draft storage is unavailable', async () => {
  localStorage.setItem('construction-onboarding','completed')
  vi.stubGlobal('indexedDB', undefined)
  render(<PublicSupport safe start={() => {}} />)
  fireEvent.click(screen.getByRole('button',{name:'Обратная связь'}))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('Хранилище браузера недоступно'))
  fireEvent.change(screen.getByLabelText('Сообщение'),{target:{value:'Сохранить мой текст'}})
  expect(screen.getByLabelText('Сообщение')).toHaveProperty('value','Сохранить мой текст')
  expect(screen.getByLabelText('Приложить контекст')).toHaveProperty('checked',true)
})

it('keeps admin data inaccessible before a server session', async () => {
  const fetcher = vi.fn(async (_url: string) => ({ok:false,status:401,json:async()=>({})}))
  vi.stubGlobal('fetch', fetcher)
  render(<Admin />)
  await waitFor(() => expect(screen.getByRole('heading',{name:'Вход владельца'})).toBeTruthy())
  expect(fetcher).toHaveBeenCalledOnce()
  expect(fetcher.mock.calls[0][0]).toBe('/api/admin/session')
  expect(screen.queryByText('Посетители')).toBeNull()
  expect(screen.queryByText('Как пользоваться')).toBeNull()
})

it('exposes explicit training preparation and does not start analysis on Next', async () => {
  localStorage.setItem('construction-onboarding','completed')
  const prepare = vi.fn(async () => {}), start = vi.fn()
  render(<PublicSupport safe start={start} training={{start:prepare,busy:false,ready:false,allowed:true,error:''}} />)
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  fireEvent.click(screen.getByRole('button',{name:'Попробовать на примере'}))
  await waitFor(() => expect(screen.getByText('Шаг 3 из 5')).toBeTruthy())
  expect(prepare).toHaveBeenCalledOnce()
  fireEvent.click(screen.getByRole('button',{name:'Далее'}))
  expect(start).not.toHaveBeenCalled()
})

it('protects an existing working draft from training preparation', () => {
  localStorage.setItem('construction-onboarding','completed')
  const prepare = vi.fn(async () => {})
  render(<PublicSupport safe={false} start={() => {}} training={{start:prepare,busy:false,ready:false,allowed:false,error:''}} />)
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  const action = screen.getByRole('button',{name:'Попробовать на примере'})
  expect(action).toHaveProperty('disabled',true)
  fireEvent.click(action)
  expect(prepare).not.toHaveBeenCalled()
  expect(screen.getByText(/текущий черновик/)).toBeTruthy()
})
