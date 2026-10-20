import PublicSupport from './PublicSupport'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import AssistantChat, { ChatText } from './AssistantChat'
import { TutorialProvider, useTutorial } from './Tutorial'

const descriptors = new Map(['show','showModal','close'].map(name => [name, Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype,name)]))
beforeEach(() => {
  localStorage.clear()
  for (const method of ['show','showModal','close']) Object.defineProperty(HTMLDialogElement.prototype,method,{configurable:true,value:function(this:HTMLDialogElement){if(method==='close')this.removeAttribute('open');else this.setAttribute('open','')}})
})
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.useRealTimers()
  for (const [name,descriptor] of descriptors) { if(descriptor)Object.defineProperty(HTMLDialogElement.prototype,name,descriptor);else Reflect.deleteProperty(HTMLDialogElement.prototype,name) }
})
function open() { fireEvent.click(screen.getByRole('button',{name:'Помощник'})) }
function send(text:string) { fireEvent.change(screen.getByLabelText('Сообщение помощнику'),{target:{value:text}});fireEvent.click(screen.getByRole('button',{name:'Отправить сообщение'})) }

it('immediately shows the user bubble and pending bubble, then keeps both sides of a general conversation',async()=>{
  let finish!:(value:unknown)=>void
  const request=vi.fn(()=>new Promise<any>(resolve=>{finish=resolve}))
  render(<AssistantChat request={request}/>);open();send('Где сигналы?')
  expect(within(screen.getByLabelText('Ваше сообщение')).getByText('Где сигналы?')).toBeTruthy()
  expect(screen.getByRole('status',{name:'Помощник готовит ответ'})).toBeTruthy()
  expect((screen.getByLabelText('Сообщение помощнику') as HTMLTextAreaElement).value).toBe('')
  await act(async()=>finish({messages:[{id:'answer1',role:'assistant',content:'Откройте **Сигналы** проекта.'}]}))
  expect(screen.queryByRole('status',{name:'Помощник готовит ответ'})).toBeNull()
  expect(within(screen.getByLabelText('Ответ помощника')).getByText('Сигналы',{selector:'strong'})).toBeTruthy()
  expect(screen.getAllByLabelText('Ваше сообщение')).toHaveLength(1)
  send('Как их проверить?')
  await act(async()=>finish({messages:[{id:'answer2',role:'assistant',content:'Сверьте основание с фотографиями.'}]}))
  expect(screen.getAllByLabelText('Ваше сообщение')).toHaveLength(2)
  expect(screen.getAllByLabelText('Ответ помощника')).toHaveLength(2)
})
it('switches fullscreen without losing the draft or messages and restores focus on close',()=>{
  render(<AssistantChat request={vi.fn()}/>);open()
  fireEvent.change(screen.getByLabelText('Сообщение помощнику'),{target:{value:'Мой черновик'}})
  fireEvent.click(screen.getByRole('button',{name:'Развернуть чат'}))
  expect(screen.getByRole('dialog',{name:'Чат с помощником'}).getAttribute('aria-modal')).toBe('true')
  expect(document.body.style.overflow).toBe('hidden')
  expect((screen.getByLabelText('Сообщение помощнику') as HTMLTextAreaElement).value).toBe('Мой черновик')
  fireEvent.click(screen.getByRole('button',{name:'Свернуть чат'}))
  expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBeNull()
  expect(document.body.style.overflow).not.toBe('hidden')
  fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'})
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button',{name:'Помощник'}))
  open();expect((screen.getByLabelText('Сообщение помощнику') as HTMLTextAreaElement).value).toBe('Мой черновик')
})
it('retains a failed question and retries without adding a duplicate question bubble',async()=>{
  const request=vi.fn().mockRejectedValueOnce(new Error('Нет соединения')).mockResolvedValue({messages:[{id:'answer',role:'assistant',content:'Ответ получен.'}]})
  render(<AssistantChat request={request}/>);open();send('Вопрос')
  expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('Нет соединения'))
  expect(screen.queryByRole('status',{name:'Помощник готовит ответ'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'Повторить отправку'}))
  await screen.findByText('Ответ получен.')
  expect(screen.getAllByLabelText('Ваше сообщение')).toHaveLength(1)
  expect(request.mock.calls[0][2]).toEqual(request.mock.calls[1][2])
})
it('loads saved project history once and does not repeat the user bubble in the authoritative result',async()=>{
  const past={id:'past',role:'assistant',content:'Прошлый ответ'}
  const request=vi.fn().mockResolvedValueOnce({messages:[past]}).mockResolvedValueOnce({messages:[past,{id:'saved-question',role:'user',content:'Новый вопрос'},{id:'new-answer',role:'assistant',content:'Новый ответ'}]})
  render(<AssistantChat projectId="project" request={request}/>);open()
  await screen.findByText('Прошлый ответ');send('Новый вопрос')
  await screen.findByText('Новый ответ')
  expect(screen.getAllByLabelText('Ваше сообщение')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'Закрыть чат'}));open()
  expect(request).toHaveBeenCalledTimes(2)
  expect(screen.getByText('Новый ответ')).toBeTruthy()
})
it('Enter sends, but Shift+Enter and composition do not send',async()=>{
  const request=vi.fn().mockResolvedValue({messages:[{id:'a',role:'assistant',content:'Ответ'}]})
  render(<AssistantChat request={request}/>);open()
  const field=screen.getByLabelText('Сообщение помощнику')
  fireEvent.change(field,{target:{value:'Вопрос'}})
  fireEvent.keyDown(field,{key:'Enter',shiftKey:true})
  fireEvent.keyDown(field,{key:'Enter',isComposing:true})
  expect(request).not.toHaveBeenCalled()
  fireEvent.keyDown(field,{key:'Enter'})
  await screen.findByText('Ответ');expect(request).toHaveBeenCalledTimes(1)
})
it('formats emphasis and lists while keeping model HTML inert',()=>{
  const {container}=render(<ChatText text={'**Заголовок**\n\n1. Первый\n2. Второй\n\n<script>alert(1)</script>'}/>)
  expect(screen.getByText('Заголовок',{selector:'strong'})).toBeTruthy()
  expect(screen.getAllByRole('listitem')).toHaveLength(2)
  expect(container.querySelector('script')).toBeNull()
  expect(screen.getByText('<script>alert(1)</script>')).toBeTruthy()
})

