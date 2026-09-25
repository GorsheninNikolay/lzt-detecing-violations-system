import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readFile, writeFile } from 'node:fs/promises'

const evidenceDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(evidenceDir, '../../..')
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const playwrightPath = process.env.PLAYWRIGHT_MODULE || '/opt/homebrew/lib/node_modules/omniroute/node_modules/playwright'
const { chromium } = createRequire(import.meta.url)(playwrightPath)
const port = 4187
const baseUrl = `http://127.0.0.1:${port}`
const runId = '12345678-1234-1234-1234-123456789abc'
const imageNames = ['Screenshot_23.jpg', 'Screenshot_25.jpg', 'Screenshot_26.jpg']
const images = await Promise.all(imageNames.map(name => readFile(resolve(root, 'web/public/demo', name))))
const report = { generatedAt: new Date().toISOString(), scope: 'Production Vite build rendered in headless Chromium with local API fixtures and bundled demonstration JPEGs.', browser: '', checks: [], screens: [], cssZoom: [], errors: [] }
let server
let browser

const success = (name, pass, detail = {}) => report.checks.push({ name, pass: Boolean(pass), detail })
const json = body => ({ status: 200, contentType: 'application/json', headers: { 'cache-control': 'no-store' }, body: JSON.stringify(body) })
const signalId = index => `signal-${index + 1}`
const signals = Array.from({ length: 25 }, (_, index) => ({
  id: signalId(index), run_id: index === 1 ? null : runId, zone_id: 'zone-1', revision_id: 'revision-3', work_entry_id: 'work-1',
  kind: index === 1 ? 'completion_unconfirmed' : 'expected_equipment_missing',
  state: index === 2 ? 'closed' : index === 3 ? 'in_progress' : 'new',
  basis: index === 1 ? { due_at: '2026-09-23T18:00:00+03:00' } : { class_name: 'dump_truck', reason: 'Expected equipment was not detected in the assessable series.', recommendation: 'Check completion with the site team.', supporting_input_ids: ['input-0', 'input-1', 'input-2'] },
  comment: '', created_at: `2026-09-${String(24 - Math.min(index, 20)).padStart(2, '0')}T12:00:00+03:00`,
  project_name: 'Жилой комплекс «Северный»', zone_name: 'Котлован, северный сектор', plan_revision_number: 3, work_title: 'Разработка грунта',
  preview: index === 1 ? null : { input_id: 'input-0', ordinal: 0, artifact_id: 'source-0' },
}))
const plan = {
  revision_id: 'revision-3', revision_number: 3,
  entries: [{ id: 'work-1', starts_at: '2026-09-23T08:00:00+03:00', ends_at: '2026-09-23T18:00:00+03:00', state: 'active', stage_key: 'excavation', expected_equipment: ['excavator', 'dump_truck'], allowed_equipment: [], excluded_equipment: [] }],
}
const rule = { name: 'Демонстрационное правило земляных работ', revision: '1', expectation: 'Экскаватор и самосвал на пригодных кадрах серии', provenance: 'Демонстрационное правило прототипа', recommendation: 'Проверьте ход вывоза грунта с командой площадки.' }
const inputs = imageNames.map((_, index) => ({ input_id: `input-${index}`, ordinal: index, sha256: `fixture-sha-${index}`, artifact_id: `source-${index}` }))
const observations = inputs.flatMap(input => [
  { input_id: input.input_id, ordinal: input.ordinal, class_name: 'excavator', state: 'detected', reason: null, source_artifact_id: input.artifact_id, input_sha256: input.sha256 },
  { input_id: input.input_id, ordinal: input.ordinal, class_name: 'dump_truck', state: 'not_detected_in_frame', reason: null, source_artifact_id: input.artifact_id, input_sha256: input.sha256 },
])
const run = {
  run_id: runId, state: 'succeeded', intent: 'rule_evaluation', stage: 'excavation', created_at: '2026-09-23T12:10:00+03:00',
  context: { period: '2026-09-23T12:00:00+03:00', observation_area: 'Котлован, северный сектор', stage_id: 'excavation' },
  stages: ['input_registration', 'frame_usability', 'equipment_observation', 'series_aggregation', 'rule_evaluation', 'result_projection'].map(name => ({ name, state: 'succeeded' })),
  inputs, observations, requested_classes: ['excavator', 'dump_truck'], outcome: 'check_requested',
  objects: [{ input_id: 'input-0', class_name: 'excavator', score: .92, box: [.16, .20, .55, .79], image_size: [1280, 720], invocation_id: 'fixture-invocation' }],
  result_projection: {
    outcome: 'check_requested', frames: observations,
    context: { period: '2026-09-23T12:00:00+03:00', observation_area: 'Котлован, северный сектор', stage_id: 'excavation' },
    series: { usable_count: 3, usable_input_ids: inputs.map(input => input.input_id), declared_observation_area: 'Котлован, северный сектор', input_order: inputs.map(input => input.input_id), excavator_supporting_input_ids: inputs.map(input => input.input_id), dump_truck_persistence_input_ids: inputs.map(input => input.input_id), dump_truck_persistence_text: 'Самосвал не обнаружен в пригодной серии.' },
    reason: 'Экскаватор обнаружен; самосвал не обнаружен в пригодных кадрах серии.', uncertainty: 'Кадры не подтверждают отсутствие техники на всей площадке.',
    recommendation: rule.recommendation, rule, supporting_input_ids: inputs.map(input => input.input_id),
    stage_hypotheses: [{ stage: 'excavation', equipment: 'excavator', scene_features: ['котлован'] }],
  },
  plan_binding: { zone_id: 'zone-1', revision_id: 'revision-3', capture_times: inputs.map(() => '2026-09-23T12:00:00+03:00') },
}

