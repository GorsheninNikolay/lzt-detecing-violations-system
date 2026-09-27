// Headless verification entrypoint; install playwright-core in an external tooling directory.
import { createRequire } from 'node:module'
const require = createRequire(process.env.PLAYWRIGHT_PACKAGE || '/private/tmp/lzt-design-experiment/tooling/package.json')
const { chromium } = require('playwright-core')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/private/tmp/lzt-video-browsers/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell' })
try {
  const page = await browser.newPage()
  await page.goto(process.env.DEMO_URL || 'http://127.0.0.1:5174')
  await page.getByRole('heading', { name: 'Проекты', exact: true }).waitFor()
  console.log('Demo project entry rendered')
} finally { await browser.close() }