it('does not show a late answer after changing the project scope',async()=>{
  let finish!:(value:unknown)=>void
  const request=vi.fn((path:string,method?:string)=>method==='POST'?new Promise<any>(resolve=>{finish=resolve}):Promise.resolve({messages:[]}))
  const view=render(<AssistantChat key="first" projectId="first" request={request}/>)
  open();await act(async()=>{});send('Вопрос первого проекта')
  view.rerender(<AssistantChat key="second" projectId="second" request={request}/>)
  open();await act(async()=>{})
  await act(async()=>finish({messages:[{id:'private-answer',role:'assistant',content:'Закрытые сведения первого проекта'}]}))
  expect(screen.queryByText('Закрытые сведения первого проекта')).toBeNull()
  expect(screen.queryByText('Вопрос первого проекта')).toBeNull()
})

function ChangeTutorialStep() { const tutorial = useTutorial(); return <button onClick={() => tutorial?.update({step:'photos'})}>Следующий учебный шаг</button> }
it('sends the current tutorial context on each ordinary question and keeps project identity', async () => {
 localStorage.setItem('tutorial:1:a',JSON.stringify({version:1,step:'plan',projectId:'p',key:'k',started:true,paused:false,selected:[],signal:false,questionSubmitted:true}))
 const request=vi.fn().mockResolvedValue({messages:[]})
 render(<TutorialProvider account="a" navigate={()=>true}><ChangeTutorialStep/><AssistantChat accountId="a" projectId="p" request={request}/></TutorialProvider>)
 await act(async()=>{});expect(screen.queryByText('Чем помочь?')).toBeNull();expect(screen.getByRole('dialog').classList.contains('has-tutorial')).toBe(true);send('Что означает план?');await waitForPost();expect(request.mock.calls.find(call=>call[1]==='POST')?.[2]).toEqual({message:'Что означает план?',project_id:'p',tutorial_context:{version:1,step:'plan'}})
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).paused).toBe(false);expect(screen.queryByRole('button',{name:'Вернуться к обучению'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'К текущему шагу'}));expect(screen.queryByRole('button',{name:'К текущему шагу'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Следующий учебный шаг'}));send('А эти кадры?');await waitForPost();expect(request.mock.calls.filter(call=>call[1]==='POST').at(-1)?.[2]).toEqual({message:'А эти кадры?',project_id:'p',tutorial_context:{version:1,step:'photos'}})
 async function waitForPost(){await act(async()=>{})}
})
it('restores unsent drafts only for the matching account and project after remount', () => {
 const request=vi.fn().mockResolvedValue({messages:[]})
 const view=render(<AssistantChat key="a:p" accountId="a" projectId="p" request={request}/>);open();fireEvent.change(screen.getByLabelText('Сообщение помощнику'),{target:{value:'Черновик проекта'}})
 view.rerender(<AssistantChat key="b:p" accountId="b" projectId="p" request={request}/>);open();expect((screen.getByLabelText('Сообщение помощнику') as HTMLTextAreaElement).value).toBe('')
 view.rerender(<AssistantChat key="a:q" accountId="a" projectId="q" request={request}/>);open();expect((screen.getByLabelText('Сообщение помощнику') as HTMLTextAreaElement).value).toBe('')
 view.rerender(<AssistantChat key="a:p2" accountId="a" projectId="p" request={request}/>);open();expect((screen.getByLabelText('Сообщение помощнику') as HTMLTextAreaElement).value).toBe('Черновик проекта')
})
it('hides without pausing learning, retains its draft and stays hidden across project transitions', async () => {
 localStorage.setItem('tutorial:1:a',JSON.stringify({version:1,step:'plan',projectId:'p',key:'hide-guide',started:true,paused:false,selected:[],signal:false,questionSubmitted:true}))
 const request=vi.fn().mockResolvedValue({messages:[]})
 const content=(key:string)=><TutorialProvider account="a" navigate={()=>true}><button data-tutorial="plan-import">Действие плана</button><button data-tutorial="select-photos">Действие фотографий</button><ChangeTutorialStep/><AssistantChat key={key} accountId="a" projectId="p" request={request}/></TutorialProvider>
 const view=render(content('first'))
 await act(async()=>{})
 fireEvent.change(screen.getByLabelText('Сообщение помощнику'),{target:{value:'Черновик вопроса'}})
 fireEvent.click(screen.getByRole('button',{name:'Развернуть чат'}))
 fireEvent.click(screen.getByRole('button',{name:'Скрыть чат'}))
 expect(screen.queryByRole('dialog',{name:'Чат с помощником'})).toBeNull()
 expect(document.body.style.overflow).not.toBe('hidden')
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!)).toMatchObject({step:'plan',started:true,paused:false,chatHidden:true})
 expect(screen.getByRole('button',{name:'Действие плана'}).getAttribute('data-tutorial-highlighted')).toBe('true')
 fireEvent.click(screen.getByRole('button',{name:'Следующий учебный шаг'}))
 expect(screen.getByRole('button',{name:'Действие фотографий'}).getAttribute('data-tutorial-highlighted')).toBe('true')
 view.rerender(content('next-project-scope'))
 expect(screen.queryByRole('dialog',{name:'Чат с помощником'})).toBeNull()
 open()
 expect(screen.getByRole('dialog',{name:'Чат с помощником'})).toBeTruthy()
 expect((screen.getByLabelText('Сообщение помощнику') as HTMLTextAreaElement).value).toBe('Черновик вопроса')
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!)).toMatchObject({step:'photos',started:true,paused:false,chatHidden:false})
 fireEvent.click(screen.getByRole('button',{name:'Закрыть чат'}))
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).paused).toBe(true)
})