async function installFixture(context) {
  await context.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path === '/api/analysis-choices') return route.fulfill(json({ stages: [{ id: 'excavation', label: 'Земляные работы котлована', rule }] }))
    if (path === '/api/projects') return route.fulfill(json({ projects: [{ id: 'project-1', name: 'Жилой комплекс «Северный»', timezone: 'Europe/Moscow' }] }))
    if (path === '/api/projects/project-1/zones') return route.fulfill(json({ zones: [{ id: 'zone-1', name: 'Котлован, северный сектор' }] }))
    if (path === '/api/zones/zone-1/plan') return route.fulfill(json(plan))
    if (path === `/api/runs/${runId}`) return route.fulfill(json(run))
    if (path === '/api/runs') return route.fulfill(json({ runs: [{ id: runId, created_at: run.created_at, stage: 'excavation', intent: run.intent, state: run.state, outcome: run.outcome }], next_offset: null }))
    if (path === '/api/stages/summary') return route.fulfill(json({ stages: [{ stage_id: 'excavation', name: 'Земляные работы котлована', supported: true, latest_result: { run_id: runId, created_at: run.created_at, projection: { outcome: run.outcome } }, latest_lifecycle: { run_id: runId, created_at: run.created_at, state: run.state } }] }))
    if (path === '/api/catalog/works') return route.fulfill(json({ works: [{ id: 'catalog-1', source_row: 1, code: '01', title: 'Разработка грунта' }] }))
    if (path === '/api/readiness' || path === '/api/provider-comparison') return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
    if (path === '/api/signals') {
      const filtered = url.searchParams.get('state') ? signals.filter(signal => signal.state === url.searchParams.get('state')) : signals
      return route.fulfill(json({ new_count: signals.filter(signal => signal.state === 'new').length, signals: filtered }))
    }
    const artifact = path.match(new RegExp(`^/api/runs/${runId}/artifacts/source-(\\d+)$`))
    if (artifact) return route.fulfill({ status: 200, contentType: 'image/jpeg', headers: { 'cache-control': 'no-store' }, body: images[Number(artifact[1])] })
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ code: 'fixture_route_not_found' }) })
  })
}

