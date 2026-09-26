const { chromium } = require('/opt/homebrew/lib/node_modules/omniroute/node_modules/playwright');
const fs=require('node:fs'), path=require('node:path');
const out=process.argv[2]||'initial';
const run='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', project='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', zone='cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const uid=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const photo=fs.readFileSync(path.resolve('web/public/demo/Screenshot_87.jpg'));
const inputs=Array.from({length:8},(_,i)=>({input_id:uid(i+10),ordinal:i,sha256:'a'.repeat(64),artifact_id:uid(i+20)}));
const objects=inputs.flatMap((input,i)=>[0,1].map(n=>({id:uid(100+i*2+n),input_id:input.input_id,class_name:'excavator',score:.83,box:n?[.55,.2,.9,.7]:[.1,.3,.45,.8],image_size:[1920,1080],invocation_id:uid(90)})));
const stages=['input_registration','frame_usability','equipment_observation','series_aggregation','rule_evaluation','result_projection'];
const observations=inputs.map(input=>({...input,class_name:'excavator',state:'detected',source_artifact_id:input.artifact_id}));
const completed={run_id:run,project_id:project,purpose:'ordinary',state:'succeeded',stages:stages.map(name=>({name,state:name==='rule_evaluation'?'skipped':'succeeded',reason:name==='rule_evaluation'?'not_applicable':null})),inputs,objects,observations,context:{project_id:project,zone_id:zone,period:'2026-09-26T10:00:00Z',capture_times:inputs.map(()=>'2026-09-26T10:00:00Z')},result_projection:{outcome:'observations_only',frames:observations}};
const proposal={id:uid(200),run_id:run,input_id:inputs[0].input_id,input_sha256:inputs[0].sha256,artifact_id:inputs[0].artifact_id,original_objects:objects.slice(0,2),objects:objects.slice(0,2),revision:1,status:'pending',version_id:uid(201),whole_frame_verified:false,reason:''};

(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 await context.addInitScript(()=>localStorage.setItem('construction-onboarding','completed'));
 let fail=false,requests=0;
 const signal={id:uid(301),zone_id:zone,revision_id:uid(400),plan_revision_number:1,state:'new',kind:'expected_equipment_missing',run_id:run,created_at:'2026-09-26T10:00:00Z',comment:'',basis:{class_name:'dump_truck'},preview:inputs[0]};
 await context.route('**/api/**',route=>{
 const p=new URL(route.request().url()).pathname.replace('/api','');
 if(p.includes('/artifacts/')){requests++;return fail?route.fulfill({status:503,contentType:'application/json',body:'{}'}):route.fulfill({contentType:'image/jpeg',body:photo})}
 const body=p===`/runs/${run}`?completed:p==='/projects'?{projects:[{id:project,name:'Test',timezone:'UTC'}]}:p==='/signals'?{signals:[signal],new_count:1,summary:{open_count:1,attention_count:1,insufficient_data_count:0}}:p.endsWith('/plan')?{revision_id:uid(400),revision_number:1,entries:[]}:{zones:[],runs:[],choices:[]};
 return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto(`http://127.0.0.1:15175/projects/${project}/signals`);
 await page.locator('.signal-photo img').waitFor();fail=true;
 await page.getByRole('button',{name:'Открыть фото',exact:true}).click();
 const retry=page.getByRole('dialog').getByRole('button',{name:'Повторить',exact:true});await retry.waitFor();fail=false;const before=requests;await retry.click();await page.waitForTimeout(300);
 const result={retryRequested:requests>before,imageVisible:await page.getByRole('dialog').locator('img').count()===1};
 console.log(JSON.stringify(result)); if(!result.retryRequested || !result.imageVisible) process.exitCode=1;
 } finally {await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
