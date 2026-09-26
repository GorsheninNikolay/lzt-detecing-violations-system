import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AnnotationEditor, AnnotationQueue, shiftBox, resizeBox, validObjects } from './Annotations'

const initial = [{id:'00000000-0000-4000-8000-000000000001',class_name:'excavator',box:[.1,.2,.5,.6] as [number,number,number,number]}]
const review={id:'proposal',run_id:'run',input_id:'frame',input_sha256:'sha',artifact_id:'artifact',original_objects:initial,objects:initial,revision:1,status:'pending',version_id:'version',whole_frame_verified:false,reason:''}
function loadImage(){const image=screen.getByAltText('Кадр для исправления объектов');Object.defineProperties(image,{naturalWidth:{value:100,configurable:true},naturalHeight:{value:100,configurable:true}});fireEvent.load(image)}
const props = {runId:'run',inputId:'frame',checksum:'sha',artifactId:'artifact',initial}
beforeEach(()=>{Element.prototype.setPointerCapture=()=>{};localStorage.clear();vi.stubGlobal('matchMedia',()=>({matches:true}));vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({id:'proposal'})})))})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()})

it('keeps valid geometry inside the frame and rejects ambiguous identities',()=>{
 expect(shiftBox([.2,.3,.7,.8],1,-1)).toEqual([.5,0,1,.5])
 expect(shiftBox([.2,.3,.7,.8],-1,-1,true)).toEqual([.2,.3,.201,.301])
 expect(validObjects(initial)).toBe(true)
 expect(validObjects([...initial,...initial])).toBe(false)
 expect(validObjects([{...initial[0],box:[0,0,NaN,1]}])).toBe(false)
})

it('preserves edits, undo/redo and unknown request identity across reload',async()=>{
 const user=userEvent.setup()
 const fetchMock=vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValue({ok:true,json:async()=>({id:'proposal'})})
 vi.stubGlobal('fetch',fetchMock)
 const view=render(<AnnotationEditor {...props}/>)
 await user.selectOptions(screen.getByLabelText('Класс'),'dump_truck')
 await user.click(screen.getByRole('button',{name:'Отменить'}))
 expect((screen.getByLabelText('Класс') as HTMLSelectElement).value).toBe('excavator')
 await user.click(screen.getByRole('button',{name:'Повторить правку'}))
 await user.click(screen.getByRole('button',{name:'Отправить поправки на проверку'}))
 await screen.findByText(/Ответ неизвестен/)
 expect((screen.getByLabelText('Класс') as HTMLSelectElement).disabled).toBe(true)
 view.unmount()
 render(<AnnotationEditor {...props}/>)
 expect((screen.getByLabelText('Класс') as HTMLSelectElement).value).toBe('dump_truck')
 await user.click(screen.getByRole('button',{name:'Повторить сохранённый запрос'}))
 await screen.findByText(/Поправки отправлены/)
 expect(fetchMock.mock.calls[0][1].body).toBe(fetchMock.mock.calls[1][1].body)
 expect(fetchMock.mock.calls[0][1].headers['Idempotency-Key']).toBe(fetchMock.mock.calls[1][1].headers['Idempotency-Key'])
})

it('links image and list selection, handles keyboard geometry and isolates other frames',async()=>{
 const user=userEvent.setup()
 const view=render(<AnnotationEditor {...props}/>)
 const box=screen.getByRole('button',{name:'Объект 1: Экскаватор'})
 await user.click(box)
 expect(screen.getByRole('button',{name:'Объект 1'}).getAttribute('aria-pressed')).toBe('true')
 fireEvent.keyDown(box,{key:'ArrowRight'})
 expect(Number((screen.getByLabelText('Слева') as HTMLInputElement).value)).toBe(.11)
 fireEvent.keyDown(box,{key:'ArrowDown',shiftKey:true})
 expect(Number((screen.getByLabelText('Снизу') as HTMLInputElement).value)).toBe(.61)
 await user.click(screen.getByRole('button',{name:'Удалить объект 1'}))
 await user.click(screen.getByRole('button',{name:'Отменить'}))
 expect(screen.getByLabelText('Класс')).toBeTruthy()
 view.unmount()
 render(<AnnotationEditor {...props} inputId="other-frame"/>)
 expect(Number((screen.getByLabelText('Слева') as HTMLInputElement).value)).toBe(.1)
})