async function waitForServer() {
  const deadline = Date.now() + 30000
  while (Date.now() < deadline) {
    if (server.exitCode !== null) throw new Error(`Preview exited with ${server.exitCode}: ${server.output}`)
    try { if ((await fetch(baseUrl)).ok) return } catch { /* Wait for preview. */ }
    await new Promise(resolveDelay => setTimeout(resolveDelay, 150))
  }
  throw new Error(`Preview did not start: ${server.output}`)
}

async function metrics(page) {
  return page.evaluate(() => ({
    viewport: { width: innerWidth, height: innerHeight, pixelRatio: devicePixelRatio },
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
    documentHeight: document.documentElement.scrollHeight,
    title: document.querySelector('main h1')?.textContent?.trim() ?? null,
    font: getComputedStyle(document.body).fontFamily,
    uiFont: getComputedStyle(document.querySelector('.radix-themes')).fontFamily,
    headingFont: getComputedStyle(document.querySelector('main h1')).fontFamily,
    fontFaces: [...document.fonts].filter(face => face.family === 'Onest').map(face => ({ status: face.status, weight: face.weight, unicodeRange: face.unicodeRange })),
    cyrillicFontReady: document.fonts.check('16px Onest', 'Новый анализ'),
    bottomNavVisible: getComputedStyle(document.querySelector('.bottom-nav')).display !== 'none',
  }))
}

async function openScreen(page, screen) {
  const path = screen === 'new' ? '/new' : screen === 'result' ? `/runs/${runId}` : '/signals'
  await page.goto(baseUrl + path, { waitUntil: 'networkidle' })
  if (screen === 'new') {
    await page.locator('#images').setInputFiles(imageNames.map(name => resolve(root, 'web/public/demo', name)))
    await page.locator('.frame-preview').first().waitFor()
    await page.waitForFunction(() => [...document.querySelectorAll('.frame-preview')].every(image => image.complete && image.naturalWidth > 0))
  } else if (screen === 'result') {
    await page.getByRole('heading', { name: 'Рекомендована проверка человеком' }).waitFor()
    await page.waitForFunction(() => [...document.querySelectorAll('.result-feature-image img,.source-thumbnail img')].every(image => image.complete && image.naturalWidth > 0))
  } else {
    await page.getByRole('heading', { name: 'Сигналы', exact: true }).waitFor()
    await page.locator('.signals-row').first().waitFor()
    await page.waitForFunction(() => document.querySelector('.signals-preview img')?.naturalWidth > 0)
  }
  await page.evaluate(() => document.fonts.ready)
}

async function capture(screen, width, height, pixelRatio = 1) {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: pixelRatio, reducedMotion: 'reduce' })
  await installFixture(context)
  const page = await context.newPage()
  page.on('pageerror', error => report.errors.push(`${screen} ${width}x${height}: ${error.message}`))
  await openScreen(page, screen)
  const result = await metrics(page)
  const filename = `${screen}-${width}x${height}${pixelRatio > 1 ? '-dsf2' : ''}.png`
  await page.screenshot({ path: resolve(evidenceDir, filename) })
  if (width === 390) await page.screenshot({ path: resolve(evidenceDir, `${screen}-390x844-full.png`), fullPage: true })
  report.screens.push({ screen, filename, ...result })
  success(`${screen} ${width}x${height} horizontal fit`, result.documentWidth <= width + 1 && result.bodyWidth <= width + 1, { documentWidth: result.documentWidth, bodyWidth: result.bodyWidth })
  success(`${screen} ${width}x${height} Onest Cyrillic loaded`, result.cyrillicFontReady, { font: result.font, fontFaces: result.fontFaces })
  success(`${screen} ${width}x${height} nav mode`, result.bottomNavVisible === (width < 768), { bottomNavVisible: result.bottomNavVisible })
  if (screen === 'new') success(`${screen} ${width}x${height} local previews`, await page.locator('.frame-preview').count() === 3)
  if (screen === 'result') success(`${screen} ${width}x${height} source decoded`, await page.locator('.result-feature-image img').evaluate(img => img.naturalWidth > 0))
  if (screen === 'signals') success(`${screen} ${width}x${height} row/detail`, await page.locator('.signals-row').count() === 20 && await page.getByRole('heading', { name: 'Основание' }).count() === 1)
  await context.close()
}

