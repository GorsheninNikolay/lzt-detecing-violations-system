import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

it('opens the floating assistant on request without automatically launching help', () => {
  const open = vi.fn()
  addEventListener('open-assistant', open)
  const view = render(<PublicSupport safe={false} start={() => {}} />)
  expect(open).not.toHaveBeenCalled()
  view.rerender(<PublicSupport safe start={() => {}} />)
  expect(open).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  expect(open).toHaveBeenCalledOnce()
  expect(screen.queryByRole('dialog')).toBeNull()
  removeEventListener('open-assistant', open)
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