it('keeps the current lesson active while answering a question and after its answer', async () => {
 localStorage.setItem('tutorial:1:a',JSON.stringify({version:1,step:'plan',projectId:'p',key:'question-live',started:true,paused:false,selected:[],signal:false,questionSubmitted:true}))
 let finish!: (reply:{messages:{id:string;role:string;content:string}[]})=>void
 const request=vi.fn((_:string,method?:string)=>method==='POST'?new Promise<any>(resolve=>{finish=resolve}):Promise.resolve({messages:[]}))
 render(<TutorialProvider account="a" navigate={()=>true}><button data-tutorial="plan-import">Продолжить шаг на странице</button><AssistantChat projectId="p" accountId="a" request={request}/></TutorialProvider>)
 await act(async()=>{})
 send('Что добавить в план?')
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!)).toMatchObject({step:'plan',started:true,paused:false})
 expect(screen.getByRole('button',{name:'Продолжить шаг на странице'}).getAttribute('data-tutorial-highlighted')).toBe('true')
 expect(screen.getByRole('status',{name:'Помощник готовит ответ'})).toBeTruthy()
 await act(async()=>finish({messages:[{id:'plan-answer',role:'assistant',content:'Добавьте работы, сроки и ожидаемую технику.'}]}))
 expect(screen.getByText('Добавьте работы, сроки и ожидаемую технику.')).toBeTruthy()
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!)).toMatchObject({step:'plan',started:true,paused:false})
 expect(screen.queryByRole('button',{name:'Продолжить обучение'})).toBeNull()
 expect(screen.queryByRole('button',{name:'Вернуться к обучению'})).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'К текущему шагу'}))
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).paused).toBe(false)
})

it('starts interactive training directly from public help instead of opening an empty chat', async () => {
 const navigate = vi.fn(() => true)
 const request = vi.fn(async () => ({messages: []}))
 render(<TutorialProvider account="a" navigate={navigate}><PublicSupport safe start={() => {}} /><AssistantChat accountId="a" request={request} /></TutorialProvider>)
 expect(screen.queryByRole('dialog')).toBeNull()
 fireEvent.click(screen.getByRole('button', {name: 'Как пользоваться'}))
 expect(navigate).toHaveBeenCalledWith('/')
 expect(screen.getByRole('dialog').classList.contains('has-tutorial')).toBe(true)
 expect(screen.queryByText('Чем помочь?')).toBeNull()
 expect(screen.queryByRole('button', {name: 'Как пользоваться приложением?'})).toBeNull()
 expect(JSON.parse(localStorage.getItem('tutorial:1:a')!)).toMatchObject({started:true,paused:false,step:'create_project'})
 expect(request).not.toHaveBeenCalled()
})
