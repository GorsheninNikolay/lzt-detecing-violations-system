import { createHash } from 'node:crypto'
import { execFileSync, spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readFile, writeFile } from 'node:fs/promises'

const evidenceDir = dirname(fileURLToPath(import.meta.url))
const projectRoot = resolve(evidenceDir, '../../..')
const runId = '12345678-1234-1234-1234-123456789abc'
const runPath = `/runs/${runId}`
const port = 4179
const baseUrl = `http://127.0.0.1:${port}`
const chromePath = process.env.CHROME_PATH
const playwrightPath = process.env.PLAYWRIGHT_MODULE
const jpegPath = resolve(projectRoot, 'web/public/demo/Screenshot_23.jpg')
const jpegBytes = await readFile(jpegPath)
const jpegSha256 = createHash('sha256').update(jpegBytes).digest('hex')
const jpegDimensions = Object.fromEntries(execFileSync('sips', ['-g', 'pixelWidth', '-g', 'pixelHeight', jpegPath], { encoding: 'utf8' })
  .split('\n').flatMap(line => {
    const match = line.match(/pixel(Width|Height): (\d+)/)
    return match ? [[match[1] === 'Width' ? 'width' : 'height', Number(match[2])]] : []
  }))
const require = createRequire(import.meta.url)
const { chromium } = require(playwrightPath)
const checks = []
const artifactResponses = []
const pageErrors = []
let artifactMode = 'jpeg'
let server
let browser

function check(name, pass, details = {}) {
  checks.push({ name, pass: Boolean(pass), details })
  return Boolean(pass)
}

function targetSelector() {
  return `button, a:not(.skip-link), select, input:not([type=hidden]):not([type=file]):not([type=radio]), textarea, summary, .file-button`
}

async function targetMeasurements(page, scopeSelector) {
  return page.evaluate(({ selector, scopeSelector }) => {
    const scope = document.querySelector(scopeSelector)
    if (!scope) return []
    const describe = element => {
      const rect = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      const label = element.getAttribute('aria-label') || element.innerText || element.labels?.[0]?.innerText || element.id || element.tagName
      return {
        label: label.trim().replace(/\s+/g, ' ').slice(0, 90),
        tag: element.tagName.toLowerCase(),
        width: Math.round(rect.width * 100) / 100,
        height: Math.round(rect.height * 100) / 100,
        left: Math.round(rect.left * 100) / 100,
        right: Math.round(rect.right * 100) / 100,
        visible: style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0,
      }
    }
    const controls = [...scope.querySelectorAll(selector)]
      .filter(element => element.getClientRects().length && !element.closest('.sr-only'))
      .map(describe)
    const radioLabels = [...scope.querySelectorAll('input[type=radio]')]
      .map(input => input.closest('label')).filter(Boolean).map(describe)
    return [...controls, ...radioLabels].filter(target => target.visible)
  }, { selector: targetSelector(), scopeSelector })
}

async function layoutMetrics(page) {
  return page.evaluate(() => ({
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
    documentHeight: document.documentElement.scrollHeight,
  }))
}

async function screenshot(page, name, fullPage = true) {
  const path = resolve(evidenceDir, name)
  await page.screenshot({ path, fullPage })
  const png = await readFile(path)
  return { path: name, width: png.readUInt32BE(16), height: png.readUInt32BE(20) }
}

async function waitForServer(child) {
  const deadline = Date.now() + 20000
  let lastError
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`Vite exited with ${child.exitCode}: ${child.output}`)
    const localLine = child.output.split(/\r?\n/).find(line => line.includes('Local:'))
    const announcedUrl = localLine?.match(/Local:\s*(\S+)/)?.[1]?.replace(/\/$/, '')
    if (announcedUrl === baseUrl) {
      try {
        const response = await fetch(`${baseUrl}/`)
        if (response.ok) return announcedUrl
      } catch (error) { lastError = error }
    }
    await new Promise(resolveDelay => setTimeout(resolveDelay, 150))
  }
  throw new Error(`Vite did not become ready: ${lastError ?? child.output}`)
}

