import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import PublicSupport from './PublicSupport'
vi.mock('./engagement',()=>({startActivity:()=>()=>{},track:async()=>{}}))
let stored: unknown, hold: Promise<void>|undefined
beforeEach(()=>{
 stored=undefined;hold=undefined;localStorage.setItem('construction-onboarding','completed')
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
 vi.stubGlobal('indexedDB',{open:()=>{
  const request: any={};queueMicrotask(()=>{request.result={close(){},transaction(){
   const transaction:any={objectStore:()=>({get(){const result:any={};setTimeout(()=>{result.result=structuredClone(stored);transaction.oncomplete?.()},0);return result},put(value:unknown){const wait=hold;setTimeout(()=>{void Promise.resolve(wait).then(()=>{stored=structuredClone(value);transaction.oncomplete?.()})},0);return {}}})};return transaction
  }};request.onsuccess?.()});return request
 }})
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
async function open(){fireEvent.click(screen.getByRole('button',{name:'Обратная связь'}));await waitFor(()=>expect(screen.getByLabelText('Сообщение').closest('fieldset')?.disabled).toBe(false))}
async function fill(){fireEvent.change(screen.getByLabelText('Категория'),{target:{value:'idea'}});fireEvent.change(screen.getByLabelText('Сообщение'),{target:{value:'Original'}});await waitFor(()=>expect((stored as any)?.message).toBe('Original'))}
it('restores after all prior-instance writes and ignores attachment readers from closed instances',async()=>{
 render(<PublicSupport safe start={()=>{}}/>);await open();await fill()
 let release!:()=>void;hold=new Promise(resolve=>{release=resolve})
 fireEvent.change(screen.getByLabelText('Сообщение'),{target:{value:'Latest'}})
 fireEvent.click(screen.getByText('Закрыть'));fireEvent.click(screen.getByRole('button',{name:'Обратная связь'}))
 expect(screen.getByLabelText('Сообщение').closest('fieldset')?.disabled).toBe(true)
 release();hold=undefined;await waitFor(()=>expect(screen.getByLabelText('Сообщение')).toHaveProperty('value','Latest'))
 let reader:any
 vi.stubGlobal('FileReader',class{result='data:image/png;base64,AA==';onload?:()=>void;readAsDataURL(){reader=this}})
 fireEvent.change(screen.getByLabelText('Изображения'),{target:{files:[new File(['x'],'old.png',{type:'image/png'})]}})
 fireEvent.click(screen.getByText('Закрыть'));await open()
 fireEvent.change(screen.getByLabelText('Сообщение'),{target:{value:'Newer'}})
 await act(async()=>{reader.onload()})
 await waitFor(()=>expect((stored as any)?.message).toBe('Newer'))
 expect((stored as any).pictures).toHaveLength(0)
})
it('settles rejected sends before reopening, unlocks correction, and clears success durably',async()=>{
 let finish!:(value:unknown)=>void
 vi.stubGlobal('fetch',vi.fn(()=>new Promise(resolve=>{finish=resolve})))
 render(<PublicSupport safe start={()=>{}}/>);await open();await fill()
 fireEvent.click(screen.getByText('Отправить отзыв'));await waitFor(()=>expect(finish).toBeTypeOf('function'))
 fireEvent.click(screen.getByText('Закрыть'));fireEvent.click(screen.getByRole('button',{name:'Обратная связь'}))
 expect(screen.getByLabelText('Сообщение').closest('fieldset')?.disabled).toBe(true)
 finish({ok:false,status:400});await waitFor(()=>expect(screen.getByLabelText('Сообщение').closest('fieldset')?.disabled).toBe(false))
 expect((stored as any).frozen).toBeUndefined()
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200})))
 fireEvent.click(screen.getByText('Отправить отзыв'));await screen.findByText('Спасибо, отзыв сохранён')
 fireEvent.click(screen.getByText('Закрыть'));await open()
 expect(screen.getByLabelText('Сообщение')).toHaveProperty('value','')
})
it('retains the exact frozen request on unknown response and reuses it after reopening',async()=>{
 const fetcher=vi.fn().mockRejectedValueOnce(new TypeError('lost response')).mockResolvedValueOnce({ok:true,status:200})
 vi.stubGlobal('fetch',fetcher);render(<PublicSupport safe start={()=>{}}/>);await open();await fill()
 fireEvent.click(screen.getByText('Отправить отзыв'));await screen.findByRole('alert')
 fireEvent.click(screen.getByText('Закрыть'));fireEvent.click(screen.getByRole('button',{name:'Обратная связь'}))
 await waitFor(()=>expect(screen.getByText('Повторить отправку')).toHaveProperty('disabled',false))
 fireEvent.click(screen.getByText('Повторить отправку'));await screen.findByText('Спасибо, отзыв сохранён')
 expect(fetcher.mock.calls[1][1].body).toBe(fetcher.mock.calls[0][1].body)
 expect(fetcher.mock.calls[1][1].headers).toEqual(fetcher.mock.calls[0][1].headers)
})
