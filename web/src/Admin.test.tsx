import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Admin from './Admin'
const json = (value: unknown, status=200) => ({ok:status<400,status,json:async()=>value})
const row = (id: string, message=id) => ({id,message,category:'idea',created_at:'2026-09-26T00:00:00Z',read_at:null})
const overview = {cards:{},daily:[],projects:[],funnel:{},wizard:{},collection_started_at:'2026-09-26T00:00:00Z'}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('distinguishes session outage from authoritative logout and retries',async()=>{
 const fetcher=vi.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(json({},401))
 vi.stubGlobal('fetch',fetcher);render(<Admin />)
 await screen.findByText(/Не удалось проверить сессию/)
 expect(screen.queryByText('Вход владельца')).toBeNull()
 fireEvent.click(screen.getByText('Повторить проверку сессии'))
 await screen.findByText('Вход владельца')
})
it('fences delayed detail and pagination when changing category or tab, and safely renders old malformed context',async()=>{
 let finishDetail!: (value: unknown)=>void, finishPage!: (value:unknown)=>void
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url.endsWith('/session'))return json({csrf:'csrf'})
  if(url.includes('/overview'))return json(overview)
  if(url.includes('/open'))return await new Promise(resolve=>{finishDetail=resolve})
  if(url.includes('offset='))return await new Promise(resolve=>{finishPage=resolve})
  if(url.includes('category=problem'))return json({feedback:[row('new')],next_offset:null})
  return json({feedback:[row('old')],next_offset:50})
 }))
 render(<Admin />);await screen.findByText('По дням')
 fireEvent.click(screen.getByRole('button',{name:'Обратная связь'}));await screen.findByText('old')
 fireEvent.click(screen.getByRole('button',{name:/old/}))
 fireEvent.change(screen.getByLabelText('Категория'),{target:{value:'problem'}})
 await screen.findByText('new');finishDetail(json({...row('old'),message:'stale detail',context:{project_id:{}}}))
 await waitFor(()=>expect(screen.queryByText('stale detail')).toBeNull())
 fireEvent.change(screen.getByLabelText('Категория'),{target:{value:''}});await screen.findByText('old')
 fireEvent.click(screen.getByText('Показать ещё'));fireEvent.click(screen.getByRole('button',{name:'Обзор'}))
 await screen.findByText('По дням');finishPage(json({feedback:[row('stale page')],next_offset:null}))
 fireEvent.click(screen.getByRole('button',{name:'Обратная связь'}));await screen.findByText('old')
 expect(screen.queryByText('stale page')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:/old/}));finishDetail(json({...row('old'),context:{project_id:{},analysis_id:[]},attachments:[]}))
 expect(await screen.findAllByText('Некорректный сохранённый контекст')).toHaveLength(2)
})