async function captureCssZoom(screen) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' })
  await installFixture(context)
  const page = await context.newPage()
  page.on('pageerror', error => report.errors.push(`${screen} CSS zoom: ${error.message}`))
  await openScreen(page, screen)
  await page.evaluate(() => { document.documentElement.style.zoom = '200%' })
  await page.evaluate(() => new Promise(resolveFrame => requestAnimationFrame(() => requestAnimationFrame(resolveFrame))))
  const result = await metrics(page)
  const filename = `${screen}-css-zoom-200-1280x900.png`
  await page.screenshot({ path: resolve(evidenceDir, filename) })
  report.cssZoom.push({ screen, filename, ...result })
  success(`${screen} CSS zoom 200% horizontal fit`, result.documentWidth <= 1281 && result.bodyWidth <= 1281, { documentWidth: result.documentWidth, bodyWidth: result.bodyWidth })
  await context.close()
}

async function interactionChecks() {
  const formContext = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
  await installFixture(formContext)
  const formPage = await formContext.newPage()
  await openScreen(formPage, 'new')
  success('new form reduced motion disables upload transition', await formPage.locator('.upload-zone').evaluate(node => getComputedStyle(node).transitionDuration.split(',').every(value => parseFloat(value) < .001)))
  for (const selector of ['#scenario', '#area', '#period']) {
    await formPage.locator(selector).click()
    success(`new form ${selector} remains reachable below action panel`, await formPage.locator(selector).evaluate(input => document.activeElement === input))
  }
  await formPage.locator('.frame-actions button[aria-label^="Удалить:"]').last().click()
  success('new form last frame action remains reachable', await formPage.locator('.frame-preview').count() === 2)
  await formContext.close()

  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
  await installFixture(context)
  const page = await context.newPage()
  await openScreen(page, 'result')
  const second = page.getByRole('button', { name: 'Выбрать кадр 2' })
  await second.click()
  success('result frame selection', await second.getAttribute('aria-pressed') === 'true' && await page.locator('.result-frame-caption strong').innerText() === 'Кадр 2')
  const opener = page.getByRole('button', { name: 'Открыть кадр 2' })
  await opener.click()
  success('viewer opens and focuses control', await page.locator('dialog[open]').count() === 1 && await page.evaluate(() => document.activeElement?.closest('dialog') !== null))
  await page.keyboard.press('Escape')
  success('viewer Escape returns focus', await page.locator('dialog[open]').count() === 0 && await opener.evaluate(button => document.activeElement === button))
  const motion = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)
  success('reduced motion preference', motion)
  await page.goto(baseUrl + '/signals', { waitUntil: 'networkidle' })
  await page.locator('.signals-row').first().waitFor()
  success('signals initially capped at 20', await page.locator('.signals-row').count() === 20 && await page.getByRole('button', { name: 'Показать ещё' }).count() === 1)
  await page.getByRole('button', { name: 'Показать ещё' }).click()
  success('signals show remaining rows', await page.locator('.signals-row').count() === 25)
  await page.locator('#signals-filter').selectOption('closed')
  await page.locator('.signals-row').first().waitFor()
  success('signals closed filter', await page.locator('.signals-row').count() === 1 && await page.getByText('Закрыт означает завершение ручной обработки').count() === 1)
  await page.locator('#signals-filter').selectOption('')
  await page.locator('.signals-row').nth(1).click()
  success('calendar signal has no linked frames', await page.getByText('Связанных кадров нет.').count() === 1)
  await context.close()

  const navContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await installFixture(navContext)
  const navPage = await navContext.newPage()
  for (const [path, heading] of [['/', 'Этапы строительства'], ['/analyses', 'История анализов'], ['/plan', 'Проект и план зоны'], ['/about', 'Контроль строительства'], ['/readiness', 'Готовность'], ['/provider-comparison', 'Сравнение провайдеров']]) {
    await navPage.goto(baseUrl + path, { waitUntil: 'networkidle' })
    success(`other route ${path}`, await navPage.getByRole('heading', { name: heading, exact: true }).count() === 1)
  }
  await navPage.goto(baseUrl + '/new', { waitUntil: 'networkidle' })
  const more = navPage.locator('.more-menu summary')
  await more.focus()
  await navPage.keyboard.press('Enter')
  success('More keyboard disclosure', await navPage.locator('.more-menu[open]').count() === 1)
  success('More visible focus', await more.evaluate(node => getComputedStyle(node).outlineStyle !== 'none'))
  await navContext.close()
}

