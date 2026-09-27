import { createRequire } from 'node:module'
import { mkdir, writeFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
const require = createRequire(process.env.PLAYWRIGHT_PACKAGE || '/private/tmp/lzt-design-experiment/tooling/package.json')
const { chromium } = require('playwright-core')
const root = '/private/tmp/lzt-design-experiment'
const pass = process.env.VISUAL_PASS || 'initial'
const out = `${root}/evidence/${pass}`
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/private/tmp/lzt-video-browsers/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell' })
const A = '11111111-1111-4111-8111-111111111111', R = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
const report = { checks: [], screenshots: [], layout: [], failures: [] }
async function check(name, fn) { try { const detail = await fn(); report.checks.push({ name, status: 'pass', detail }) } catch (error) { report.failures.push({ name, message: error.message }); console.log('FAIL', name, error.message.slice(0, 300)) } }
async function audit(page, label) {
  const details = await page.evaluate(() => {
    const visible = e => { const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none' }
    const overflow = document.documentElement.scrollWidth > innerWidth + 2
    const wide = [...document.querySelectorAll('main *,.topbar *')].filter(visible).filter(e => { const r=e.getBoundingClientRect();return r.right>innerWidth+2||r.left < -2 }).slice(0,12).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,60),width:e.getBoundingClientRect().width}))
    const small = [...document.querySelectorAll('button,select,a.primary,summary')].filter(visible).filter(e=>!e.matches('.object-box,.annotation-box,.annotation-resize,.resize-handle')).filter(e=>e.getBoundingClientRect().height<43).map(e=>({text:e.textContent.slice(0,60),height:e.getBoundingClientRect().height}))
    const luminance = rgb => rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0)
    const color = css => css.match(/[\d.]+/g)?.map(Number)
    const contrast = []
    for(const e of document.querySelectorAll('h1,h2,p,label,button,summary,a')) {
      if(!visible(e)||!e.textContent.trim()||e.matches('[disabled]')||e.closest('[aria-hidden=true]'))continue
      const s=getComputedStyle(e),fg=color(s.color);let el=e,bg
      while(el){const c=color(getComputedStyle(el).backgroundColor);if(c&&(c.length===3||c[3]===1)){bg=c;break}el=el.parentElement}
      if(!bg||!fg)continue
      const l=[luminance(fg),luminance(bg)].sort((a,b)=>b-a), ratio=(l[0]+.05)/(l[1]+.05), large=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&Number(s.fontWeight)>=700)
      if(ratio<(large?3:4.5)-.05)contrast.push({text:e.textContent.slice(0,55),ratio:Math.round(ratio*100)/100,fg:s.color,bg})
    }
    return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,overflow,wide,small,contrast:contrast.slice(0,15)}
  })
  report.layout.push({ label,...details })
}
async function shot(page, label) { await page.screenshot({path:`${out}/${label}.png`,fullPage:true});report.screenshots.push(`${label}.png`);await audit(page,label) }
try {
for(const [variant,port] of [['project-dashboard',5174],['photo-workspace',5175],['3d-experience',5176]]) {
  if(process.env.VARIANTS && !process.env.VARIANTS.split(',').includes(variant)) continue
  const base=`http://127.0.0.1:${port}`
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'})
  await context.addInitScript(()=>localStorage.setItem('construction-onboarding','skipped'))
  const page=await context.newPage();page.setDefaultTimeout(12000)
  const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message))
  async function reset(state){const response=await context.request.post(base+'/api/__demo/state',{data:{state}});assert.equal(response.status(),200)}
  async function go(path){await page.goto(base+path);await page.locator('main h1').first().waitFor();await page.locator('.demo-panel').waitFor();await page.waitForTimeout(180);await page.evaluate(()=>document.fonts.ready)}
  await reset('result')
  await check(`${variant}: unknown API stays explicit`,async()=>{assert.equal((await context.request.get(base+'/api/unknown-sentinel')).status(),404)})
  for(const width of [320,390,768,1440]) {
    await page.setViewportSize({width,height:1000})
    for(const [scene,path] of [['projects','/'],['overview',`/projects/${A}`],['upload',`/projects/${A}/new`],['result',`/projects/${A}/runs/${R}`],['signals',`/projects/${A}/signals`],['plan',`/projects/${A}/plan`]]) {
      await go(path)
      if(scene==='result'||scene==='signals')await page.locator('.source-image img').first().waitFor()
      await shot(page,`${variant}-${scene}-${width}`)
    }
    for(const [state,path] of [['empty','/'],['error',`/projects/${A}/runs/${R}`],['analyzing',`/projects/${A}/runs/${R}`],['recovery',`/projects/${A}/new`]]) {await reset(state);await go(path);await shot(page,`${variant}-${state}-${width}`)}
    await reset('result')
  }
  await page.setViewportSize({width:390,height:1000})
  await go(`/projects/${A}/runs/${R}`)
  await check(`${variant}: selection links box and object`,async()=>{await page.getByRole('button',{name:'Объект 1: Экскаватор',exact:true}).click();assert.equal(await page.getByRole('button',{name:'1. Экскаватор',exact:true}).getAttribute('aria-pressed'),'true')})
  if(variant==='photo-workspace')await check('photo: mobile evidence switch',async()=>{await page.getByRole('button',{name:'Основание',exact:true}).click();assert.equal(await page.locator('.result-basis').isVisible(),true);assert.equal(await page.locator('.object-list').isVisible(),false);await page.getByRole('button',{name:'Объекты',exact:true}).click()})
  await check(`${variant}: evidence viewer keyboard and return focus`,async()=>{await page.getByRole('button',{name:'Открыть кадр 1',exact:true}).click();await page.getByRole('dialog').waitFor();const zoomButtons=await page.getByRole('dialog').getByRole('button').allTextContents();report.checks.push({name:variant+': viewer controls',status:'info',buttons:zoomButtons});await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Открыть кадр 1')})
  await check(`${variant}: correction and confirmation`,async()=>{await page.getByText('Исправить разметку',{exact:true}).click();await page.locator('.annotation-canvas img').waitFor();await page.locator('.annotation-editor').getByRole('button',{name:'Добавить объект',exact:true}).click();await page.locator('.annotation-editor').getByRole('button',{name:'Отменить',exact:true}).click();await page.locator('.annotation-editor').getByRole('button',{name:'Повторить правку',exact:true}).click();await page.locator('.annotation-editor').getByRole('button',{name:'Отправить поправки на проверку',exact:true}).click();await page.getByText('Поправки отправлены на проверку. Исходный анализ не изменён.',{exact:true}).waitFor();await shot(page,`${variant}-editor-390`);const buttons=await page.locator('.annotation-editor button').allTextContents();report.checks.push({name:variant+': editor controls',buttons,status:'info'});await page.getByRole('button',{name:'Вернуться к результату',exact:true}).click();await page.locator('#stage-comment').fill('Проверено на демонстрационном наборе');await page.getByRole('button',{name:'Подтвердить этап',exact:true}).click();await page.getByText('Человек подтвердил этап',{exact:false}).waitFor()})
  await go(`/projects/${A}/signals`)
  await check(`${variant}: human signal workflow`,async()=>{await page.locator('[id^=signal-comment-]').fill('Проверено по исходным фотографиям');await page.locator('[id^=signal-state-]').selectOption('in_progress');await page.getByRole('button',{name:'Сохранить',exact:true}).click();await page.waitForTimeout(200);const payload=await(await context.request.get(base+`/api/signals?project_id=${A}`)).json();assert.equal(payload.signals[0].state,'in_progress')})
  await reset('empty');await go('/')
  const longName='Многофункциональный жилой комплекс «Береговой — строительство инженерных сетей и благоустройство территории второй очереди»'
  await check(`${variant}: create project and upload preserves ownership`,async()=>{
    await page.locator('#project-name').fill(longName);await page.locator('form.project-create button').click();await page.getByRole('heading',{name:longName,exact:true}).waitFor();const projectId=new URL(page.url()).pathname.split('/')[2]
    await shot(page,`${variant}-long-project-390`)
    await page.getByRole('link',{name:'Загрузить фотографии',exact:true}).click();await page.locator('#images').setInputFiles(`${root}/project-dashboard/web/public/demo/Screenshot_23.jpg`);if(await page.locator('#area').count())await page.locator('#area').fill('Котлован · участок 1');if(await page.locator('#scenario').count())await page.locator('#scenario').fill('Наблюдение за техникой');await page.locator('#cloud-consent').check();await page.locator('#submit-action').click();await page.getByRole('heading',{name:'Только наблюдения',exact:true}).waitFor({timeout:20000});const id=new URL(page.url()).pathname.split('/').pop();const data=await(await context.request.get(base+'/api/runs/'+id)).json();assert.equal(data.project_id,projectId);assert.equal(data.inputs.length,1);assert.equal(data.state,'succeeded')
  })
  await reset('recovery');await go(`/projects/${A}/new`)
  await check(`${variant}: retained upload after recoverable failure`,async()=>{
    await page.locator('#images').setInputFiles(`${root}/project-dashboard/web/public/demo/Screenshot_23.jpg`);if(await page.locator('#area').count())await page.locator('#area').fill('Котлован · восстановление');if(await page.locator('#scenario').count())await page.locator('#scenario').fill('Наблюдение за техникой');await page.locator('#cloud-consent').check();await page.locator('#submit-action').click();await page.getByRole('button',{name:'Повторить отправку',exact:true}).waitFor();await shot(page,`${variant}-recovery-pending-390`);await page.getByRole('button',{name:'Повторить отправку',exact:true}).click();await page.getByRole('heading',{name:'Только наблюдения',exact:true}).waitFor({timeout:20000})
  })
  await reset('result');await go(`/projects/${A}/runs/${R}`)
  await check(`${variant}: working image has no decorative transform`,async()=>{const transformed=await page.locator('.result-feature-image img').evaluate(e=>{let n=e;const result=[];while(n){const s=getComputedStyle(n);if(s.transform!=='none'||s.perspective!=='none')result.push(n.className);n=n.parentElement}return result});assert.deepEqual(transformed,[])})
  for(const width of [390,1440])for(const [scene,path] of [['result',`/projects/${A}/runs/${R}`],['upload',`/projects/${A}/new`],['signals',`/projects/${A}/signals`]]){await page.setViewportSize({width,height:1000});await go(path);await page.evaluate(()=>{const items=[...document.querySelectorAll('body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const[e,size]of items)e.style.fontSize=`${size*2}px`});await shot(page,`${variant}-text200-${scene}-${width}`)}
  await go('/');await page.keyboard.press('Tab');await check(`${variant}: keyboard focus visible`,async()=>{const focused=await page.evaluate(()=>({text:document.activeElement.textContent,outline:getComputedStyle(document.activeElement).outlineStyle}));assert.notEqual(focused.outline,'none');return focused})
  await page.emulateMedia({reducedMotion:'reduce'});await check(`${variant}: OS motion preference`,async()=>assert.equal(await page.locator('html').getAttribute('data-motion'),'off'))
  await page.emulateMedia({reducedMotion:'no-preference'});await page.reload();await page.locator('.more-menu>summary').click();await page.locator('.motion-toggle').click();await page.reload();await check(`${variant}: persistent motion disable`,async()=>assert.equal(await page.locator('html').getAttribute('data-motion'),'off'))
  if(variant==='3d-experience'){await page.evaluate(()=>localStorage.setItem('analysis-motion','on'));await page.reload();await page.waitForTimeout(300);await page.setViewportSize({width:1440,height:400});await page.locator('.demo-panel').scrollIntoViewIfNeeded();await page.waitForTimeout(150);await check('3d: marquee pauses offscreen',async()=>assert.equal(await page.locator('.marquee-scene').getAttribute('data-moving'),'false'))}
  await check(`${variant}: no uncaught JS errors`,async()=>assert.deepEqual(pageErrors,[]))
  await reset('result');await context.close()
}
} finally {await browser.close();await writeFile(`${out}/report${process.env.VARIANTS ? '-'+process.env.VARIANTS.replaceAll(',','-') : ''}.json`,JSON.stringify(report,null,2));if(report.failures.length || report.layout.some(item=>item.overflow||item.small.length||item.contrast.length))process.exitCode=1;console.log(JSON.stringify({checks:report.checks.length,failures:report.failures.length,screenshots:report.screenshots.length,overflow:report.layout.filter(x=>x.overflow).map(x=>x.label)},null,2))}