it('requires whole-frame verification again after each change and retains stale admin edits',async()=>{
 const user=userEvent.setup()
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:409,json:async()=>({detail:'stale_revision'})})))
 render(<AnnotationEditor {...props} review={review} csrf="csrf"/>)
 loadImage()
 const approve=screen.getByRole('button',{name:'Одобрить весь кадр'}) as HTMLButtonElement
 expect(approve.disabled).toBe(true)
 await user.click(screen.getByRole('checkbox'))
 expect(approve.disabled).toBe(false)
 await user.selectOptions(screen.getByLabelText('Класс'),'truck')
 expect(approve.disabled).toBe(true)
 await user.click(screen.getByRole('checkbox'))
 await user.click(approve)
 await waitFor(()=>expect(screen.getByText(/Версия на сервере изменилась/)).toBeTruthy())
 expect((screen.getByLabelText('Класс') as HTMLSelectElement).value).toBe('truck')
 expect(JSON.parse(localStorage.getItem('annotation:run:frame:sha:proposal')!).history.at(-1)[0].class_name).toBe('truck')
})

it('accepts typed numeric geometry on blur and explains invalid boundaries',async()=>{
 const user=userEvent.setup()
 render(<AnnotationEditor {...props}/>)
 const left=screen.getByLabelText('Слева') as HTMLInputElement
 await user.clear(left);await user.type(left,'0.25');await user.tab()
 expect(left.value).toBe('0.25')
 expect(JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!).history.at(-1)[0].box[0]).toBe(.25)
 await user.clear(left);await user.type(left,'0.9');await user.tab()
 expect(left.getAttribute('aria-invalid')).toBe('true')
 expect(screen.getByRole('alert').textContent).toContain('Введите границы')
 expect(JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!).history.at(-1)[0].box[0]).toBe(.25)
})

it('recovers owner exact pending request when the server revision advanced after an unknown response',async()=>{
 const user=userEvent.setup(),fetchMock=vi.fn().mockRejectedValueOnce(new TypeError('lost')).mockResolvedValue({ok:true,json:async()=>({id:'proposal',revision:2})})
 vi.stubGlobal('fetch',fetchMock)
 const view=render(<AnnotationEditor {...props} review={review} csrf="csrf"/>);loadImage()
 await user.selectOptions(screen.getByLabelText('Класс'),'truck')
 await user.click(screen.getByRole('button',{name:'Сохранить правки'}));await screen.findByText(/Ответ неизвестен/)
 view.unmount();render(<AnnotationEditor {...props} review={{...review,revision:2}} csrf="csrf"/> )
 expect((screen.getByLabelText('Класс') as HTMLSelectElement).value).toBe('truck')
 await user.click(screen.getByRole('button',{name:'Повторить сохранённый запрос'}));await screen.findByText(/Версия сохранена/)
 expect(fetchMock.mock.calls[1][1].body).toBe(fetchMock.mock.calls[0][1].body)
 expect(fetchMock.mock.calls[1][1].headers['Idempotency-Key']).toBe(fetchMock.mock.calls[0][1].headers['Idempotency-Key'])
 expect(JSON.parse(fetchMock.mock.calls[1][1].body).expected_revision).toBe(1)
 const stored=JSON.parse(localStorage.getItem('annotation:run:frame:sha:proposal')!)
 expect(stored.history).toHaveLength(1);expect(stored.pending).toBeNull()
 await user.click(screen.getByRole('button',{name:'Удалить завершённый локальный черновик'}))
 expect(localStorage.getItem('annotation:run:frame:sha:proposal')).toBeNull()
})