async function labelMeasurements(page) {
  return page.evaluate(() => [
    ['scenario', 'label[for="scenario"]'], ['area', 'label[for="area"]'],
    ['period', 'label[for="period"]'], ['imagePicker', '.file-button[for="images"]'],
  ].map(([name, selector]) => {
    const element = document.querySelector(selector)
    const rect = element.getBoundingClientRect()
    const style = getComputedStyle(element)
    return { name, text: element.innerText.trim(), visible: style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0, withinWidth: rect.left >= 0 && rect.right <= innerWidth + 1, rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } }
  }))
}

function targetsFitViewport(targets, width) {
  return targets.length > 0 && targets.every(target => target.left >= 0 && target.right <= width + 1)
}

function spacingOverride() {
  return `*, *::before, *::after { letter-spacing: .12em !important; word-spacing: .16em !important; line-height: 1.5 !important; } p { margin-block-end: 2em !important; }`
}

async function applySpacingOverride(page) {
  await page.addStyleTag({ content: spacingOverride() })
  await page.evaluate(() => new Promise(resolveFrame => requestAnimationFrame(() => requestAnimationFrame(resolveFrame))))
}

function runFixture() {
  const input = { input_id: 'input-0', ordinal: 0, sha256: jpegSha256, artifact_id: 'source-0' }
  const observations = [
    { input_id: input.input_id, ordinal: 0, class_name: 'excavator', state: 'detected', reason: null, source_artifact_id: input.artifact_id, input_sha256: jpegSha256 },
    { input_id: input.input_id, ordinal: 0, class_name: 'dump_truck', state: 'not_detected_in_frame', reason: null, source_artifact_id: input.artifact_id, input_sha256: jpegSha256 },
  ]
  return {
    run_id: runId,
    state: 'succeeded',
    intent: 'observation_only',
    context: { period: '2026-09-23T12:00:00+03:00', observation_area: 'north_gate' },
    stages: ['input_registration', 'frame_usability', 'equipment_observation', 'series_aggregation', 'rule_evaluation', 'result_projection']
      .map(name => ({ name, state: 'succeeded' })),
    inputs: [input],
    observations,
    requested_classes: ['excavator', 'dump_truck'],
    outcome: 'observations_only',
    result_projection: { outcome: 'observations_only', frames: observations, context: { period: '2026-09-23T12:00:00+03:00', observation_area: 'north_gate' } },
    native_evidence_by_frame: [{ artifact_id: 'native-0', input_id: input.input_id, ordinal: 0, sha256: 'native-sha256', invocation_id: 'invocation-0', profile_id: 'profile-0', profile_revision: 1, preprocessing_revision: 'fixture-v1' }],
  }
}

async function installApiFixture(context) {
  await context.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/analysis-choices') {
      await route.fulfill({ status: 200, contentType: 'application/json', headers: { 'cache-control': 'no-store' }, body: JSON.stringify({ stages: [{ id: 'excavation', label: 'Земляные работы', rule: null }] }) })
      return
    }
    if (url.pathname === `/api/runs/${runId}`) {
      await route.fulfill({ status: 200, contentType: 'application/json', headers: { 'cache-control': 'no-store' }, body: JSON.stringify(runFixture()) })
      return
    }
    const artifactMatch = url.pathname.match(new RegExp(`^/api/runs/${runId}/artifacts/([^/]+)$`))
    if (artifactMatch && artifactMatch[1] === 'native-0') {
      await route.fulfill({ status: 200, contentType: 'application/json', headers: { 'cache-control': 'no-store' }, body: JSON.stringify({ fixture: 'native evidence' }) })
      return
    }
    if (artifactMatch && artifactMatch[1] === 'source-0') {
      if (artifactMode === 'jpeg') {
        artifactResponses.push({ mode: artifactMode, url: url.pathname, status: 200, contentType: 'image/jpeg', byteLength: jpegBytes.length, sha256: jpegSha256 })
        await route.fulfill({ status: 200, contentType: 'image/jpeg', headers: { 'cache-control': 'no-store' }, body: jpegBytes })
      } else {
        const integrity = artifactMode === 'integrity'
        artifactResponses.push({ mode: artifactMode, url: url.pathname, status: integrity ? 409 : 503, contentType: 'application/json' })
        await route.fulfill({ status: integrity ? 409 : 503, contentType: 'application/json', headers: { 'cache-control': 'no-store' }, body: JSON.stringify({ code: integrity ? 'artifact_integrity_failed' : 'artifact_unavailable' }) })
      }
      return
    }
    await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ code: 'fixture_route_not_found' }) })
  })
}

