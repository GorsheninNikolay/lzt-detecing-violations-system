const { chromium } = require('/opt/homebrew/lib/node_modules/omniroute/node_modules/playwright');
const { spawnSync } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const base = 'http://127.0.0.1:15174';
const secret = randomBytes(24).toString('base64url');
const runTag = randomBytes(4).toString('hex');
const configure = spawnSync(path.join(root,'backend/.venv/bin/python'), ['-c', `import sys,os\nfrom sqlalchemy import create_engine,text\nfrom app.application.admin_password import hash_password\ne=create_engine(os.environ['TEST_DATABASE_URL'])\nwith e.begin() as c:\n c.execute(text("INSERT INTO admin_credentials VALUES ('gorshenin-nik',:hash) ON CONFLICT(login) DO UPDATE SET password_hash=excluded.password_hash"),{'hash':hash_password(sys.stdin.read())})\n c.execute(text('DELETE FROM admin_sessions'))\n c.execute(text("DELETE FROM request_limits WHERE scope IN ('login','feedback')"))`], { cwd:path.join(root,'backend'), env:{...process.env,TEST_DATABASE_URL:'postgresql+psycopg://evidence:evidence-local@127.0.0.1:55432/onboarding_test_20260926'}, input:secret, encoding:'utf8' });
if (configure.status !== 0) throw new Error('Test admin provisioning failed');
(async () => {
 const browser = await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const checks=[]; const check=(name,value)=>{assert(value,name);checks.push({name,passed:true});console.log(name)};
 const requests=[];
 try {
  for (const [device,viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]) {
   const context=await browser.newContext({viewport}); const page=await context.newPage(); const errors=[]; page.setDefaultTimeout(10000);
   page.on('pageerror',error=>errors.push(error.message)); let loseFeedback=false;
   await context.route('**/api/**',async route=>{
    try {
     const req=route.request(); const url=req.url().replace(`${base}/api`,'http://127.0.0.1:18010');
     const response=await context.request.fetch(url,{method:req.method(),data:req.postDataBuffer()??undefined,headers:{...req.headers(),host:'127.0.0.1:15174'}});
     if (req.url().endsWith('/api/feedback')) { requests.push({body:req.postData(),key:req.headers()['idempotency-key']}); if(loseFeedback){loseFeedback=false;await route.abort();return;} }
     await route.fulfill({response});
    } catch { await route.abort().catch(()=>{}); }
   });
   await page.goto(base+'/?omit=private');
   await page.getByRole('dialog').waitFor();
   check(`${device}: first safe visit opens wizard`,await page.getByText('Шаг 1 из 5').isVisible());
   await page.screenshot({path:path.join(__dirname,`${device}-onboarding.png`),fullPage:true});
   await page.keyboard.press('Escape');
   await page.reload();
   await page.getByRole('heading',{name:'Проекты',exact:true}).waitFor();
   check(`${device}: skip persists on reload`,await page.getByRole('dialog').count()===0);
   const help=page.getByRole('button',{name:'Как пользоваться'});
   await help.focus();await page.keyboard.press('Enter');
   for(let i=0;i<4;i++) {
    await page.getByRole('button',{name:'Далее',exact:true}).click();
    const target=await page.locator('.tour-spotlight').boundingBox(),tip=await page.locator('.tour-tooltip').boundingBox();
    check(`${device}: anchored step ${i+2} stays in viewport`,tip.x>=0&&tip.y>=0&&tip.x+tip.width<=viewport.width+1&&tip.y+tip.height<=viewport.height+1);
    check(`${device}: anchored step ${i+2} avoids spotlight`,tip.x+tip.width<=target.x||target.x+target.width<=tip.x||tip.y+tip.height<=target.y||target.y+target.height<=tip.y);
    if(i===1)await page.screenshot({path:path.join(__dirname,`${device}-tour-prerequisite.png`),fullPage:true});
   }
   await page.getByRole('button',{name:'Назад',exact:true}).click();
   check(`${device}: back reaches step four`,await page.getByText('Шаг 4 из 5').isVisible());
   await page.keyboard.press('Escape');
   check(`${device}: Escape restores focus`,await help.evaluate(el=>el===document.activeElement));
   await page.getByRole('button',{name:'Обратная связь',exact:true}).click();
   await page.getByLabel('Категория',{exact:true}).selectOption('idea');
   const message=`Headless ${device} durable feedback ${runTag}`;
   await page.getByLabel('Сообщение',{exact:true}).fill(message);
   await page.getByLabel('Изображения',{exact:true}).setInputFiles({name:'illustration.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGNsYGhgwAaYsIoOWgkAzQgBEJwaof4AAAAASUVORK5CYII=','base64')});
   await page.getByRole('img',{name:'illustration.png',exact:true}).waitFor();
   await page.waitForTimeout(150);
   await page.screenshot({path:path.join(__dirname,`${device}-feedback.png`),fullPage:true});
   await page.reload();
   await page.getByRole('button',{name:'Обратная связь',exact:true}).click();
   await page.getByRole('img',{name:'illustration.png',exact:true}).waitFor();
   check(`${device}: reload preserves feedback text and picture`,await page.getByLabel('Сообщение',{exact:true}).inputValue()===message);
   const tab=await context.newPage();
   await tab.goto(base);
   check(`${device}: browser identity shared by tabs`,await tab.evaluate(()=>localStorage.getItem('construction-browser'))===await page.evaluate(()=>localStorage.getItem('construction-browser')));
   await tab.getByRole('button',{name:'Обратная связь',exact:true}).click();
   await tab.getByLabel('Сообщение',{exact:true}).waitFor();
   check(`${device}: second tab has independent draft`,await tab.getByLabel('Сообщение',{exact:true}).inputValue()==='');
   await tab.close();
   await page.getByLabel('Приложить контекст').uncheck();
   loseFeedback=true;
   await page.getByRole('button',{name:'Отправить отзыв',exact:true}).click();
   await page.getByRole('alert').waitFor();
   await page.reload();
   await page.getByRole('button',{name:'Обратная связь',exact:true}).click();
   await page.getByRole('button',{name:'Повторить отправку',exact:true}).click();
   await page.getByText('Спасибо, отзыв сохранён',{exact:true}).waitFor();
   const sent=requests.slice(-2);
   check(`${device}: lost-response retry preserves exact body and key`,sent.length===2&&sent[0].body===sent[1].body&&sent[0].key===sent[1].key);
   check(`${device}: optional context omitted`,Object.keys(JSON.parse(sent[0].body).context).length===0);
   await page.getByRole('button',{name:'Закрыть',exact:true}).click();
   check(`${device}: public layout has no horizontal overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.goto(base+'/admin');
   await page.getByRole('heading',{name:'Вход владельца',exact:true}).waitFor();
   check(`${device}: admin excludes public onboarding`,await page.getByRole('button',{name:'Как пользоваться'}).count()===0);
   await page.getByLabel('Пароль',{exact:true}).fill(secret);
   await page.getByRole('button',{name:'Войти',exact:true}).click();
   await page.getByRole('heading',{name:'По дням',exact:true}).waitFor();
   await page.screenshot({path:path.join(__dirname,`${device}-admin-overview.png`),fullPage:true});
   check(`${device}: admin layout has no horizontal overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.getByRole('button',{name:'Обратная связь',exact:true}).click();
   await page.getByRole('button').filter({hasText:message}).click();
   await page.locator('.feedback-detail').waitFor();
   const image=page.locator('.feedback-detail img'); await image.waitFor();
   check(`${device}: private stored feedback image loads`,await image.evaluate(el=>el.complete&&el.naturalWidth>0));
   await page.screenshot({path:path.join(__dirname,`${device}-admin-feedback.png`),fullPage:true});
   await page.getByRole('button',{name:'Выйти',exact:true}).click();
   await page.getByRole('heading',{name:'Вход владельца',exact:true}).waitFor();
   check(`${device}: no uncaught browser errors`,errors.length===0);
   await context.close();
  }
  fs.writeFileSync(path.join(__dirname,'headless.json'),JSON.stringify({checks},null,2));
  console.log(`${checks.length} headless checks passed`);
 } finally { await browser.close(); }
})().catch(error=>{console.error(error.message);process.exitCode=1});
