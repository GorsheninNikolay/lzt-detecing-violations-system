import { afterEach, expect, it, vi } from 'vitest'
import { waitFor } from '@testing-library/react'
import { startActivity } from './engagement'
afterEach(()=>vi.unstubAllGlobals())
it('records a hidden tab becoming visible and excludes hidden activity and admin',async()=>{
 let state='hidden';vi.spyOn(document,'visibilityState','get').mockImplementation(()=>state as DocumentVisibilityState)
 const fetcher=vi.fn(async()=>({ok:true,status:200}));vi.stubGlobal('fetch',fetcher)
 history.replaceState({},'','/');const stop=startActivity()
 await Promise.resolve();expect(fetcher).not.toHaveBeenCalled()
 state='visible';document.dispatchEvent(new Event('visibilitychange'))
 await waitFor(()=>expect(fetcher).toHaveBeenCalledOnce())
 document.dispatchEvent(new Event('visibilitychange'));window.dispatchEvent(new Event('pointerdown'))
 expect(fetcher).toHaveBeenCalledOnce();stop()
 history.replaceState({},'','/admin');const stopAdmin=startActivity()
 document.dispatchEvent(new Event('visibilitychange'));window.dispatchEvent(new Event('scroll'))
 expect(fetcher).toHaveBeenCalledOnce();stopAdmin();vi.restoreAllMocks()
})
