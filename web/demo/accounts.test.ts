import { describe, expect, it } from 'vitest'
import { createAccountDemo } from './accounts'

describe('isolated account preview', () => {
  it('separates accounts, restricts viewer writes and makes duplicate invitations idempotent', async () => {
    const demo=createAccountDemo()
    const register=async(email:string)=>(await demo.request('POST','/account/register',{email,name:email,password:'correct horse battery staple'})).session
    const owner=await register('owner@example.test'), viewer=await register('viewer@example.test'), outsider=await register('outsider@example.test')
    const created=await demo.request('POST','/projects',{name:'Private site'},'project-key',owner), id=created.data.id
    expect((await demo.request('GET','/projects',{},'',outsider)).data.projects).toEqual([])
    expect((await demo.request('GET',`/projects/${id}/zones`,{},'',outsider)).status).toBe(404)
    const invite=await demo.request('POST',`/projects/${id}/invitations`,{email:'viewer@example.test',role:'viewer'},'',owner)
    expect((await demo.request('POST','/invitations/accept',{token:invite.data.token},'',outsider)).status).toBe(404)
    expect((await demo.request('GET','/notifications',{},'',viewer)).data.notifications).toHaveLength(1)
    expect((await demo.request('POST','/invitations/accept',{token:invite.data.token},'',viewer)).data.role).toBe('viewer')
    const editor=await demo.request('POST',`/projects/${id}/invitations`,{role:'editor'},'',owner)
    expect((await demo.request('POST','/invitations/accept',{token:editor.data.token},'',viewer)).data.role).toBe('viewer')
    expect((await demo.request('GET',`/projects/${id}/zones`,{},'',viewer)).status).toBe(200)
    expect((await demo.request('POST',`/projects/${id}/zones`,{name:'Denied'},'',viewer)).status).toBe(403)
    const zones=(await demo.request('GET',`/projects/${id}/zones`,{},'',owner)).data.zones
    expect((await demo.request('PUT',`/zones/${zones[0].id}/plan`,{entries:[]},'',viewer)).status).toBe(403)
    await demo.request('DELETE',`/projects/${id}/invitations/${editor.data.id}`,{},'',owner)
    expect((await demo.request('POST','/invitations/accept',{token:editor.data.token},'',outsider)).status).toBe(404)
  })
  it('expires invitations and keeps private assistant histories separate', async () => {
    let clock=Date.now();const demo=createAccountDemo(()=>clock)
    const owner=(await demo.request('POST','/account/register',{email:'a@example.test',name:'A',password:'correct horse battery staple'})).session
    const other=(await demo.request('POST','/account/register',{email:'b@example.test',name:'B',password:'correct horse battery staple'})).session
    const id=(await demo.request('POST','/projects',{name:'Site'},'',owner)).data.id
    await demo.request('POST','/assistant/messages',{project_id:id,message:'Private question'},'',owner)
    expect((await demo.request('GET',`/assistant/messages?project_id=${id}`,{},'',other)).status).toBe(404)
    const invite=await demo.request('POST',`/projects/${id}/invitations`,{role:'viewer'},'',owner)
    clock+=8*86400000
    expect((await demo.request('POST','/invitations/accept',{token:invite.data.token},'',other)).status).toBe(404)
  })
})

it('accepts nine-character demo passwords and rejects eight-character ones', async () => {
  const demo = createAccountDemo()
  const register = (email: string, password: string) => demo.request('POST', '/account/register', {email, name: 'Demo', password})
  expect((await register('short@example.test', '12345678')).status).toBe(400)
  expect((await register('valid@example.test', 'demo-pass')).status).toBe(200)
})

it('attaches tutorial materials only to an empty owned project and keeps real history empty', async () => {
  const demo = createAccountDemo()
  const owner = (await demo.request('POST','/account/register',{email:'learn@example.test',name:'Learner',password:'demo-pass'})).session
  const project = (await demo.request('POST','/projects',{name:'Learning'},'',owner)).data.id
  const key = '11111111-1111-4111-8111-111111111111'
  expect((await demo.request('GET',`/projects/${project}/trial`,{},'',owner)).status).toBe(404)
  const [first, replay] = await Promise.all([1,2].map(()=>demo.request('POST',`/projects/${project}/trial`,{},key,owner)))
  expect((await demo.request('POST','/trial/import',{},key,owner)).data.code).toBe('idempotency_key_conflict')
  expect(first.data).toEqual({project_id:project});expect(replay.data).toEqual(first.data)
  expect((await demo.request('GET',`/projects/${project}/trial`,{},'',owner)).data.illustrative).toBe(true)
  expect((await demo.request('GET',`/runs?project_id=${project}`,{},'',owner)).data.total).toBe(0)
  expect((await demo.request('GET',`/signals?project_id=${project}`,{},'',owner)).data.signals).toHaveLength(0)
  expect((await demo.request('POST',`/projects/${project}/trial`,{},'22222222-2222-4222-8222-222222222222',owner)).data.code).toBe('project_not_empty')
  const other = (await demo.request('POST','/projects',{name:'Keep this'},'',owner)).data.id
  expect((await demo.request('POST',`/projects/${other}/trial`,{},key,owner)).data.code).toBe('idempotency_key_conflict')
  const zones=(await demo.request('GET',`/projects/${other}/zones`,{},'',owner)).data.zones
  await demo.request('PUT',`/zones/${zones[0].id}/plan`,{expected_revision:0,entries:[]},'',owner)
  expect((await demo.request('POST',`/projects/${other}/trial`,{},'33333333-3333-4333-8333-333333333333',owner)).data.code).toBe('project_not_empty')
})
it('rejects editor tutorial seeding and unsupported tutorial context',async()=>{
  const demo=createAccountDemo()
  const owner=(await demo.request('POST','/account/register',{email:'owner-learning@example.test',name:'Owner',password:'demo-pass'})).session
  const editor=(await demo.request('POST','/account/register',{email:'editor-learning@example.test',name:'Editor',password:'demo-pass'})).session
  const project=(await demo.request('POST','/projects',{name:'Protected'},'',owner)).data.id
  const invite=(await demo.request('POST',`/projects/${project}/invitations`,{role:'editor'},'',owner)).data
  await demo.request('POST','/invitations/accept',{token:invite.token},'',editor)
  expect((await demo.request('POST',`/projects/${project}/trial`,{},'11111111-1111-4111-8111-111111111111',editor)).data.code).toBe('owner_required')
  expect((await demo.request('POST','/assistant/messages',{message:'Help',tutorial_context:{version:1,step:'run-command'}},'',owner)).status).toBe(400)
  expect((await demo.request('POST','/assistant/messages',{message:'Help',tutorial_context:{version:1,step:'photos'}},'',owner)).status).toBe(200)
})