async function captureMockups() {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await context.newPage()
  const mockupDir = resolve(root, '_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/mockups')
  await page.goto(`file://${resolve(mockupDir, 'key-new-analysis.html')}`)
  await page.locator('.device.browser').screenshot({ path: resolve(evidenceDir, 'reference-new-analysis-desktop.png') })
  await page.goto(`file://${resolve(mockupDir, 'key-run-workspace.html')}`)
  await page.locator('.state-block').nth(1).locator('.laptop').screenshot({ path: resolve(evidenceDir, 'reference-result-desktop.png') })
  await context.close()
}

try {
  server = spawn(resolve(root, 'web/node_modules/.bin/vite'), ['preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: resolve(root, 'web'), stdio: ['ignore', 'pipe', 'pipe'] })
  server.output = ''
  server.stdout.on('data', data => { server.output += data.toString() })
  server.stderr.on('data', data => { server.output += data.toString() })
  await waitForServer()
  browser = await chromium.launch({ headless: true, executablePath: chromePath })
  report.browser = browser.version()
  for (const [width, height] of [[1440, 900], [1366, 768], [768, 1024], [390, 844], [320, 844], [640, 900]]) {
    for (const screen of ['new', 'result', 'signals']) await capture(screen, width, height, width === 640 ? 2 : 1)
  }
  for (const screen of ['new', 'result', 'signals']) await captureCssZoom(screen)
  await interactionChecks()
  await captureMockups()
} catch (error) {
  report.errors.push(error.stack || String(error))
} finally {
  if (browser) await browser.close()
  if (server && server.exitCode === null) { server.kill('SIGTERM'); await new Promise(resolveDelay => server.once('exit', resolveDelay)) }
  await writeFile(resolve(evidenceDir, 'measurements.json'), JSON.stringify(report, null, 2) + '\n')
}

const passed = report.checks.filter(check => check.pass).length
const summary = `# Premium frontend headless verification\n\n${passed}/${report.checks.length} checks passed. Browser: headless Chromium ${report.browser}. Screenshots render the production Vite bundle at the named CSS viewports. The 640×900, device-scale-2 pass is a 200% rendered-size equivalent, not browser toolbar zoom.\n\nData comes from local API fixtures; evidence images are bundled JPEGs from \`web/public/demo\`. No live backend, model output, production service, physical device, or GUI app was exercised.\n\n## Findings\n\n${report.checks.filter(check => !check.pass).map(check => `- FAIL: ${check.name} ${JSON.stringify(check.detail)}`).join('\n') || '- All scripted checks passed.'}\n${report.errors.map(error => `- ERROR: ${error}`).join('\n')}\n\nScreenshots and detailed measurements are in this directory.\n`
await writeFile(resolve(evidenceDir, 'automated-summary.md'), summary)
console.log(`${passed}/${report.checks.length} checks passed; ${report.errors.length} errors`)
if (passed !== report.checks.length || report.errors.length) process.exitCode = 1
