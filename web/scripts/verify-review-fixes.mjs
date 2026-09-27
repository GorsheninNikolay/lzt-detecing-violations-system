import { createRequire } from 'node:module'
import { mkdir, writeFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import { auditTargets } from './target-audit.mjs'
const require=createRequire(process.env.PLAYWRIGHT_PACKAGE||'/private/tmp/lzt-design-experiment/tooling/package.json')
const {chromium}=require('playwright-core'),root='/private/tmp/lzt-design-experiment',out=root+'/evidence/review-fixes',A='11111111-1111-4111-8111-111111111111',R='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
await mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/private/tmp/lzt-video-browsers/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell'})
const checks=[],targets=[]
async function check(name,fn){try{checks.push({name,status:'pass',detail:await fn()})}catch(error){checks.push({name,status:'fail',error:error.message});console.log('FAIL',name,error.message.slice(0,250))}}
const doubleText=page=>page.evaluate(()=>{const sizes=[...document.querySelectorAll('body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const[e,size]of sizes)e.style.fontSize=`${size*2}px`})
async function targetCheck(page,label){const result=await auditTargets(page);targets.push({label,...result});assert.deepEqual(result.failures,[])}
try{for(const[name,port]of[['project-dashboard',5174],['photo-workspace',5175],['3d-experience',5176]]){
 const base=`http://127.0.0.1:${port}`,context=await browser.newContext({viewport:{width:390,height:560},reducedMotion:'reduce'})
 const page=await context.newPage();page.setDefaultTimeout(12000);page.on('dialog',dialog=>dialog.accept())
 await context.request.post(base+'/api/__demo/state',{data:{state:'result'}})
 await page.goto(base+`/projects/${A}`);await page.locator('.tour-tooltip').waitFor();await page.evaluate(()=>document.fonts.ready);await doubleText(page)
 await check(name+': first-use onboarding at 200% text in short viewport',async()=>{
   const states=[]
   for(let step=0;step<5;step++){
     await page.waitForTimeout(80)
     const rect=await page.locator('.tour-tooltip').evaluate(e=>{const r=e.getBoundingClientRect(),t=document.querySelector('.tour-spotlight').getBoundingClientRect();return{top:r.top,bottom:r.bottom,height:r.height,viewport:innerHeight,overlap:Math.min(r.right,t.right)>Math.max(r.left,t.left)&&Math.min(r.bottom,t.bottom)>Math.max(r.top,t.top)}})
     assert(rect.top>=0&&rect.bottom<=rect.viewport+1);assert.equal(rect.overlap,false);states.push(rect)
     const button=step===4?page.getByRole('button',{name:'Перейти к загрузке фото',exact:true}):page.getByRole('button',{name:'Далее',exact:true})
     await button.scrollIntoViewIfNeeded();await button.click()
   }
   await page.locator('#images').waitFor();return states
 })
 if(await page.locator('.tour-tooltip').count())await page.keyboard.press('Escape')
 for(const width of [390,1440])await check(name+`: More menu at 200% text, ${width}x560`,async()=>{
   await page.setViewportSize({width,height:560});await page.goto(base+`/projects/${A}`);await page.locator('main h1').waitFor();await doubleText(page);await page.locator('.more-menu>summary').click()
   const measurement=await page.locator('.secondary-nav').evaluate(nav=>{const entries=[...nav.querySelectorAll('button,a')].map(e=>{const r=e.getBoundingClientRect();return{text:e.textContent,left:r.left,right:r.right,top:r.top,bottom:r.bottom}});const overlaps=[];for(let i=0;i<entries.length;i++)for(let j=i+1;j<entries.length;j++){const a=entries[i],b=entries[j];if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)overlaps.push([a.text,b.text])}return{entries,overlaps}})
   assert.deepEqual(measurement.overlaps,[])
   for(const link of await page.locator('.secondary-nav a').all()){await link.scrollIntoViewIfNeeded();await link.focus();const reachable=await link.evaluate(e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return e===hit||e.contains(hit)});assert(reachable)}
   await targetCheck(page,name+` More menu ${width}`);await page.screenshot({path:`${out}/${name}-more-text200-${width}.png`,fullPage:false});return measurement
 })
 await page.setViewportSize({width:390,height:1000})
 await page.goto(base+`/projects/${A}/runs/${R}`);await page.locator('.result-feature-image img').waitFor()
 if(name==='photo-workspace')await check('photo box selection reveals its description from evidence mode',async()=>{await page.getByRole('button',{name:'Основание',exact:true}).click();assert.equal(await page.locator('.object-list').isVisible(),false);await page.getByRole('button',{name:'Объект 1: Экскаватор',exact:true}).click();assert.equal(await page.locator('.object-list').isVisible(),true);assert.equal(await page.getByRole('button',{name:'1. Экскаватор',exact:true}).getAttribute('aria-pressed'),'true')})
 await page.getByText('Исправить разметку',{exact:true}).click();await page.locator('.annotation-canvas img').waitFor()
 await check(name+': annotation number contrast and target coverage',async()=>{
  const contrast=await page.locator('.annotation-box span').first().evaluate(e=>{const s=getComputedStyle(e),rgb=c=>c.match(/[\d.]+/g).map(Number).slice(0,3),l=c=>rgb(c).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0),values=[l(s.color),l(s.backgroundColor)].sort((a,b)=>b-a);return{foreground:s.color,background:s.backgroundColor,ratio:(values[0]+.05)/(values[1]+.05)}})
  assert(contrast.ratio>=4.5);await targetCheck(page,name+' annotation editor');if(name==='project-dashboard'){await page.screenshot({path:`${out}/project-dashboard-editor-390.png`,fullPage:true});await page.screenshot({path:`${root}/evidence/confirmation/project-dashboard-editor-390.png`,fullPage:true})}return contrast
 })
 await context.request.post(base+'/api/__demo/state',{data:{state:'analyzing'}});await page.goto(base+`/projects/${A}/runs/${R}`)
 await check(name+': system override disables motion controls without changing saved choice',async()=>{await page.evaluate(()=>localStorage.setItem('analysis-motion','on'));await page.reload();const checkbox=page.getByRole('checkbox',{name:'Движение во время анализа'});await checkbox.waitFor();assert.equal(await checkbox.isDisabled(),true);await page.locator('.more-menu>summary').click();assert.equal(await page.getByRole('button',{name:'Движение: выключено системой'}).isDisabled(),true);assert.equal(await page.evaluate(()=>localStorage.getItem('analysis-motion')),'on')})
 for(const[scene,path]of[['upload',`/projects/${A}/new`],['plan',`/projects/${A}/plan`],['signals',`/projects/${A}/signals`]])await check(name+': measured targets '+scene,async()=>{await context.request.post(base+'/api/__demo/state',{data:{state:'result'}});await page.goto(base+path);await page.locator('main h1').waitFor();await page.waitForTimeout(150);await targetCheck(page,name+' '+scene)})
 await check(name+': actual demo preset clears retained request, annotation and IndexedDB drafts',async()=>{
   await context.request.post(base+'/api/__demo/state',{data:{state:'recovery'}});await page.goto(base+`/projects/${A}/runs/${R}`);await page.getByText('Исправить разметку',{exact:true}).click();await page.getByRole('button',{name:'Добавить объект',exact:true}).click()
   await page.evaluate(()=>{localStorage.setItem('analysis-motion','off');localStorage.setItem('review-unrelated-preference','preserve')});await page.goto(base+`/projects/${A}/new`);await page.locator('#images').setInputFiles(root+'/project-dashboard/web/public/demo/Screenshot_23.jpg');await page.locator('#cloud-consent').check();await page.locator('#submit-action').click();await page.getByRole('button',{name:'Повторить отправку',exact:true}).waitFor()
   const before=await page.evaluate(async()=>{const pending=JSON.parse(sessionStorage.getItem('observation-pending'));await new Promise((resolve,reject)=>{const open=indexedDB.open('observation-recovery',1);open.onupgradeneeded=()=>open.result.createObjectStore('requests');open.onsuccess=()=>{const db=open.result,tx=db.transaction('requests','readwrite');tx.objectStore('requests').put(pending,pending.key);tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error)}});sessionStorage.removeItem('observation-pending');sessionStorage.setItem('observation-pending-id',pending.key);return{pending:true,annotationKeys:Object.keys(localStorage).filter(key=>key.startsWith('annotation:')),databases:(await indexedDB.databases()).map(db=>db.name)}})
   assert(before.annotationKeys.length>0);assert(before.databases.includes('observation-recovery'));await page.reload();await page.getByRole('button',{name:'Повторить отправку',exact:true}).waitFor()
   await page.locator('.demo-panel summary').click();await page.locator('.demo-panel').getByRole('button',{name:'Загрузка',exact:true}).click();await page.waitForURL(base+`/projects/${A}/new`);await page.waitForFunction(()=>!sessionStorage.getItem('observation-pending-id'));await page.waitForTimeout(200)
   const after=await page.evaluate(async()=>({pending:sessionStorage.getItem('observation-pending'),pointer:sessionStorage.getItem('observation-pending-id'),annotations:Object.keys(localStorage).filter(key=>key.startsWith('annotation:')),databases:(await indexedDB.databases()).map(db=>db.name),motion:localStorage.getItem('analysis-motion'),unrelated:localStorage.getItem('review-unrelated-preference')}))
   assert.equal(after.pending,null);assert.equal(after.pointer,null);assert.deepEqual(after.annotations,[]);assert(!after.databases.includes('observation-recovery'));assert.equal(after.motion,'off');assert.equal(after.unrelated,'preserve');assert.equal(await page.getByRole('button',{name:'Повторить отправку',exact:true}).count(),0);await page.getByRole('button',{name:'Запустить анализ',exact:true}).waitFor();return{before,after,destination:page.url()}
 })
 if(name==='3d-experience')await check('3d actual column transforms change while active and stop offscreen/disabled',async()=>{
   await page.emulateMedia({reducedMotion:'no-preference'});await page.evaluate(()=>localStorage.setItem('analysis-motion','on'));await page.setViewportSize({width:1440,height:500});await page.goto(base+'/');await page.locator('.marquee-scene[data-moving=true]').waitFor()
   const sample=()=>page.locator('.marquee-column').evaluateAll(elements=>elements.map(e=>getComputedStyle(e).transform));const moving1=await sample();await page.waitForTimeout(550);const moving2=await sample();assert.notDeepEqual(moving1,moving2)
   await page.locator('.demo-panel').scrollIntoViewIfNeeded();await page.locator('.marquee-scene[data-moving=false]').waitFor();await page.waitForTimeout(100);const off1=await sample();await page.waitForTimeout(450);const off2=await sample();assert.deepEqual(off1,off2)
   await page.locator('.more-menu>summary').click();await page.locator('.motion-toggle').click();await page.locator('.more-menu>summary').click();await page.locator('.marquee-scene').scrollIntoViewIfNeeded();await page.waitForTimeout(100);const disabled1=await sample();await page.waitForTimeout(450);const disabled2=await sample();assert.deepEqual(disabled1,disabled2);return{moving1,moving2,off1,off2,disabled1,disabled2}
 })
 await context.request.post(base+'/api/__demo/state',{data:{state:'result'}});await context.close()
}}finally{await browser.close();await writeFile(out+'/report.json',JSON.stringify({checks,targets,coverage:'Targets measured in both dimensions include fields, checkbox/radio labels, file labels, summary/buttons and navigation; inline links and geometry controls are enumerated exceptions.'},null,2));console.log(JSON.stringify({checks:checks.length,failures:checks.filter(c=>c.status==='fail')},null,2));if(checks.some(c=>c.status==='fail'))process.exitCode=1}