async function collectSpacing(page) {
  return page.evaluate(() => {
    const element = document.querySelector('.page-intro p:last-child') || document.querySelector('p')
    const style = getComputedStyle(element)
    const fontSize = parseFloat(style.fontSize)
    return {
      letterSpacingPx: parseFloat(style.letterSpacing),
      letterSpacingEm: parseFloat(style.letterSpacing) / fontSize,
      wordSpacingPx: parseFloat(style.wordSpacing),
      wordSpacingEm: parseFloat(style.wordSpacing) / fontSize,
      lineHeightPx: parseFloat(style.lineHeight),
      lineHeightRatio: parseFloat(style.lineHeight) / fontSize,
      paragraphGapPx: parseFloat(style.marginBottom),
      paragraphGapEm: parseFloat(style.marginBottom) / fontSize,
      fontSizePx: fontSize,
    }
  })
}

async function findClippedContent(page) {
  return page.evaluate(() => [...document.querySelectorAll('body *')].flatMap(element => {
    if (element.closest('.sr-only') || element.matches('.sr-only') || !element.getClientRects().length) return []
    const style = getComputedStyle(element)
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return []
    const rect = element.getBoundingClientRect()
    const clipsX = ['hidden', 'clip'].includes(style.overflowX) && element.scrollWidth > element.clientWidth + 1
    const clipsY = ['hidden', 'clip'].includes(style.overflowY) && element.scrollHeight > element.clientHeight + 1
    return clipsX || clipsY ? [{ tag: element.tagName.toLowerCase(), className: String(element.className || ''), width: rect.width, height: rect.height, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight, text: (element.innerText || '').slice(0, 80) }] : []
  }))
}

