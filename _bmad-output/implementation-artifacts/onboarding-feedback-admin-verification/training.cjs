const { chromium } = require('/opt/homebrew/lib/node_modules/omniroute/node_modules/playwright');
const base=process.env.TOUR_BASE||'http://127.0.0.1:15174';
const api=process.env.TOUR_API||'http://127.0.0.1:18010';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const replay=process.env.REPLAY_REQUESTS_FILE ? JSON.parse(fs.readFileSync(process.env.REPLAY_REQUESTS_FILE,'utf8')) : null;
 const checks=[],captures=[];const check=(name,condition)=>{assert(condition,name);checks.push({name,passed:true});console.log(name)};
 try {
 for(const [device,viewport]of[['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
  const context=await browser.newContext({viewport});if(replay)await context.addInitScript(value=>sessionStorage.setItem('onboarding-training-request',JSON.stringify(value)),replay.project);const page=await context.newPage();page.setDefaultTimeout(15000);
  const creations=[];let lose=true,submissions=0;
  await context.route('**/api/**',async route=>{
   const req=route.request();
   try{
    if(req.url().includes('/runs/')&&req.method()==='POST')submissions++;
    const response=await context.request.fetch(req.url().replace(base+'/api',api),{method:req.method(),data:req.postDataBuffer()??undefined,headers:{...req.headers(),host:new URL(base).host,...(replay&&req.url().includes('/runs/')&&req.method()==='POST'?{'idempotency-key':replay.runKey}:{})}});
    if(req.url().endsWith('/api/projects')&&req.method()==='POST'){
     creations.push({body:req.postData(),key:req.headers()['idempotency-key'],result:await response.json()});
     if(lose){lose=false;await route.abort();return;}
    }
    await route.fulfill({response});
   }catch{await route.abort().catch(()=>{})}
  });
  await page.goto(base+'/');
  await page.getByRole('button',{name:'Попробовать на примере',exact:true}).click();
  await page.getByRole('alert').waitFor();
  await page.getByRole('button',{name:'Попробовать на примере',exact:true}).click();
  await page.getByText('Screenshot_89.jpg',{exact:true}).waitFor();
  await page.getByText('Учебный проект и проверенная фотография готовы.',{exact:false}).waitFor();
  check(`${device}: training project retry reuses body key and project`,creations.length===2&&creations[0].body===creations[1].body&&creations[0].key===creations[1].key&&creations[0].result.id===creations[1].result.id);
  check(`${device}: separate educational project named`,creations[1].result.name.startsWith('Учебный проект'));
  check(`${device}: single bundled sample staged`,await page.locator('.manifest .frame').count()===1);
  check(`${device}: no automatic inference`,submissions===0);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const target=await page.locator('#submit-action').boundingBox(),spot=await page.locator('.tour-spotlight').boundingBox(),tip=await page.locator('.tour-tooltip').boundingBox();
  check(`${device}: real submit is spotlighted`,Math.abs(spot.x-target.x)<=6&&Math.abs(spot.y-target.y)<=6);
  check(`${device}: sample tooltip avoids submit`,tip.x+tip.width<=spot.x||spot.x+spot.width<=tip.x||tip.y+tip.height<=spot.y||spot.y+spot.height<=tip.y);
  const unobstructed=await page.locator('#submit-action').evaluate(element=>{const box=element.getBoundingClientRect();const hit=document.elementFromPoint(box.x+box.width/2,box.y+box.height/2);return element===hit||element.contains(hit)});
  captures.push({device,state:'ready',target,spot,tip,unobstructed});
  await page.screenshot({path:path.join(__dirname,`${device}-training-ready.png`),fullPage:false});
  check(`${device}: submit is unobstructed at visible center`,unobstructed);
  if(replay || process.env.REAL_INFERENCE==='1') {
   await page.locator('#submit-action').click();
   await page.waitForURL(/\/runs\/[0-9a-f-]{36}$/);
   const runId=page.url().split('/').pop();if(replay)assert.equal(runId,replay.runId);let result;
   for(let attempt=0;attempt<120;attempt++){
    result=await (await context.request.get(api+'/runs/'+runId)).json();
    if(result.state==='succeeded'||result.state==='failed')break;
    await page.waitForTimeout(1000);
   }
   assert.equal(result.state,'succeeded','server-authoritative successful training run');
   check(`${device}: persisted ordinary result ${runId}`,result.purpose==='ordinary'&&result.result_projection?.outcome==='observations_only');
   await page.waitForTimeout(3500);
   check(`${device}: explicit highlighted submit ${replay?'reused persisted successful run':'produced real successful run'}`,submissions===1);
   check(`${device}: tour followed actual persisted result`,await page.getByText('Это ваш реальный учебный анализ.',{exact:false}).isVisible());
   captures.push({device,state:'result',target:await page.locator('#main h1').boundingBox(),spot:await page.locator('.tour-spotlight').boundingBox(),tip:await page.locator('.tour-tooltip').boundingBox()});
   await page.screenshot({path:path.join(__dirname,`${device}-training-result${replay?'-replay':''}.png`),fullPage:false});
  }
  await page.keyboard.press('Escape');
  if(replay){
   await page.locator('.result-basis .observation-rows').scrollIntoViewIfNeeded();
   const widths=await page.locator('.result-basis .observation-row p:last-child').evaluateAll(elements=>elements.map(element=>({paragraph:element.getBoundingClientRect().width,row:element.closest('article').getBoundingClientRect().width})));
   captures.push({device,state:'result-text',widths});
   check(`${device}: equipment descriptions use readable row width`,widths.length>0&&widths.every(item=>item.paragraph>=item.row*.95&&item.paragraph>=160));
   await page.screenshot({path:path.join(__dirname,`${device}-result-without-tour.png`),fullPage:false});
  }
  if(!replay && process.env.REAL_INFERENCE!=='1')check(`${device}: closing tour preserves staged sample`,await page.locator('.manifest .frame').count()===1);
  await context.close();
 }
 fs.writeFileSync(path.join(__dirname,replay?'training-runtime-replay.json':process.env.REAL_INFERENCE==='1'?'training-runtime.json':'training.json'),JSON.stringify({checks,captures},null,2));
 }finally{await browser.close()}
})().catch(error=>{console.error(error.stack || error);process.exitCode=1});
