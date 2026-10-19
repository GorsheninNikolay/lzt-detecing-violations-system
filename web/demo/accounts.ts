import { randomUUID, scryptSync, timingSafeEqual } from 'node:crypto'
import { trialFixture, trialPhoto, trialZip } from './trial'
import { createDemoStore } from './server'

type Data = Record<string, any>
export function createAccountDemo(now = Date.now) {
  const users = new Map<string, Data>(), sessions = new Map<string,string>(), stores = new Map<string,ReturnType<typeof createDemoStore>>()
  const memberships = new Map<string,Map<string,string>>(), owners = new Map<string,string>(), invitations = new Map<string,Data>(), notifications = new Map<string,Data[]>(), conversations = new Map<string,Data[]>()
  const attachedTrials = new Set<string>(), trialRequests = new Map<string, { projectId: string; kind: string }>(), pendingTrials = new Map<string, Promise<any>>()
  const response=(data:Data,status=200,session?:string)=>({status,data,session})
  const fail=(code:string,status=400)=>response({code},status)
  async function request(method:string,rawUrl:string,body:Data={},key='',session=''):Promise<any>{
    const url=new URL(rawUrl,'http://demo.local'), path=url.pathname.replace(/^\/api/,''); const user=users.get(sessions.get(session)??'')
    if(path==='/account/session')return response({user:user?publicUser(user):null})
    if(path==='/account/register'&&method==='POST'){
      const email=String(body.email??'').trim().toLowerCase(); if(!email.includes('@')||(String(body.password??'').length<9||String(body.password??'').length>1024)||!String(body.name??'').trim())return fail('invalid_registration')
      if([...users.values()].some(item=>item.email===email))return fail('email_already_registered',409)
      const id=randomUUID(), salt=randomUUID();const row={id,email,name:body.name,theme:'system',verified:true,salt,password:scryptSync(body.password,salt,32)};users.set(id,row); const store=createDemoStore(now);stores.set(id,store)
      // Each preview account receives its own illustrative fixtures with fresh project identifiers.
      await store.request('POST','/__demo/state',{state:'empty'})
      const token=randomUUID();sessions.set(token,id);return response({user:publicUser(row)},200,token)
    }
    if(path==='/account/login'&&method==='POST'){
      const row=[...users.values()].find(item=>item.email===String(body.email??'').trim().toLowerCase());if(!row||!timingSafeEqual(row.password,scryptSync(String(body.password??''),row.salt,32)))return fail('invalid_credentials',401)
      const token=randomUUID();sessions.set(token,row.id);return response({user:publicUser(row)},200,token)
    }
    if(path==='/account/logout'){sessions.delete(session);return response({accepted:true},200,'')}
    if(path==='/trial/preview')return response(trialView())
    if(path==='/trial/project.zip'||path==='/trial/photos.zip')return {status:200,data:null,artifact:trialZip(path.endsWith('photos.zip')),contentType:'application/zip'}
    const publicPhoto=path.match(/^\/trial\/photos\/([^/]+)$/);if(publicPhoto){try{return {status:200,data:null,artifact:trialPhoto(publicPhoto[1])}}catch{return fail('not_found',404)}}
    if(path==='/assistant/messages'&&method==='POST'&&body.tutorial_context!==undefined){const context=body.tutorial_context;if(!context||typeof context!=='object'||Array.isArray(context)||Object.keys(context).sort().join(',')!=='step,version'||context.version!==1||!['create_project','add_materials','plan','photos','result','signals','complete'].includes(context.step))return fail('invalid_tutorial_context')}
    if(path==='/assistant/messages'&&!user&&!body.project_id&&method==='POST')return response({messages:[{role:'assistant',content:'Для работы создайте аккаунт, затем проект и загрузите фотографии. Это справка локального предпросмотра; модель не подключена.'}]})
    if(!user)return fail('authentication_required',401)
    if(path==='/account/profile'&&method==='PATCH'){
      if((body.password||body.email&&body.email!==user.email)&&(!body.current_password||!timingSafeEqual(user.password,scryptSync(body.current_password,user.salt,32))))return fail('invalid_credentials',403)
      if(body.theme&&!['system','light','dark'].includes(body.theme))return fail('invalid_theme')
      if(body.name)user.name=body.name;if(body.theme)user.theme=body.theme
      if(body.email&&body.email!==user.email){if([...users.values()].some(item=>item.email===body.email))return fail('email_already_registered',409);user.email=body.email}
      if(body.password){if((body.password.length<9||body.password.length>1024))return fail('password_too_short');user.password=scryptSync(body.password,user.salt,32)}
      if(body.password||body.email)for(const [token,id]of sessions)if(id===user.id&&token!==session)sessions.delete(token)
      return response({user:publicUser(user)})
    }
    if(path==='/notifications')return response({notifications:(notifications.get(user.id)??[]).map(item=>{const invite=[...invitations.values()].find(invite=>invite.id===item.invitation_id);return {...item,actionable:!!invite&&!invite.revoked&&Date.parse(invite.expires_at)>now()}})})
    const read=path.match(/^\/notifications\/([^/]+)\/read$/);if(read){const item=notifications.get(user.id)?.find(item=>item.id===read[1]);if(!item)return fail('not_found',404);item.read=true;return response({accepted:true})}
    const preview=method==='GET'?path.match(/^\/invitations\/([^/]+)$/):null
    const invitation=preview?invitations.get(preview[1]):[...invitations.values()].find(item=>item.token===body.token||item.id===body.invitation_id)
    if(preview||path==='/invitations/accept'){
      if(!invitation||invitation.revoked||Date.parse(invitation.expires_at)<=now()||invitation.email&&invitation.email!==user.email)return fail('invitation_unavailable',404)
      if(preview)return response({project_name:invitation.project_name,role:invitation.role,expires_at:invitation.expires_at})
      const members=memberships.get(invitation.project_id)!;if(!members.has(user.id))members.set(user.id,invitation.role)
      return response({project_id:invitation.project_id,role:members.get(user.id)})
    }
    const projectId=path.match(/^\/projects\/([^/]+)/)?.[1]??url.searchParams.get('project_id')??body.project_id
    let store=stores.get(user.id)!,role='owner'
    if(projectId){role=memberships.get(projectId)?.get(user.id)??'';if(!role)return fail('project_not_found',404);store=stores.get(owners.get(projectId)!)!;if(method!=='GET'&&role==='viewer')return fail('project_read_only',403)}
    const membersPath=path.match(/^\/projects\/([^/]+)\/members(?:\/([^/]+))?$/)
    if(membersPath){const members=memberships.get(projectId)!;if(method==='GET')return response({members:[...members].map(([id,role])=>({user_id:id,name:users.get(id)?.name,email:users.get(id)?.email,role}))});if(role!=='owner')return fail('owner_required',403);if(members.get(membersPath[2])==='owner')return fail('cannot_remove_owner');members.delete(membersPath[2]);return response({accepted:true})}
    const invitesPath=path.match(/^\/projects\/([^/]+)\/invitations(?:\/([^/]+))?$/)
    if(invitesPath){if(role!=='owner')return fail('owner_required',403);if(method==='GET')return response({invitations:[...invitations.values()].filter(item=>item.project_id===projectId)});if(method==='DELETE'){const item=[...invitations.values()].find(item=>item.id===invitesPath[2]&&item.project_id===projectId);if(!item)return fail('not_found',404);item.revoked=true;return response({accepted:true})}
      if(!['viewer','editor'].includes(body.role))return fail('invalid_role');const recipient=body.email?[...users.values()].find(item=>item.email===body.email):null;if(body.email&&!recipient)return fail('recipient_not_registered')
      const projects=(await store.request('GET','/projects')).data.projects;const token=randomUUID(),item={id:randomUUID(),token,project_id:projectId,project_name:projects.find((item:Data)=>item.id===projectId)?.name,email:body.email??null,role:body.role,expires_at:new Date(now()+7*86400000).toISOString(),revoked:false};invitations.set(token,item)
      if(recipient){const rows=notifications.get(recipient.id)??[];rows.push({id:randomUUID(),invitation_id:item.id,project_name:item.project_name,role:item.role,created_at:new Date(now()).toISOString(),read:false,actionable:true});notifications.set(recipient.id,rows)}return response({...item,url:`/invite/${token}`})
    }
    if(path==='/assistant/messages'){const scope=`${user.id}:${projectId??'general'}`;if(method==='GET')return response({messages:conversations.get(scope)??[]});const rows=conversations.get(scope)??[];rows.push({id:randomUUID(),role:'user',content:String(body.message).slice(0,4000)},{id:randomUUID(),role:'assistant',content:'Локальный предпросмотр: модель не подключена. Сверьте фотографии, план работ и сигналы текущего проекта. Помощник ничего не изменяет.'});conversations.set(scope,rows);return response({messages:rows})}
    if(path.match(/^\/projects\/[^/]+\/trial$/)){
      if(method==='GET')return attachedTrials.has(projectId)?response(trialView(projectId)):fail('trial_not_found',404)
      if(method!=='POST')return fail('method_not_allowed',405)
      if(role!=='owner')return fail('owner_required',403)
      if(!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(key))return fail('invalid_idempotency_key')
      const requestKey=`${user.id}:${key}`, previous=trialRequests.get(requestKey)
      if(previous)return previous.projectId===projectId&&previous.kind==='attach'?response({project_id:projectId}):fail('idempotency_key_conflict',409)
      if(pendingTrials.has(requestKey)){await pendingTrials.get(requestKey);return request(method,rawUrl,body,key,session)}
      if(pendingTrials.has(projectId)){await pendingTrials.get(projectId);return request(method,rawUrl,body,key,session)}
      const operation=(async()=>{
        const zones=(await store.request('GET',`/projects/${projectId}/zones`)).data.zones
        const plans=await Promise.all(zones.map((zone:Data)=>store.request('GET',`/zones/${zone.id}/plan`)))
        const runs=await store.request('GET',`/runs?project_id=${projectId}`)
        const projects=(await store.request('GET','/projects')).data.projects
        if(attachedTrials.has(projectId)||zones.length!==1||plans.some(plan=>plan.data.revision_number!==0||plan.data.entries.length)||runs.data.total||projects.find((project:Data)=>project.id===projectId)?.cover_sha256)return fail('project_not_empty',409)
        const fixture=trialFixture()
        const saved=await store.request('PUT',`/zones/${zones[0].id}/plan`,{expected_revision:0,entries:fixture.plan.map((item:Data)=>({...item,catalog_work_id:'earthworks',start_at:item.starts_at,end_at:item.ends_at,allowed_equipment:[],excluded_equipment:[],stage_key:'excavation'}))})
        if(saved.status>=300)return saved
        attachedTrials.add(projectId);trialRequests.set(requestKey,{projectId,kind:'attach'})
        return response({project_id:projectId})
      })()
      pendingTrials.set(projectId,operation);pendingTrials.set(requestKey,operation)
      try{return await operation}finally{pendingTrials.delete(projectId);pendingTrials.delete(requestKey)}
    }
    const projectPhoto=path.match(/^\/projects\/[^/]+\/trial\/photos\/([^/]+)$/);if(projectPhoto){if(!attachedTrials.has(projectId))return fail('photo_not_found',404);try{return {status:200,data:null,artifact:trialPhoto(projectPhoto[1])}}catch{return fail('not_found',404)}}
    if(path==='/trial/import'){
      if(!key)return fail('idempotency_key_required')
      if(pendingTrials.has(`${user.id}:${key}`))await pendingTrials.get(`${user.id}:${key}`)
      const prior=trialRequests.get(`${user.id}:${key}`);if(prior)return prior.kind==='import'?response({project_id:prior.projectId}):fail('idempotency_key_conflict',409)
      const fixture=trialFixture(),created=await store.request('POST','/projects',{name:fixture.name},key);const id=created.data.id
      owners.set(id,user.id);memberships.set(id,new Map([[user.id,'owner']]))
      const zones=(await store.request('GET',`/projects/${id}/zones`)).data.zones
      await store.request('PUT',`/zones/${zones[0].id}/plan`,{expected_revision:0,entries:fixture.plan.map((item:Data)=>({...item,catalog_work_id:'earthworks',start_at:item.starts_at,end_at:item.ends_at,allowed_equipment:[],excluded_equipment:[],stage_key:'excavation'}))})
      attachedTrials.add(id);trialRequests.set(`${user.id}:${key}`,{projectId:id,kind:'import'})
      return response({project_id:id})
    }
    if(path==='/projects'&&method==='GET'){const rows=[];for(const [id,members]of memberships)if(members.has(user.id)){const source=stores.get(owners.get(id)!)!;const project=(await source.request('GET','/projects')).data.projects.find((item:Data)=>item.id===id);if(project)rows.push({...project,role:members.get(user.id)})}return response({projects:rows})}
    if(!projectId&&/^\/(runs\/|zones\/|signals\/)/.test(path)){
      let found=false
      for(const [id,members]of memberships){
        if(!members.has(user.id))continue
        const ownerStore=stores.get(owners.get(id)!)!
        const runId=path.match(/^\/runs\/([^/]+)/)?.[1]
        const zoneId=path.match(/^\/zones\/([^/]+)/)?.[1]
        const signalId=path.match(/^\/signals\/([^/]+)/)?.[1]
        let belongs=false
        if(runId){const result=await ownerStore.request('GET',`/runs/${runId}`);belongs=result.status===200&&result.data.project_id===id}
        if(zoneId){const result=await ownerStore.request('GET',`/projects/${id}/zones`);belongs=result.data.zones?.some((item:Data)=>item.id===zoneId)}
        if(signalId){const result=await ownerStore.request('GET',`/signals?project_id=${id}`);belongs=result.data.signals?.some((item:Data)=>item.id===signalId)}
        if(belongs){if(method!=='GET'&&members.get(user.id)==='viewer')return fail('project_read_only',403);store=ownerStore;found=true;break}
      }
      if(!found)return fail('not_found',404)
    }
    const result=await store.request(method,rawUrl,body,key)
    if(path==='/projects'&&method==='POST'&&result.status<300){owners.set(result.data.id,user.id);memberships.set(result.data.id,new Map([[user.id,'owner']]))}
    return result
  }
  return {request}
}
function publicUser(user:Data){return {id:user.id,email:user.email,name:user.name,theme:user.theme,verified:user.verified}}

function trialView(projectId?:string){const fixture=trialFixture();return {...fixture,illustrative:true,examples:fixture.examples.map((example:Data)=>({...example,illustrative:true,photos:example.photos.map((name:string)=>projectId?`/api/projects/${projectId}/trial/photos/${name.split('/').pop()}`:`/api/trial/photos/${name.split('/').pop()}`)}))}}