it('preserves unsent owner changes across a newer revision and exposes reconciliation',async()=>{
 const user=userEvent.setup(),view=render(<AnnotationEditor {...props} review={review}/>)
 await user.selectOptions(screen.getByLabelText('Класс'),'truck');view.unmount()
 render(<AnnotationEditor {...props} review={{...review,revision:3}}/>)
 expect((screen.getByLabelText('Класс') as HTMLSelectElement).value).toBe('truck')
 expect(screen.getByRole('button',{name:'Загрузить новую версию для сравнения'})).toBeTruthy()
 expect(JSON.parse(localStorage.getItem('annotation:run:frame:sha:proposal')!).reviewRevision).toBe(1)
})

it('blocks submission for displayed invalid geometry and resets frame verification immediately',async()=>{
 const user=userEvent.setup(),fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock)
 render(<AnnotationEditor {...props} review={review}/>);loadImage()
 await user.click(screen.getByRole('checkbox'));expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(true)
 fireEvent.change(screen.getByLabelText('Слева'),{target:{value:'.9'}})
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false)
 await user.click(screen.getByRole('button',{name:'Сохранить правки'}));await user.click(screen.getByRole('button',{name:'Одобрить весь кадр'}))
 expect(fetchMock).not.toHaveBeenCalled()
 await user.click(screen.getByRole('button',{name:'Вернуть сохранённые границы'}))
 expect((screen.getByRole('button',{name:'Сохранить правки'}) as HTMLButtonElement).disabled).toBe(false)
})

it('requires a successfully loaded image for whole-frame confirmation',async()=>{
 const user=userEvent.setup();render(<AnnotationEditor {...props} review={review}/>)
 const checkbox=screen.getByRole('checkbox') as HTMLInputElement
 expect(checkbox.disabled).toBe(true);loadImage();expect(checkbox.disabled).toBe(false)
 await user.click(checkbox);fireEvent.error(screen.getByAltText('Кадр для исправления объектов'))
 expect(checkbox.disabled).toBe(true);expect(checkbox.checked).toBe(false)
 expect((screen.getByRole('button',{name:'Одобрить весь кадр'}) as HTMLButtonElement).disabled).toBe(true)
})

it.each([{reason:42},{verified:'yes'},{reviewRevision:'1'},{pending:{key:crypto.randomUUID(),body:JSON.stringify({expected_revision:9,objects:initial,status:'pending',whole_frame_verified:false,reason:''})}}])('rejects corrupt stored draft shape or request binding %j',patch=>{
 localStorage.setItem('annotation:run:frame:sha:proposal',JSON.stringify({binding:'annotation:run:frame:sha:proposal',history:[initial],cursor:0,pending:null,verified:false,reason:'',reviewRevision:1,geometry:{},completed:false,...patch}))
 render(<AnnotationEditor {...props} review={review}/>)
 expect(screen.queryByRole('button',{name:'Повторить сохранённый запрос'})).toBeNull()
 expect((screen.getByLabelText('Причина решения') as HTMLTextAreaElement).value).toBe('')
})

it('does not send without durable pending storage and recovers the retained edits',async()=>{
 const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:'proposal'})});vi.stubGlobal('fetch',fetchMock)
 render(<AnnotationEditor {...props}/>);await user.selectOptions(screen.getByLabelText('Класс'),'truck')
 const write=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('quota','QuotaExceededError')})
 await user.click(screen.getByRole('button',{name:'Отправить поправки на проверку'}))
 expect(fetchMock).not.toHaveBeenCalled();expect((screen.getByLabelText('Класс') as HTMLSelectElement).value).toBe('truck')
 write.mockRestore();await user.click(screen.getByRole('button',{name:'Отправить поправки на проверку'}));await screen.findByText(/Поправки отправлены/)
 expect(JSON.parse(fetchMock.mock.calls[0][1].body).objects[0].class_name).toBe('truck')
})

