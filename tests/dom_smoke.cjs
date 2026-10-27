/* Interface logic check without a rendering engine: npm install --no-save jsdom
   Run from the project root: node tests/dom_smoke.cjs */
const { JSDOM } = require('jsdom');
const { readFileSync, mkdtempSync, rmSync } = require('node:fs');
const { spawn } = require('node:child_process');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const assert = require('node:assert/strict');
const pause = () => new Promise(resolve => setTimeout(resolve, 50));
(async () => {
  const dir = mkdtempSync(join(tmpdir(), 'planner-dom-'));
  const server = spawn(process.env.PYTHON || 'python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8766'], {
    env: {...process.env, DATABASE_PATH: join(dir, 'test.db'), APP_ACCESS_TOKEN: '', YOUTUBE_API_KEY: '', LLM_API_KEY: ''}, stdio: 'pipe'});
  let logs = ''; server.stderr.on('data', text => logs += text);
  let dom;
  try {
    let ready = false;
    for (let i = 0; i < 200; i++) {
      try { if ((await fetch('http://127.0.0.1:8766/health')).ok) { ready = true; break; } } catch (_) {}
      await pause();
    }
    assert(ready, logs);
    dom = new JSDOM(readFileSync('app/static/index.html', 'utf8'), {url: 'http://127.0.0.1:8766', runScripts: 'outside-only'});
    const {window} = dom; const d = window.document;
    const errors = []; window.addEventListener('error', e => errors.push(e.message));
    window.fetch = (path, options) => fetch(new URL(path, window.location.href), options);
    window.confirm = () => true;
    window.eval(readFileSync('app/static/app.js', 'utf8'));
    async function until(check) { for (let i = 0; i < 200; i++) { if (check()) return; await pause(); } throw new Error('UI wait timed out: ' + d.getElementById('status').textContent); }
    await until(() => d.getElementById('live-option').disabled);
    d.getElementById('research-form').dispatchEvent(new window.Event('submit', {cancelable: true}));
    await until(() => d.querySelectorAll('.topic-card').length > 1 && !d.getElementById('run-button').disabled);
    assert(d.getElementById('run-mode').textContent.includes('SYNTHETIC'));
    assert.equal(d.querySelectorAll('.topic-card').length, 4);
    assert(d.querySelector('table').textContent.includes('Omitted'));
    assert(d.querySelector('.history-item'));
    assert(d.querySelector('.topic-card').textContent.includes('Title directions'));
    assert.equal(d.querySelectorAll('.evidence a').length, 0, 'Demo evidence must not create real source links');
    d.querySelector('.history-item').click(); await pause();
    d.getElementById('niche').value = '<img src=x onerror=alert(1)>';
    d.getElementById('research-form').dispatchEvent(new window.Event('submit', {cancelable: true}));
    await until(() => d.getElementById('results-title').textContent === '<img src=x onerror=alert(1)>' && !d.getElementById('run-button').disabled);
    assert.equal(d.querySelectorAll('#results img').length, 0);
    d.getElementById('clear-history').click();
    await until(() => d.getElementById('results').hidden);
    assert.equal(d.querySelectorAll('.history-item').length, 0);
    assert.deepEqual(errors, []);
    console.log('PASS: DOM research submission, four topic cards, score table, content plan, demo label, history, safe text rendering and clear-history flow. This is not a visual browser check.');
  } finally {
    if (dom) dom.window.close();
    if (server.exitCode === null) { server.kill(); await new Promise(resolve => server.once('exit', resolve)); }
    rmSync(dir, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exit(1); });
