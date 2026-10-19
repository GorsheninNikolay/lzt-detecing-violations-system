import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import TrialExamples from './TrialExamples'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const fixture={examples:[{title:'Earthworks',found:'Excavator',expected:'Truck',check:'Review',outcome:'Illustrative',photos:['/api/projects/site/trial/photos/photo.jpg'],annotations:[{label:'Illustrative box',box:[.1,.1,.5,.5]}],signals:[{kind:'illustrative',state:'new',comment:'Check on site'}]}]}
it('preserves illustrative annotations and signals and stages real photo bytes without running analysis',async()=>{
 const fetcher=vi.fn(async(url:string,_options?:RequestInit)=>url.endsWith('/trial')?{ok:true,json:async()=>fixture}:{ok:true,blob:async()=>new Blob(['photo bytes'],{type:'image/jpeg'})})
 vi.stubGlobal('fetch',fetcher);const rerun=vi.fn()
 render(<TrialExamples projectId="site" readOnly={false} rerun={rerun} />)
 await screen.findByText('Earthworks');expect(screen.getByText(/Illustrative box/)).toBeTruthy();expect(screen.getByText(/Check on site/)).toBeTruthy()
 fireEvent.click(screen.getByRole('button',{name:'Загрузить фото для нового анализа'}))
 await vi.waitFor(()=>expect(rerun).toHaveBeenCalledOnce())
 expect(rerun.mock.calls[0][0][0].type).toBe('image/jpeg')
 expect(fetcher.mock.calls.every(call=>call.length===1||(!call[1]?.method || call[1]?.method === 'GET'))).toBe(true)
})
it('keeps imported example rerun unavailable for viewers',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>fixture})))
 render(<TrialExamples projectId="site" readOnly rerun={vi.fn()} />)
 expect(await screen.findByRole('button',{name:'Загрузить фото для нового анализа'})).toHaveProperty('disabled',true)
})
it('clears old examples and ignores old photo staging after a project switch',async()=>{
 let finishPhoto!:(value:unknown)=>void
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.includes('/photos/')?new Promise(resolve=>{finishPhoto=resolve}):url.includes('/B/')?{ok:false,json:async()=>({})}:{ok:true,json:async()=>fixture}))
 const rerun=vi.fn(),view=render(<TrialExamples projectId="A" readOnly={false} rerun={rerun} />)
 await screen.findByText('Earthworks');fireEvent.click(screen.getByRole('button',{name:'Загрузить фото для нового анализа'}))
 view.rerender(<TrialExamples projectId="B" readOnly={false} rerun={rerun} />)
 expect(screen.queryByText('Earthworks')).toBeNull()
 await act(async()=>finishPhoto({ok:true,blob:async()=>new Blob(['old bytes'],{type:'image/jpeg'})}))
 expect(rerun).not.toHaveBeenCalled()
})
it('ignores an earlier project response and displays source and corrected annotations separately',async()=>{
 let finishA!:(value:unknown)=>void
 const corrected={examples:[{...fixture.examples[0],corrections:[{photo:'/photo.jpg',original_annotations:[{label:'Original observation',box:[0,0,1,1]}],corrected_annotations:[{label:'Human correction',box:[.1,.1,.5,.5]}],comment:'Illustrative reviewer comment',illustrative:true}]}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.includes('/A/')?new Promise(resolve=>{finishA=resolve}):{ok:true,json:async()=>corrected}))
 const view=render(<TrialExamples projectId="A" readOnly={false} rerun={vi.fn()} />)
 view.rerender(<TrialExamples projectId="B" readOnly={false} rerun={vi.fn()} />)
 await screen.findByText(/Human correction/)
 await act(async()=>finishA({ok:true,json:async()=>({examples:[{...fixture.examples[0],title:'Old project A'}]})}))
 expect(screen.queryByText('Old project A')).toBeNull()
 expect(screen.getByText(/Original observation/)).toBeTruthy()
 expect(screen.getByText('Иллюстративная правка человеком')).toBeTruthy()
 expect(screen.getByText('Illustrative reviewer comment')).toBeTruthy()
})
it('routes backend-shaped private photo paths through the API prefix',async()=>{
 const photo='/projects/site/trial/photos/photo-id'
 const fetcher=vi.fn(async(url:string)=>url.endsWith('/trial')?{ok:true,json:async()=>({examples:[{...fixture.examples[0],photos:[photo]}]})}:{ok:true,blob:async()=>new Blob(['photo'],{type:'image/jpeg'})})
 vi.stubGlobal('fetch',fetcher)
 render(<TrialExamples projectId="site" readOnly={false} rerun={vi.fn()} />)
 expect((await screen.findByRole('img')).getAttribute('src')).toBe(`/api${photo}`)
 fireEvent.click(screen.getByRole('button',{name:'Загрузить фото для нового анализа'}))
 await vi.waitFor(()=>expect(fetcher).toHaveBeenCalledWith(`/api${photo}`,{credentials:'same-origin'}))
})