it('resizes tiny edge boxes within bounds and previews the moving resize handle',async()=>{
 expect(validObjects([{...initial[0],box:shiftBox([.9999,.9998,1,1],-1,-1,true)}])).toBe(true)
 vi.stubGlobal('PointerEvent',MouseEvent)
 const user=userEvent.setup(),view=render(<AnnotationEditor {...props}/> )
 vi.spyOn(view.container.querySelector('.annotation-canvas')!,'getBoundingClientRect').mockReturnValue({width:100,height:100,x:0,y:0,top:0,left:0,bottom:100,right:100,toJSON:()=>({})})
 await user.click(screen.getByRole('button',{name:'Объект 1'}))
 const handle=screen.getByRole('button',{name:'Изменить размер выбранного объекта'})
 fireEvent.pointerDown(handle,{clientX:50,clientY:60,pointerId:1});fireEvent.pointerMove(handle,{clientX:70,clientY:80,pointerId:1})
 expect(handle.style.left).toBe('70%');expect(handle.style.top).toBe('80%')
 fireEvent.pointerUp(handle,{clientX:70,clientY:80,pointerId:1})
 expect((screen.getByLabelText('Справа') as HTMLInputElement).value).toBe('0.7')
})

it('keeps later-page rows after save, deduplicates paging, serializes reads and focuses the new revision',async()=>{
 const user=userEvent.setup(),later={...review,id:'later',input_id:'later-frame'},first={...review,id:'first'}
 let release!:()=>void
 const fetchMock=vi.fn(async(url:string,options?:RequestInit)=>{
  if(options?.method==='POST')return {ok:true,json:async()=>({id:'later',revision:2})}
  if(url.endsWith('/later'))return {ok:true,json:async()=>({...later,revision:2})}
  if(url.includes('offset=50')){await new Promise<void>(resolve=>{release=resolve});return {ok:true,json:async()=>({annotations:[first,later],next_offset:null})}}
  return {ok:true,json:async()=>({annotations:[first],next_offset:50})}
 });vi.stubGlobal('fetch',fetchMock);render(<AnnotationQueue csrf="csrf"/> )
 await user.click(await screen.findByRole('button',{name:'Показать ещё'}))
 expect((screen.getByRole('button',{name:'Показать ещё'}) as HTMLButtonElement).disabled).toBe(true)
 await user.click(screen.getByRole('button',{name:'Показать ещё'}));release()
 await screen.findByRole('button',{name:/Кадр later-fr/})
 expect(fetchMock.mock.calls.filter(([url])=>url.includes('offset=50'))).toHaveLength(1)
 expect(screen.getAllByRole('button',{name:/Кадр frame/})).toHaveLength(1)
 await user.click(screen.getByRole('button',{name:/Кадр later-fr/}));await user.click(screen.getByRole('button',{name:'Сохранить правки'}))
 const heading=await screen.findByRole('heading',{name:'Проверка кадра · версия 2'});await waitFor(()=>expect(document.activeElement).toBe(heading))
 await user.click(screen.getByRole('button',{name:'Вернуться к очереди'}))
 const row=screen.getByRole('button',{name:/Кадр later-fr · Версия 2/});await waitFor(()=>expect(document.activeElement).toBe(row))
 expect(screen.getByRole('button',{name:/Кадр frame/})).toBeTruthy()
})

it('keeps selected exact versions visible after queue refresh and enforces the export limit',async()=>{
 const user=userEvent.setup(),rows=Array.from({length:33},(_,i)=>({...review,id:`p${i}`,input_id:`frame${i}`,version_id:`v${i}`,status:'approved'}))
 let refreshed=false
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({annotations:refreshed?rows.map(row=>({...row,status:'pending',revision:2,version_id:`new-${row.version_id}`})):rows,next_offset:null})})))
 render(<AnnotationQueue csrf="csrf"/>);await screen.findAllByRole('checkbox')
 for(const checkbox of screen.getAllByRole('checkbox').slice(0,32))fireEvent.click(checkbox)
 expect((screen.getAllByRole('checkbox')[32] as HTMLInputElement).disabled).toBe(true)
 refreshed=true;await user.click(screen.getByRole('button',{name:'Обновить очередь'}));await screen.findByRole('button',{name:/Кадр frame0 · Версия 2/})
 const selection=screen.getByRole('region',{name:'Выбранные версии для экспорта'})
 expect(within(selection).getAllByRole('listitem')).toHaveLength(32)
 expect(within(selection).getByText('v0')).toBeTruthy()
 await user.click(within(selection).getAllByRole('button')[0]);expect(within(selection).getAllByRole('listitem')).toHaveLength(31)
})

