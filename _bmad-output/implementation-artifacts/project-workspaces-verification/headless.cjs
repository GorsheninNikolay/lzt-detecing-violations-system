const { chromium } = require('/opt/homebrew/lib/node_modules/omniroute/node_modules/playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const dir = __dirname;
const smoke = JSON.parse(fs.readFileSync(path.join(dir, 'live-smoke.json')));
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const checks = [];
  const check = (name, value) => { assert(value, name); checks.push({ name, passed: true }); };
  try {
    for (const [name, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await context.route('**/api/**', async route => {
        try {
        const request = route.request();
        const response = await context.request.fetch(request.url().replace('http://127.0.0.1:15173/api', 'http://127.0.0.1:18000'), {
          method: request.method(), data: request.postDataBuffer() ?? undefined,
          headers: request.headers(),
        });
        await route.fulfill({ response });
        } catch { await route.abort().catch(() => {}); }
      });
      await page.goto('http://127.0.0.1:15173/');
      await page.getByRole('heading', { name: 'Проекты', exact: true }).waitFor();
      await page.getByRole('link', { name: 'Smoke project A', exact: true }).waitFor();
      await page.keyboard.press('Tab');
      check(`${name} keyboard reaches focusable element`, await page.evaluate(() => document.activeElement !== document.body));
      const tabTo = async locator => {
        for (let step = 0; step < 50; step++) {
          if (await locator.evaluate(element => document.activeElement === element)) return;
          await page.keyboard.press('Tab');
        }
        throw new Error('Keyboard target was unreachable');
      };
      const projectLink = page.getByRole('link', { name: 'Smoke project A', exact: true });
      await tabTo(projectLink);
      check(`${name} keyboard focuses project link`, await projectLink.evaluate(element => document.activeElement === element));
      await page.keyboard.press('Enter');
      await page.getByRole('heading', { name: 'Smoke project A', exact: true }).waitFor();
      await page.getByText('Запланированные работы', { exact: true }).waitFor();
      const switcher = page.getByLabel('Выбрать проект');
      await tabTo(switcher);
      await page.keyboard.press('s');
      await page.getByRole('heading', { name: 'Smoke project B', exact: true }).waitFor();
      check(`${name} keyboard switches project`, await switcher.inputValue() === smoke.projects[1].id);
      await tabTo(switcher);
      await page.keyboard.press('s');
      await page.getByRole('heading', { name: 'Smoke project A', exact: true }).waitFor();
      check(`${name} navigation focuses project heading`, await page.getByRole('heading', { name: 'Smoke project A', exact: true }).evaluate(element => document.activeElement === element));
      await page.screenshot({ path: path.join(dir, `${name}-overview.png`), fullPage: true });
      check(`${name} overview has no horizontal overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.getByRole('link', { name: 'Загрузить фотографии', exact: true }).click();
      await page.getByLabel('Участок', { exact: true }).waitFor({ timeout: 5000 }).catch(async error => { console.log(page.url(), (await page.locator('main').innerText()).slice(0,2500)); throw error; });
      await page.waitForFunction(id => document.querySelector('#analysis-zone')?.value === id, smoke.projects[0].default_zone_id);
      check(`${name} selects default area`, await page.getByLabel('Участок', { exact: true }).inputValue() === smoke.projects[0].default_zone_id);
      await page.getByLabel('Сопоставить с сохранённым планом').waitFor();
      check(`${name} plan comparison opt-in`, !await page.getByLabel('Сопоставить с сохранённым планом').isChecked());
      await page.getByLabel('Выбрать изображение').setInputFiles(path.resolve('web/public/demo/Screenshot_87.jpg'));
      await page.getByLabel('Время съёмки').waitFor();
      const otherTab = await context.newPage();
      await otherTab.goto(`http://127.0.0.1:15173/projects/${smoke.projects[1].id}`);
      await otherTab.getByRole('heading', { name: 'Smoke project B', exact: true }).waitFor();
      check(`${name} tabs retain independent project URLs`, page.url().includes(smoke.projects[0].id) && otherTab.url().includes(smoke.projects[1].id));
      await otherTab.close();
      page.once('dialog', dialog => dialog.dismiss());
      await page.evaluate(() => history.back());
      await page.waitForTimeout(100);
      check(`${name} declined browser Back preserves upload`, page.url().endsWith('/new') && await page.getByLabel('Время съёмки').count() === 1);
      page.once('dialog', dialog => dialog.dismiss());
      await page.getByLabel('Выбрать проект').selectOption(smoke.projects[1].id);
      check(`${name} declined dirty switch keeps original URL`, page.url().includes(smoke.projects[0].id));
      await page.screenshot({ path: path.join(dir, `${name}-upload.png`), fullPage: true });
      page.once('dialog', dialog => dialog.accept());
      await page.getByLabel('Выбрать проект').selectOption(smoke.projects[1].id);
      await page.getByRole('heading', { name: 'Smoke project B', exact: true }).waitFor();
      check(`${name} accepted switch selects other project`, page.url().endsWith(smoke.projects[1].id));
      await page.goto(`http://127.0.0.1:15173/projects/${smoke.projects[1].id}/runs/${smoke.runs[0]}`);
      await page.getByRole('heading', { name: 'Только наблюдения', exact: true }).waitFor();
      check(`${name} server ownership corrects wrong URL`, page.url().includes(smoke.projects[0].id));
      await page.getByText('Этот анализ выполнен без сопоставления с планом. Добавленный позже план не меняет сохранённый результат.').waitFor();
      await page.screenshot({ path: path.join(dir, `${name}-result.png`), fullPage: true });
      check(`${name} result has no horizontal overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      check(`${name} no uncaught browser errors`, errors.length === 0);
      await context.close();
    }
    fs.writeFileSync(path.join(dir, 'headless.json'), JSON.stringify({ scope: 'Headless Chromium against isolated real API; desktop/mobile keyboard and workspace flow, not model quality or deployment evidence', checks }, null, 2) + '\n');
    console.log(JSON.stringify({ passed: checks.length }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
