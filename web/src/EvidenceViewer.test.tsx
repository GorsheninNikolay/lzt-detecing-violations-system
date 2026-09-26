import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EvidenceViewer, SourceImage } from './EvidenceViewer'

beforeEach(()=>{
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:photo')})
 Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()})

it('leaves pointer activation of the photo retry button outside viewer pan capture',async()=>{
 const fetchMock=vi.fn().mockResolvedValueOnce({ok:false,json:async()=>({})}).mockResolvedValue({ok:true,blob:async()=>new Blob(['image'])})
 vi.stubGlobal('fetch',fetchMock)
 const view=render(<EvidenceViewer runId="run" frames={[{input_id:'frame',ordinal:0,artifact_id:'artifact',sha256:'sha',usable:true,observations:[]}]} native={[]} objects={[]} showBoxes selected={0} onSelect={()=>{}} onClose={()=>{}}/>)
 const pan=view.container.querySelector('.viewer-image')!,capture=vi.fn();Object.defineProperty(pan,'setPointerCapture',{value:capture})
 const retry=await screen.findByRole('button',{name:'Повторить'})
 await userEvent.setup().pointer([{target:retry,keys:'[MouseLeft>]'}, {target:retry,keys:'[/MouseLeft]'}])
 expect(capture).not.toHaveBeenCalled()
 await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2))
 expect(await screen.findByRole('img')).toBeTruthy()
})

it('offers a new fetch after HTTP-200 bytes fail image decoding',async()=>{
 const fetchMock=vi.fn(async()=>({ok:true,blob:async()=>new Blob(['corrupt'])}));vi.stubGlobal('fetch',fetchMock)
 render(<SourceImage runId="run" artifactId="artifact" label="Кадр 1" description=""/> )
 fireEvent.error(await screen.findByRole('img'))
 expect(screen.getByText('Не удалось прочитать изображение')).toBeTruthy()
 await userEvent.setup().click(screen.getByRole('button',{name:'Повторить'}))
 await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2))
 expect(await screen.findByRole('img')).toBeTruthy()
})