it('recovers a second uncertain submission after an acknowledged submission',async()=>{
 const user=userEvent.setup()
 const fetchMock=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({id:'proposal'})}).mockRejectedValueOnce(new TypeError('lost')).mockResolvedValue({ok:true,json:async()=>({id:'proposal'})})
 vi.stubGlobal('fetch',fetchMock)
 const view=render(<AnnotationEditor {...props}/>)
 await user.click(screen.getByRole('button',{name:'Отправить поправки на проверку'}));await screen.findByText(/Поправки отправлены/)
 await user.click(screen.getByRole('button',{name:'Отправить поправки на проверку'}));await screen.findByText(/Ответ неизвестен/)
 expect(JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!).completed).toBe(false)
 view.unmount();render(<AnnotationEditor {...props}/>)
 await user.click(screen.getByRole('button',{name:'Повторить сохранённый запрос'}));await screen.findByText(/Поправки отправлены/)
 expect(fetchMock.mock.calls[2][1].body).toBe(fetchMock.mock.calls[1][1].body)
 expect(fetchMock.mock.calls[2][1].headers['Idempotency-Key']).toBe(fetchMock.mock.calls[1][1].headers['Idempotency-Key'])
 expect(fetchMock.mock.calls[1][1].headers['Idempotency-Key']).not.toBe(fetchMock.mock.calls[0][1].headers['Idempotency-Key'])
})

it('keeps an approved pending request frozen when its image fails before reload',async()=>{
 const user=userEvent.setup()
 const fetchMock=vi.fn().mockRejectedValueOnce(new TypeError('lost')).mockResolvedValue({ok:true,json:async()=>({id:'proposal',revision:2})})
 vi.stubGlobal('fetch',fetchMock)
 const view=render(<AnnotationEditor {...props} review={review} csrf="csrf"/>);loadImage()
 await user.click(screen.getByRole('checkbox'))
 await user.click(screen.getByRole('button',{name:'Одобрить весь кадр'}));await screen.findByText(/Ответ неизвестен/)
 const frozen=localStorage.getItem('annotation:run:frame:sha:proposal')
 fireEvent.error(screen.getByAltText('Кадр для исправления объектов'))
 expect(localStorage.getItem('annotation:run:frame:sha:proposal')).toBe(frozen)
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false)
 view.unmount();render(<AnnotationEditor {...props} review={{...review,revision:2}} csrf="csrf"/> )
 await user.click(screen.getByRole('button',{name:'Повторить сохранённый запрос'}));await screen.findByText(/Версия сохранена/)
 expect(fetchMock.mock.calls[1][1].body).toBe(fetchMock.mock.calls[0][1].body)
 expect(fetchMock.mock.calls[1][1].headers['Idempotency-Key']).toBe(fetchMock.mock.calls[0][1].headers['Idempotency-Key'])
 expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({status:'approved',whole_frame_verified:true,expected_revision:1})
})

