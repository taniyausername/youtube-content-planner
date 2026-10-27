/* Optional end-to-end check. Start with: npm install --no-save playwright
   npx playwright install chromium
   node tests/browser_smoke.cjs
   CHROMIUM_EXECUTABLE may select an existing Chromium binary. */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const dir = mkdtempSync(join(tmpdir(), 'planner-browser-'));
  const server = spawn(process.env.PYTHON || 'python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8765'], {
    env: {...process.env, DATABASE_PATH: join(dir, 'test.db'), APP_ACCESS_TOKEN: '', YOUTUBE_API_KEY: '', LLM_API_KEY: ''}, stdio: 'pipe'});
  let logs = ''; server.stderr.on('data', text => { logs += text; });
  let browser;
  try {
    let ready = false;
    for (let i = 0; i < 100; i++) {
      try { const response = await fetch('http://127.0.0.1:8765/health'); if (response.ok) { ready = true; break; } } catch (_) {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert(ready, 'Server did not start: ' + logs);
    browser = await chromium.launch({headless: true, ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath: process.env.CHROMIUM_EXECUTABLE} : {})});
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:8765');
    await page.getByRole('button', {name: 'Build content plan'}).click();
    await page.waitForSelector('.topic-card');
    assert((await page.locator('.topic-card').count()) > 1);
    assert((await page.locator('#run-mode').textContent()).includes('SYNTHETIC'));
    await page.locator('.topic-card').first().getByText('Why this score?', {exact: true}).click();
    assert(await page.locator('.topic-card').first().locator('table').isVisible());
    await page.locator('.topic-card').first().getByText('Content plan & title directions', {exact: true}).click();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', {name: 'JSON ↓'}).click();
    assert.equal((await downloadPromise).suggestedFilename(), 'content-plan.json');
    await page.waitForSelector('.history-item');
    await page.reload(); await page.waitForSelector('.history-item');
    await page.locator('.history-item').first().click();
    await page.waitForSelector('.topic-card');
    if (process.env.SCREENSHOT_DIR) await page.screenshot({path: join(process.env.SCREENSHOT_DIR, 'desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile horizontal overflow');
    if (process.env.SCREENSHOT_DIR) await page.screenshot({path: join(process.env.SCREENSHOT_DIR, 'mobile.png'), fullPage: true});
    await page.locator('#niche').fill('<img src=x onerror=alert(1)>');
    await page.getByRole('button', {name: 'Build content plan'}).click();
    await page.waitForFunction(() => document.getElementById('results-title').textContent === '<img src=x onerror=alert(1)>');
    assert.equal(await page.locator('#results img').count(), 0);
    page.on('dialog', dialog => dialog.accept());
    await page.getByRole('button', {name: 'Clear all'}).click();
    await page.waitForFunction(() => document.getElementById('results').hidden);
    assert.deepEqual(errors, []);
    console.log('PASS: browser research, score details, plan details, JSON download, history reopen, mobile overflow, safe text rendering, clear history; no page errors.');
  } finally {
    if (browser) await browser.close();
    if (server.exitCode === null) { server.kill(); await new Promise(resolve => server.once('exit', resolve)); }
    rmSync(dir, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exit(1); });
