import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AccountShell from './AccountShell'
import App from './App'
import { createAccountDemo } from '../demo/accounts'
const dialogDescriptors = new Map(['show','showModal','close'].map(name => [name, Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype,name)]))
vi.mock('./engagement', () => ({ startActivity: () => () => {}, track: async () => {}, attributionHeaders: () => ({}) }))
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear(); sessionStorage.clear(); for (const [name,descriptor] of dialogDescriptors) { if(descriptor)Object.defineProperty(HTMLDialogElement.prototype,name,descriptor); else Reflect.deleteProperty(HTMLDialogElement.prototype,name) } })
it('guides real project creation from examples through an illustrative signal without inference', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockImplementation(() => { throw new Error('Completed tutorial import must not prompt to discard unsaved work') })
  localStorage.clear(); sessionStorage.clear(); localStorage.setItem('analysis-motion','off')
  history.replaceState({}, '', '/examples')
  vi.stubGlobal('matchMedia', () => ({ matches:false, addEventListener:vi.fn(), removeEventListener:vi.fn() }))
  for (const method of ['show','showModal','close']) Object.defineProperty(HTMLDialogElement.prototype, method, {configurable:true,value:function(this: HTMLDialogElement){ if(method==='close')this.removeAttribute('open');else this.setAttribute('open','') }})
  const demo=createAccountDemo()
  const registration=await demo.request('POST','/account/register',{email:'learning-flow@example.test',name:'Learner',password:'demo-pass'})
  const session=registration.session
  const fetcher=vi.fn(async (raw:string, options?:RequestInit) => {
    const headers=new Headers(options?.headers)
    const body=options?.body instanceof File ? { xlsx: new Uint8Array(await new Promise<ArrayBuffer>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result as ArrayBuffer); reader.onerror = reject; reader.readAsArrayBuffer(options.body as File) })) } : options?.body ? JSON.parse(String(options.body)) : {}
    const response=await demo.request(options?.method ?? 'GET',raw,body,headers.get('Idempotency-Key')??'',session)
    return { ok:response.status<400, status:response.status, json:async()=>response.data, blob:async()=>new Blob([response.artifact??''],{type:response.contentType??'image/jpeg'}) }
  })
  vi.stubGlobal('fetch',fetcher)
  render(<AccountShell><App /></AccountShell>)
  fireEvent.click(await screen.findByRole('button',{name:'Как пользоваться'}))
  await waitFor(()=>expect(location.pathname).toBe('/'))
  const create = await screen.findByRole('link',{name:'Создать проект'})
  await waitFor(()=>expect(create.getAttribute('data-tutorial-highlighted')).toBe('true'))
  expect(screen.getByRole('button',{name:'Пауза'}).closest('details')?.open).toBe(false)
  fireEvent.click(create)
  const name=await screen.findByLabelText('Название проекта') as HTMLInputElement
  await waitFor(()=>expect(name.value).toBe('Мой учебный проект'))
  await clickHighlighted('Создать проект')
  await clickHighlighted('Добавить учебный набор')
  await waitFor(()=>expect(location.pathname).toMatch(/\/plan$/))
  const next = await screen.findByRole('button',{name:'План импортирован, к фотографиям'}) as HTMLButtonElement
  expect(next.disabled).toBe(true)
  const download = await screen.findByRole('link',{name:'Скачать учебный Excel'})
  await waitFor(()=>expect(download.getAttribute('data-tutorial-highlighted')).toBe('true'))
  const downloaded = await fetcher(download.getAttribute('href')!)
  const file = new File([await downloaded.blob()], 'tutorial-plan.xlsx', {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
  fireEvent.change(screen.getByLabelText('План Excel'),{target:{files:[file]}})
  await screen.findByRole('heading',{name:'Предпросмотр замены плана'})
  expect(next.disabled).toBe(true)
  await clickHighlighted('Заменить план')
  await waitFor(()=>expect(next.disabled).toBe(false))
  const planWrite = fetcher.mock.calls.find(([url,options])=>url.includes('/plan') && options?.method==='PUT')
  expect(planWrite).toBeTruthy()
  expect(JSON.parse(String(planWrite![1]!.body)).expected_revision).toBe(1)
  const readback = fetcher.mock.calls.find(([url])=>url.includes('/plan?revision=2'))
  expect(readback).toBeTruthy()
  await clickHighlighted('План импортирован, к фотографиям')
  await screen.findByRole('heading',{name:'Подготовка фотографий'})
  await clickHighlighted('Выбрать учебные фотографии')
  await clickHighlighted('Посмотреть готовый пример')
  await screen.findByRole('heading',{name:'Учебный результат'})
  await clickHighlighted('Исправить рамку')
  const editorImage=screen.getByAltText('Кадр для исправления объектов')
  Object.defineProperties(editorImage,{naturalWidth:{value:1215,configurable:true},naturalHeight:{value:811,configurable:true}});fireEvent.load(editorImage)
  screen.getByText('Точные координаты').closest('details')!.open=true
  for(const [label,value] of [['Справа','.675'],['Снизу','.665'],['Слева','.255'],['Сверху','.17']]) {const field=screen.getByLabelText(label);fireEvent.change(field,{target:{value}});fireEvent.blur(field)}
  await clickHighlighted('Сохранить учебную правку')
  await clickHighlighted('Открыть учебное предупреждение')
  await screen.findByRole('heading',{name:'Учебный сигнал'})
  await clickHighlighted(/Требует проверки.*учебное предупреждение/)
  await clickHighlighted('Начать проверку')
  await screen.findByText(/Готово! Вы создали проект/)
  async function clickHighlighted(name: string | RegExp) { const button=await screen.findByRole('button',{name}); await waitFor(()=>expect(button.getAttribute('data-tutorial-highlighted')).toBe('true')); fireEvent.click(button) }
  expect(confirm).not.toHaveBeenCalled()
  const writes=fetcher.mock.calls.filter(([,options])=>options?.method==='POST')
  expect(writes.some(([url])=>url.includes('/runs/'))).toBe(false)
  expect(writes.some(([url])=>url.includes('/assistant/'))).toBe(false)
  const projects=(await demo.request('GET','/projects',{},'',session)).data.projects
  expect(projects).toHaveLength(1)
  expect((await demo.request('GET',`/runs?project_id=${projects[0].id}`,{},'',session)).data.total).toBe(0)
  expect((await demo.request('GET',`/signals?project_id=${projects[0].id}`,{},'',session)).data.signals).toHaveLength(0)
})