it('draws in reverse on a scaled, translated image and records one undo operation',async()=>{
 vi.stubGlobal('PointerEvent',MouseEvent)
 const user=userEvent.setup(),view=render(<AnnotationEditor {...props}/>)
 vi.spyOn(view.container.querySelector('.annotation-canvas')!,'getBoundingClientRect').mockReturnValue({width:400,height:200,left:50,top:30,right:450,bottom:230,x:50,y:30,toJSON:()=>({})})
 await user.click(screen.getByRole('button',{name:'Нарисовать объект'}))
 const viewport=view.container.querySelector('.annotation-viewport')!
 fireEvent.pointerDown(viewport,{clientX:370,clientY:190})
 fireEvent.pointerMove(viewport,{clientX:130,clientY:70})
 fireEvent.pointerUp(viewport,{clientX:130,clientY:70})
 const saved=JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!)
 expect(saved.history).toHaveLength(2)
 expect(saved.history[1][1].box).toEqual([.2,.2,.8,.8])
 fireEvent.click(screen.getByRole('button',{name:'Объект 1: Экскаватор'}),{detail:1})
 expect(screen.getByRole('button',{name:'Объект 2'}).getAttribute('aria-pressed')).toBe('true')
 await waitFor(()=>expect(document.activeElement).toBe(screen.getByLabelText('Класс')))
 expect(screen.getAllByRole('button',{name:/Изменить размер/})).toHaveLength(8)
 await user.selectOptions(screen.getByLabelText('Класс'),'mobile_crane')
 expect(JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!).history.at(-1)[1].class_name).toBe('mobile_crane')
 await user.click(screen.getByRole('button',{name:'Отменить'}));await user.click(screen.getByRole('button',{name:'Отменить'}))
 expect(view.container.querySelectorAll('.annotation-box')).toHaveLength(1)
})

it('cancels a geometry preview when a second touch starts pinch and keeps history unchanged',()=>{
 class TouchPointer extends MouseEvent {pointerId:number;constructor(type:string,options:PointerEventInit){super(type,options);this.pointerId=options.pointerId??0}}
 vi.stubGlobal('PointerEvent',TouchPointer)
 const view=render(<AnnotationEditor {...props}/>)
 const viewport=view.container.querySelector('.annotation-viewport')!,canvas=view.container.querySelector('.annotation-canvas')!
 const bounds={width:400,height:200,left:0,top:0,right:400,bottom:200,x:0,y:0,toJSON:()=>({})}
 vi.spyOn(canvas,'getBoundingClientRect').mockReturnValue(bounds);vi.spyOn(viewport,'getBoundingClientRect').mockReturnValue(bounds)
 const box=screen.getByRole('button',{name:'Объект 1: Экскаватор'}),before=localStorage.getItem('annotation:run:frame:sha:visitor')
 fireEvent.pointerDown(box,{pointerId:1,clientX:60,clientY:80})
 fireEvent.pointerMove(box,{pointerId:1,clientX:100,clientY:90})
 fireEvent.pointerDown(viewport,{pointerId:2,clientX:200,clientY:90})
 fireEvent.pointerMove(viewport,{pointerId:2,clientX:300,clientY:90})
 fireEvent.pointerUp(box,{pointerId:1,clientX:100,clientY:90});fireEvent.pointerUp(viewport,{pointerId:2,clientX:300,clientY:90})
 expect(localStorage.getItem('annotation:run:frame:sha:visitor')).toBe(before)
 expect(screen.getByLabelText('Масштаб фото').textContent).toBe('200%')
})

it('clamps every resize handle including tiny boxes at all image edges',()=>{
 for(const handle of ['n','ne','e','se','s','sw','w','nw'] as const){
  for(const [dx,dy] of [[-2,-2],[2,2],[-2,2],[2,-2]]){
   expect(validObjects([{...initial[0],box:resizeBox(initial[0].box,dx,dy,handle)}])).toBe(true)
   expect(validObjects([{...initial[0],box:resizeBox([.9999,.9999,1,1],dx,dy,handle)}])).toBe(true)
  }
 }
})

it('focuses a clicked box so the next keyboard arrow edits that object',async()=>{
 const user=userEvent.setup();render(<AnnotationEditor {...props}/> )
 await user.click(screen.getByRole('button',{name:'Выбрать'}))
 const box=screen.getByRole('button',{name:'Объект 1: Экскаватор'})
 await user.click(box);expect(document.activeElement).toBe(box)
 await user.keyboard('{ArrowRight}')
 expect(JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!).history.at(-1)[0].box[0]).toBe(.11)
})

