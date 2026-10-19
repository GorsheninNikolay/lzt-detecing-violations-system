import { expect, it } from 'vitest'
import { trialFixture, trialZip, validateTrialZip } from './trial'
it('round-trips the bundled complete archive and rejects corrupted photo bytes',()=>{
 const bytes=trialZip();expect(validateTrialZip(bytes)).toEqual(trialFixture())
 const corrupted=Buffer.from(bytes);corrupted[corrupted.indexOf(Buffer.from([0xff,0xd8]))+3]^=0xff
 expect(()=>validateTrialZip(corrupted)).toThrow()
})
it('rejects a photos-only archive as a project import',()=>{expect(()=>validateTrialZip(trialZip(true))).toThrow()})
