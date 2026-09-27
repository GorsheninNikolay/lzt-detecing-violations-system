import { createRequire } from 'node:module'
import { writeFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
const require=createRequire(process.env.PLAYWRIGHT_PACKAGE||'/private/tmp/lzt-design-experiment/tooling/package.json')
const {chromium}=require('playwright-core')
const root='/private/tmp/lzt-design-experiment',A='11111111-1111-4111-8111-111111111111',R='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/private/tmp/lzt-video-browsers/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell'})
const checks=[]
try{for(const[variant,port,scene,path]of[['project-dashboard',5174,'upload',`/projects/${A}/new`],['photo-workspace',5175,'result',`/projects/${A}/runs/${R}`],['3d-experience',5176,'signals',`/projects/${A}/signals`]]){
 const context=await browser.newContext({viewport:{width:390,height:1000},reducedMotion:'reduce'});await context.addInitScript(()=>localStorage.setItem('construction-onboarding','skipped'))
 const base=`http://127.0.0.1:${port}`;await context.request.post(base+'/api/__demo/state',{data:{state:'result'}})
 const page=await context.newPage();await page.goto(base+path);await page.locator('main h1').waitFor();await page.locator('.demo-panel').waitFor();await page.evaluate(()=>document.fonts.ready)
 await page.evaluate(()=>{const sizes=[...document.querySelectorAll('body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const[e,size]of sizes)e.style.fontSize=`${size*2}px`})
 const measured=await page.locator('.bottom-nav').evaluate(nav=>{
  const rect=r=>({left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height})
  const links=[...nav.querySelectorAll('a')].map(a=>{const range=document.createRange();range.selectNodeContents(a);return{text:a.textContent,box:rect(a.getBoundingClientRect()),textRects:[...range.getClientRects()].map(rect)}})
  const intersects=(a,b)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1
  const overlaps=[];for(let i=0;i<links.length;i++)for(let j=i+1;j<links.length;j++)if(links[i].textRects.some(a=>links[j].textRects.some(b=>intersects(a,b))))overlaps.push([links[i].text,links[j].text])
  return{position:getComputedStyle(nav).position,links,overlaps,overflow:document.documentElement.scrollWidth>innerWidth+2}
 })
 assert.equal(measured.position,'static');assert.deepEqual(measured.overlaps,[]);assert.equal(measured.overflow,false)
 for(const link of measured.links){assert(link.box.width>=44&&link.box.height>=44);for(const r of link.textRects){assert(r.left>=link.box.left-1&&r.right<=link.box.right+1)}}
 await page.screenshot({path:`${root}/evidence/confirmation/${variant}-text200-${scene}-390.png`,fullPage:true})
 await page.locator('.bottom-nav a').first().focus();await page.keyboard.press('Tab');const focused=await page.evaluate(()=>{const e=document.activeElement,r=e.getBoundingClientRect();const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return{outline:getComputedStyle(e).outlineStyle,reachable:e===hit||e.contains(hit)}});assert.equal(focused.reachable,true);assert.notEqual(focused.outline,'none')
 checks.push({variant,state:'200% text at 390px',status:'pass',...measured,focused});await context.close()
}}catch(error){checks.push({status:'fail',error:error.message});process.exitCode=1}finally{await browser.close();await writeFile(`${root}/evidence/navigation-text200-checks.json`,JSON.stringify(checks,null,2));console.log(JSON.stringify(checks.map(({variant,status,error,overlaps})=>({variant,status,error,overlaps})),null,2))}