it('disables drawing at capacity and never falls through to moving an existing box',async()=>{
 vi.stubGlobal('PointerEvent',MouseEvent)
 const user=userEvent.setup(),objects=Array.from({length:299},(_,index)=>({...initial[0],id:`object-${index}`}))
 const view=render(<AnnotationEditor {...props} initial={objects}/>)
 vi.spyOn(view.container.querySelector('.annotation-canvas')!,'getBoundingClientRect').mockReturnValue({width:100,height:100,left:0,top:0,right:100,bottom:100,x:0,y:0,toJSON:()=>({})})
 await user.click(screen.getByRole('button',{name:'Нарисовать объект'}));await user.click(screen.getByRole('button',{name:'Добавить объект'}))
 expect(screen.getByRole('button',{name:'Нарисовать объект'})).toHaveProperty('disabled',true)
 expect(screen.getByText(/Достигнут предел: 300 объектов/)).toBeTruthy()
 const before=localStorage.getItem('annotation:run:frame:sha:visitor'),box=screen.getByRole('button',{name:'Объект 1: Экскаватор'})
 fireEvent.pointerDown(box,{clientX:20,clientY:20});fireEvent.pointerMove(box,{clientX:40,clientY:40});fireEvent.pointerUp(box,{clientX:40,clientY:40})
 expect(localStorage.getItem('annotation:run:frame:sha:visitor')).toBe(before)
})

it('opens and focuses the affected object when pending coordinates are hidden by selection',async()=>{
 const user=userEvent.setup(),view=render(<AnnotationEditor {...props} initial={[...initial,{...initial[0],id:'second'}]}/> )
 fireEvent.change(screen.getByLabelText('Слева'),{target:{value:'.9'}})
 await user.click(screen.getByRole('button',{name:'Объект 2'}))
 expect(screen.getByRole('button',{name:'Отправить поправки на проверку'})).toHaveProperty('disabled',true)
 await user.click(screen.getByRole('button',{name:'Исправить границы объекта 1'}))
 await waitFor(()=>expect(document.activeElement).toBe(screen.getByLabelText('Слева')))
 expect(view.container.querySelector('.annotation-selected details')).toHaveProperty('open',true)
 expect(screen.getByLabelText('Слева')).toHaveProperty('value','.9')
 await user.click(screen.getByRole('button',{name:'Вернуть сохранённые границы'}))
 expect(screen.getByRole('button',{name:'Отправить поправки на проверку'})).toHaveProperty('disabled',false)
})

it.each(['n','ne','e','se','s','sw','w','nw'] as const)('persists the exact %s handle drag once and preserves its opposite edges',handle=>{
 vi.stubGlobal('PointerEvent',MouseEvent)
 const view=render(<AnnotationEditor {...props}/> )
 vi.spyOn(view.container.querySelector('.annotation-canvas')!,'getBoundingClientRect').mockReturnValue({width:100,height:100,left:0,top:0,right:100,bottom:100,x:0,y:0,toJSON:()=>({})})
 const button=view.container.querySelector(`.handle-${handle}`)!
 fireEvent.pointerDown(button,{clientX:20,clientY:20});fireEvent.pointerMove(button,{clientX:25,clientY:25});fireEvent.pointerMove(button,{clientX:30,clientY:30});fireEvent.pointerUp(button,{clientX:30,clientY:30})
 const stored=JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!)
 expect(stored.history).toHaveLength(2);expect(stored.cursor).toBe(1)
 expect(stored.history[1][0].box).toEqual([
  handle.includes('w') ? .1+.1 : .1, handle.includes('n') ? .2+.1 : .2,
  handle.includes('e') ? .5+.1 : .5, handle.includes('s') ? .6+.1 : .6,
 ])
 fireEvent.click(screen.getByRole('button',{name:'Отменить'}))
 const undone=JSON.parse(localStorage.getItem('annotation:run:frame:sha:visitor')!)
 expect(undone.cursor).toBe(0);expect(undone.history[undone.cursor][0].box).toEqual(initial[0].box)
})