async function main() {
  const report = {
    generatedAt: new Date().toISOString(),
    scope: 'Headless local Vite and a completed-run API fixture; no backend, model, production, or browser-toolbar behavior is verified.',
    setup: { baseUrl, vitePort: port, serverAnnouncedUrl: null, chromePath, playwrightModule: playwrightPath, headless: true, userAgent: null, browserVersion: null },
    sourceArtifact: { path: 'web/public/demo/Screenshot_23.jpg', mimeType: 'image/jpeg', byteLength: jpegBytes.length, sha256: jpegSha256, intrinsic: jpegDimensions },
    phone320: null,
    rendered200: null,
    imageDecode: null,
    dialog: null,
    errorMessages: null,
    screenshots: [],
    checks,
  }

  if (!chromePath || !playwrightPath) throw new Error('Set CHROME_PATH and PLAYWRIGHT_MODULE as specified in the F6 verification command.')
  server = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], {
    cwd: resolve(projectRoot, 'web'), env: process.env, stdio: ['ignore', 'pipe', 'pipe'],
  })
  server.output = ''
  server.stdout.on('data', chunk => { server.output += chunk.toString() })
  server.stderr.on('data', chunk => { server.output += chunk.toString() })
  report.setup.serverAnnouncedUrl = await waitForServer(server)
  browser = await chromium.launch({ headless: true, executablePath: chromePath })
  report.setup.browserVersion = browser.version()

  const phoneContext = await browser.newContext({ viewport: { width: 320, height: 900 }, deviceScaleFactor: 1, hasTouch: true })
  await installApiFixture(phoneContext)
  const phonePage = await phoneContext.newPage()
  phonePage.on('pageerror', error => pageErrors.push(error.message))
  const phoneNavigation = await phonePage.goto(`${baseUrl}/`, { waitUntil: 'networkidle' })
  await phonePage.getByRole('heading', { name: 'Наблюдение за техникой' }).waitFor()
  await applySpacingOverride(phonePage)
  const phoneLayout = await layoutMetrics(phonePage)
  const phoneControls = await phonePage.evaluate(() => [
    ['navigation', 'header nav a'], ['scenario', '#scenario'], ['area', '#area'], ['period', '#period'],
    ['imagePicker', '.file-button[for="images"]'], ['submit', '#submit-action'],
  ].map(([name, selector]) => {
    const element = document.querySelector(selector)
    const rect = element.getBoundingClientRect()
    const style = getComputedStyle(element)
    return { name, text: (element.innerText || element.getAttribute('aria-label') || '').trim(), visible: style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0, withinWidth: rect.left >= 0 && rect.right <= innerWidth + 1, inViewport: rect.top < innerHeight && rect.bottom > 0, rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } }
  }))
  const phoneLabels = await labelMeasurements(phonePage)
  const phoneClipped = await findClippedContent(phonePage)
  const phoneSpacing = await collectSpacing(phonePage)
  const phoneScreenshot = await screenshot(phonePage, 'f6-phone-320-css.png')
  report.screenshots.push(phoneScreenshot)
  await phonePage.evaluate(() => {
    window.__f6Touch = null
    document.querySelector('#scenario').addEventListener('pointerdown', event => {
      window.__f6Touch = { pointerType: event.pointerType, targetId: event.target.id }
    }, { once: true })
  })
  await phonePage.locator('#scenario').tap()
  const touchEvidence = { ...await phonePage.evaluate(() => ({ ...window.__f6Touch, focusedControl: document.activeElement.id })), emulation: 'Playwright BrowserContext hasTouch=true' }
  report.phone320 = { emulation: { viewportCssPixels: { width: 320, height: 900 }, deviceScaleFactor: 1, hasTouch: true, browserZoom: 'not modified', textSpacingOverride: { letterSpacing: '0.12em', wordSpacing: '0.16em', lineHeight: '1.5', paragraphSpacing: '2em' } }, responseStatus: phoneNavigation.status(), document: phoneLayout, textSpacing: phoneSpacing, keyControls: phoneControls, labels: phoneLabels, clippedContent: phoneClipped, touchEvidence, screenshot: phoneScreenshot }
  check('320 CSS-pixel viewport has no horizontal overflow', phoneLayout.innerWidth === 320 && phoneLayout.documentWidth <= 320 && phoneLayout.bodyWidth <= 320, phoneLayout)
  check('320 CSS-pixel navigation, fields, picker, and primary submit render within the viewport width', phoneControls.every(control => control.visible && control.withinWidth), phoneControls)
  check('320 CSS-pixel scenario, area, period, and image-picker labels are visible within the viewport width', phoneLabels.length === 4 && phoneLabels.every(label => label.visible && label.withinWidth), phoneLabels)
  check('320 CSS-pixel text-spacing layout has no clipped content', phoneClipped.length === 0, phoneClipped)
  check('320 CSS-pixel text-spacing overrides are applied', phoneSpacing.letterSpacingEm >= 0.12 - 0.01 && phoneSpacing.wordSpacingEm >= 0.16 - 0.01 && phoneSpacing.lineHeightRatio >= 1.5 - 0.01 && phoneSpacing.paragraphGapEm >= 2 - 0.01, phoneSpacing)
  check('320 CSS-pixel visible form targets are at least 44 CSS pixels in both dimensions', phoneControls.every(control => control.rect.height >= 44 && control.rect.width >= 44), phoneControls)
  check('320 CSS-pixel touch emulation taps and focuses the scenario field', touchEvidence.pointerType === 'touch' && touchEvidence.targetId === 'scenario' && touchEvidence.focusedControl === 'scenario', touchEvidence)

  const wideContext = await browser.newContext({ viewport: { width: 640, height: 900 }, deviceScaleFactor: 2 })
  await installApiFixture(wideContext)
  const widePage = await wideContext.newPage()
  widePage.on('pageerror', error => pageErrors.push(error.message))
  const wideFormNavigation = await widePage.goto(`${baseUrl}/`, { waitUntil: 'networkidle' })
  await widePage.getByRole('heading', { name: 'Наблюдение за техникой' }).waitFor()
  await applySpacingOverride(widePage)
  const wideFormLayout = await layoutMetrics(widePage)
  const wideFormClipped = await findClippedContent(widePage)
  const wideFormTargets = await targetMeasurements(widePage, 'form')
  const spacing = await collectSpacing(widePage)
  const wideFormScreenshot = await screenshot(widePage, 'f6-200-equivalent-form-640-css-dsf2.png')
  report.screenshots.push(wideFormScreenshot)
  check('200% equivalent uses a 640 CSS-pixel viewport and 2x device scale', wideFormLayout.innerWidth === 640 && wideFormLayout.devicePixelRatio === 2 && wideFormScreenshot.width === 1280, { document: wideFormLayout, screenshot: wideFormScreenshot })
  check('text-spacing overrides are applied at the required values', spacing.letterSpacingEm >= 0.12 - 0.01 && spacing.wordSpacingEm >= 0.16 - 0.01 && spacing.lineHeightRatio >= 1.5 - 0.01 && spacing.paragraphGapEm >= 2 - 0.01, spacing)
  check('200% equivalent form has no horizontal overflow', wideFormLayout.documentWidth <= 640 && wideFormLayout.bodyWidth <= 640, wideFormLayout)
  check('200% equivalent form has no clipped content', wideFormClipped.length === 0, wideFormClipped)
  check('visible form targets are at least 44 CSS pixels in both dimensions', wideFormTargets.length > 0 && wideFormTargets.every(target => target.height >= 44 && target.width >= 44), wideFormTargets)
  check('visible form targets stay inside the 640 CSS-pixel viewport', targetsFitViewport(wideFormTargets, 640), wideFormTargets)
  report.rendered200 = { emulation: { viewportCssPixels: { width: 640, height: 900 }, deviceScaleFactor: 2, browserZoomEquivalent: '200% at a 1280 CSS-pixel source viewport', textSpacingOverride: { letterSpacing: '0.12em', wordSpacing: '0.16em', lineHeight: '1.5', paragraphSpacing: '2em' } }, form: { responseStatus: wideFormNavigation.status(), document: wideFormLayout, textSpacing: spacing, clippedContent: wideFormClipped, targets: wideFormTargets, screenshot: wideFormScreenshot } }

  const runNavigation = await widePage.goto(`${baseUrl}${runPath}`, { waitUntil: 'networkidle' })
  await widePage.getByRole('heading', { name: 'Только наблюдения' }).waitFor()
  await applySpacingOverride(widePage)
  const runLayout = await layoutMetrics(widePage)
  const clipped = await findClippedContent(widePage)
  const resultTargets = await targetMeasurements(widePage, '.run-workspace')
  const image = widePage.locator('.source-thumbnail img').first()
  const decodedImage = await image.evaluate(async element => {
    await element.decode()
    return { complete: element.complete, naturalWidth: element.naturalWidth, naturalHeight: element.naturalHeight, currentSrc: element.currentSrc }
  })
  await image.waitFor({ state: 'visible' })
  const runScreenshot = await screenshot(widePage, 'f6-200-equivalent-completed-run-640-css-dsf2.png')
  report.screenshots.push(runScreenshot)
  report.setup.userAgent = await widePage.evaluate(() => navigator.userAgent)
  report.rendered200.run = { responseStatus: runNavigation.status(), document: runLayout, clippedContent: clipped, targets: resultTargets, screenshot: runScreenshot }
  check('direct /runs/{id} navigation renders the completed run fixture', runNavigation.status() === 200 && report.setup.userAgent !== null, { status: runNavigation.status(), url: widePage.url() })
  check('200% equivalent result has no horizontal overflow or clipped content', runLayout.innerWidth === 640 && runLayout.documentWidth <= 640 && runLayout.bodyWidth <= 640 && clipped.length === 0, { layout: runLayout, clippedContent: clipped })
  check('visible result targets are at least 44 CSS pixels in both dimensions', resultTargets.length > 0 && resultTargets.every(target => target.height >= 44 && target.width >= 44), resultTargets)
  check('visible result targets stay inside the 640 CSS-pixel viewport', targetsFitViewport(resultTargets, 640), resultTargets)
  const servedJpegs = artifactResponses.filter(response => response.mode === 'jpeg')
  report.imageDecode = { requestCount: servedJpegs.length, responses: servedJpegs, image: decodedImage, matchesBundledIntrinsicDimensions: decodedImage.naturalWidth === jpegDimensions.width && decodedImage.naturalHeight === jpegDimensions.height }
  check('actual bundled JPEG bytes are served with image/jpeg and decode to matching intrinsic dimensions', servedJpegs.length > 0 && servedJpegs.every(response => response.contentType === 'image/jpeg' && response.byteLength === jpegBytes.length && response.sha256 === jpegSha256) && report.imageDecode.matchesBundledIntrinsicDimensions, report.imageDecode)

  const opener = widePage.getByRole('button', { name: 'Открыть кадр 1' })
  await opener.focus()
  await widePage.keyboard.press('Enter')
  const dialog = widePage.getByRole('dialog', { name: 'Просмотр исходных кадров' })
  await dialog.waitFor({ state: 'visible' })
  await dialog.getByText('Технические данные наблюдателя').waitFor()
  const initialFocus = await widePage.evaluate(() => ({ inside: document.querySelector('dialog')?.contains(document.activeElement), tag: document.activeElement?.tagName, label: document.activeElement?.textContent?.trim() }))
  await widePage.keyboard.press('Shift+Tab')
  const reverseBoundaryFocus = await widePage.evaluate(() => ({ open: document.querySelector('dialog')?.open, inside: document.querySelector('dialog')?.contains(document.activeElement), tag: document.activeElement?.tagName, label: document.activeElement?.textContent?.trim().slice(0, 50) }))
  await widePage.keyboard.press('Tab')
  const reverseWrapFocus = await widePage.evaluate(() => ({ open: document.querySelector('dialog')?.open, inside: document.querySelector('dialog')?.contains(document.activeElement), tag: document.activeElement?.tagName, label: document.activeElement?.textContent?.trim().slice(0, 50) }))
  const forwardFocus = []
  for (let index = 0; index < 8; index++) {
    await widePage.keyboard.press('Tab')
    forwardFocus.push(await widePage.evaluate(() => ({ open: document.querySelector('dialog')?.open, inside: document.querySelector('dialog')?.contains(document.activeElement), tag: document.activeElement?.tagName, label: document.activeElement?.textContent?.trim().slice(0, 50) })))
  }
  await widePage.keyboard.press('Shift+Tab')
  const reverseFocus = await widePage.evaluate(() => ({ open: document.querySelector('dialog')?.open, inside: document.querySelector('dialog')?.contains(document.activeElement), tag: document.activeElement?.tagName, label: document.activeElement?.textContent?.trim().slice(0, 50) }))
  const dialogTargets = await targetMeasurements(widePage, '.evidence-dialog')
  const dialogScreenshot = await screenshot(widePage, 'f6-native-evidence-dialog-640-css-dsf2.png', false)
  report.screenshots.push(dialogScreenshot)
  await widePage.keyboard.press('Escape')
  await widePage.waitForFunction(() => !document.querySelector('dialog')?.open)
  const dialogClosed = await widePage.evaluate(() => !document.querySelector('dialog')?.open)
  const focusRestored = await opener.evaluate(element => document.activeElement === element)
  report.dialog = { initialFocus, reverseBoundaryFocus, reverseWrapFocus, forwardFocus, reverseFocus, focusRestored, targets: dialogTargets, screenshot: dialogScreenshot }
  check('native modal opens with keyboard focus inside', initialFocus.inside, initialFocus)
  check('Tab and Shift+Tab stay inside the open native modal', reverseBoundaryFocus.open && reverseBoundaryFocus.inside && reverseWrapFocus.open && reverseWrapFocus.inside && reverseWrapFocus.label === initialFocus.label && forwardFocus.every(item => item.open && item.inside) && reverseFocus.open && reverseFocus.inside, { reverseBoundaryFocus, reverseWrapFocus, forwardFocus, reverseFocus })
  check('native evidence disclosure is reachable in the modal Tab sequence', forwardFocus.some(item => item.label === 'Технические данные наблюдателя'), forwardFocus)
  check('Escape closes the native modal and restores focus to its opener', dialogClosed && focusRestored, { closed: dialogClosed, focusRestored })
  check('visible modal targets are at least 44 CSS pixels in both dimensions', dialogTargets.length > 0 && dialogTargets.every(target => target.height >= 44 && target.width >= 44), dialogTargets)
  check('visible modal targets stay inside the 640 CSS-pixel viewport', targetsFitViewport(dialogTargets, 640), dialogTargets)

  artifactMode = 'integrity'
  const integrityPage = await wideContext.newPage()
  integrityPage.on('pageerror', error => pageErrors.push(error.message))
  await integrityPage.goto(`${baseUrl}${runPath}?fixture=integrity`, { waitUntil: 'networkidle' })
  await integrityPage.getByText('Целостность артефакта не подтверждена').waitFor()
  artifactMode = 'unavailable'
  const unavailablePage = await wideContext.newPage()
  unavailablePage.on('pageerror', error => pageErrors.push(error.message))
  await unavailablePage.goto(`${baseUrl}${runPath}?fixture=unavailable`, { waitUntil: 'networkidle' })
  await unavailablePage.getByText('Не удалось открыть исходное изображение').waitFor()
  report.errorMessages = { integrity: 'Целостность артефакта не подтверждена', unavailable: 'Не удалось открыть исходное изображение', verified: true }
  check('source failures show distinct integrity and unavailable messages', true, report.errorMessages)

  check('browser page has no uncaught page errors', pageErrors.length === 0, pageErrors)
  report.checks = checks
  report.passed = checks.filter(item => item.pass).length
  report.failed = checks.length - report.passed
  report.pageErrors = pageErrors
  report.artifactResponses = artifactResponses
  await writeFile(resolve(evidenceDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`)
  const screenshotList = report.screenshots.map(item => `- \`${item.path}\` (${item.width} x ${item.height} PNG)`).join('\n')
  const markdown = `# F6 rendered UI verification\n\n- Result: **${report.failed === 0 ? 'PASS' : 'FAIL'}** (${report.passed}/${checks.length} checks).\n- Browser: ${report.setup.browserVersion}; headless via Playwright at \`${chromePath}\`; Vite announced \`${report.setup.serverAnnouncedUrl}\`.\n- Fixture: local completed-run response for \`${runId}\`; source artifact served from the bundled JPEG bytes.\n- Phone: 320 CSS px, device scale 1; document width ${report.phone320.document.documentWidth}px; labels fit, no clipped content, no browser zoom.\n- Touch emulation: tapping the scenario field produced a \`${touchEvidence.pointerType}\` pointer event and focused the field; this is emulated input, not physical-device verification.\n- 200% equivalent: 640 CSS px, device scale 2, ${report.rendered200.form.screenshot.width} rendered screenshot pixels; text spacing 0.12em / 0.16em / 1.5 / 2em; form and result have no clipped content and measured targets stay in the viewport.\n- JPEG: ${jpegBytes.length} bytes, SHA-256 \`${jpegSha256}\`, intrinsic ${jpegDimensions.width} x ${jpegDimensions.height}; browser decoded ${decodedImage.naturalWidth} x ${decodedImage.naturalHeight}.\n- Dialog: keyboard activation opened the native modal, forward/reverse boundary traversal stayed inside while open, Escape closed it, opener focus restored: ${focusRestored}.\n- Failure messages: integrity and unavailable messages both matched the UI.\n- Scope limit: local fixture evidence only; no backend/API service, model accuracy, production, browser-toolbar zoom, or physical-device touch was verified.\n\nScreenshots:\n${screenshotList}\n`
  await writeFile(resolve(evidenceDir, 'report.md'), markdown)
  console.log(`F6 rendered UI: ${report.passed}/${checks.length} checks passed; report: ${resolve(evidenceDir, 'report.md')}`)
  if (report.failed) process.exitCode = 1
}

try {
  await main()
} catch (error) {
  checks.push({ name: 'verification script completed', pass: false, details: { message: error.message, stack: error.stack } })
  const failureReport = { generatedAt: new Date().toISOString(), failed: 1, checks, artifactResponses, pageErrors, viteOutput: server?.output ?? '', scope: 'Headless local fixture only.' }
  await writeFile(resolve(evidenceDir, 'report.json'), `${JSON.stringify(failureReport, null, 2)}\n`)
  console.error(error)
  process.exitCode = 1
} finally {
  await browser?.close()
  if (server && server.exitCode === null) {
    server.kill('SIGTERM')
    await new Promise(resolveExit => {
      const timer = setTimeout(resolveExit, 2000)
      server.once('exit', () => { clearTimeout(timer); resolveExit() })
    })
  }
}
