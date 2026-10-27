'use strict';
const $ = id => document.getElementById(id);
let currentRun = null;
let busy = false;
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function token() { return $('access-token').value.trim(); }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json',
    ...(token() ? {Authorization: 'Bearer ' + token()} : {}), ...options.headers}});
  if (!response.ok) {
    let message = 'The request failed. Please try again.';
    try { const data = await response.json(); message = typeof data.detail === 'string' ? data.detail : 'Check the input fields and try again.'; } catch (_) {}
    throw new Error(message);
  }
  return response;
}
function status(text, error = false, loading = false) {
  $('status').replaceChildren();
  if (text) $('status').append(node('div', text, 'notice' + (error ? ' error' : '') + (loading ? ' busy' : '')));
}
function list(items, ordered = false) {
  const ul = node(ordered ? 'ol' : 'ul', undefined, 'outline');
  items.forEach(text => ul.append(node('li', text)));
  return ul;
}
function details(title) { const d = node('details'); d.append(node('summary', title)); return d; }
function number(value) { return value === null || value === undefined ? 'Unknown' : new Intl.NumberFormat(undefined, {maximumFractionDigits: 2}).format(value); }
function render(result) {
  currentRun = result;
  $('empty').hidden = true; $('results').hidden = false;
  $('run-mode').textContent = result.request.mode === 'demo' ? 'DEMO · SYNTHETIC DATA' : 'LIVE · PUBLIC YOUTUBE METADATA';
  $('results-title').textContent = result.request.niche;
  $('metrics').replaceChildren();
  const channels = new Set(result.videos.map(v => v.channel_id)).size;
  [[result.video_count, 'videos in sample'], [channels, 'sampled channels'], [result.opportunities.length, 'topic opportunities']].forEach(([value, label]) => {
    const box = node('div', undefined, 'metric'); box.append(node('strong', value), node('span', label)); $('metrics').append(box);
  });
  $('score-note').textContent = 'Scores compare topics within this research sample only. Evidence strength is not a prediction of success. ' + new Date(result.created_at).toLocaleString();
  $('opportunities').replaceChildren();
  result.opportunities.forEach(item => {
    const card = node('article', undefined, 'panel topic-card');
    const top = node('div', undefined, 'rank-line');
    top.append(node('span', 'OPPORTUNITY ' + String(item.rank).padStart(2, '0')),
      node('span', item.priority, 'badge' + (item.priority === 'Review first' ? ' review' : '')));
    const title = node('div', undefined, 'section-heading');
    const score = node('div', item.score.toFixed(1), 'score'); score.append(node('small', ' / 100'));
    title.append(node('h3', item.topic), score);
    card.append(top, title, node('p', item.plan.angle, 'angle'),
      node('p', item.plan.audience + ' · ' + item.plan.format + ' · ' + item.sample_size + ' supporting videos', 'meta'));
    const critic = node('div', undefined, 'critic');
    critic.append(node('strong', 'Evidence: ' + item.agents.critic.evidence_strength));
    critic.append(list(item.agents.critic.warnings.length ? item.agents.critic.warnings : ['No rule-based flags in this sample. Manual review is still required.']));
    card.append(critic);
    const plan = details('Content plan & title directions');
    plan.append(node('p', item.plan.rationale, 'small'), node('h4', 'Title directions'), list(item.plan.title_directions),
      node('h4', 'Opening hook'), node('p', item.plan.hook), node('h4', 'Outline'), list(item.plan.outline, true),
      node('h4', 'Related subtopics'), list(item.plan.subtopics), node('p', item.plan.next_action, 'small'),
      node('p', 'Draft source: ' + item.plan.source + '. ' + (item.plan.draft_notice || 'Editable template directions.'), 'small'));
    const breakdown = details('Why this score?');
    const table = node('table'); const head = node('tr');
    ['Signal', 'Raw value', 'Weight', 'Points'].forEach(s => head.append(node('th', s))); table.append(head);
    Object.keys(result.base_weights).forEach(key => {
      const row = node('tr');
      [key.replaceAll('_', ' '), number(item.raw_signals[key]), key in item.effective_weights ? (item.effective_weights[key] * 100).toFixed(1) + '%' : 'Omitted', key in item.contributions ? item.contributions[key].toFixed(2) : '—'].forEach(s => row.append(node('td', s)));
      table.append(row);
    });
    const wrap = node('div', undefined, 'table-wrap'); wrap.append(table); breakdown.append(wrap);
    breakdown.append(node('p', 'Unavailable signals are omitted across the entire cohort and remaining weights are rescaled. Competition points increase as the sampled channel count falls.', 'small'));
    ['trend', 'competition', 'engagement'].forEach(key => breakdown.append(node('p', item.agents[key].note, 'small')));
    const competitors = details('Channel activity in this sample');
    item.agents.competition.channels.forEach(c => competitors.append(node('p', c.name + ' · ' + c.sample_uploads + ' sampled videos · ' + c.sample_uploads_per_day + ' per day of search window', 'small')));
    const evidence = details('Inspect ' + item.sample_size + ' supporting videos');
    item.evidence_ids.forEach(id => {
      const v = result.videos.find(video => video.id === id); if (!v) return;
      const box = node('div', undefined, 'evidence');
      if (!v.synthetic && /^[A-Za-z0-9_-]{11}$/.test(v.id)) {
        const a = node('a', v.title); a.href = 'https://www.youtube.com/watch?v=' + encodeURIComponent(v.id); a.target = '_blank'; a.rel = 'noopener noreferrer'; box.append(a);
      } else box.append(node('strong', v.title));
      box.append(node('p', v.channel_title + ' · Published ' + new Date(v.published_at).toLocaleDateString(), 'small'),
        node('p', 'Views ' + number(v.views) + ' · Likes ' + number(v.likes) + ' · Comments ' + number(v.comments), 'small'),
        node('p', (v.synthetic ? 'Synthetic example · ' : '') + 'Observed ' + new Date(v.observed_at).toLocaleString(), 'small'));
      evidence.append(box);
    });
    card.append(plan, breakdown, competitors, evidence); $('opportunities').append(card);
  });
  $('limitations').replaceChildren(...result.limitations.map(s => node('li', s)));
  $('drafting').textContent = result.drafting;
}
async function history() {
  const rows = await (await api('/api/runs')).json();
  $('history-list').replaceChildren();
  if (!rows.length) $('history-list').append(node('p', 'No saved research yet.', 'small'));
  rows.forEach(row => {
    const button = node('button', row.request.niche, 'history-item'); button.type = 'button';
    button.append(node('small', row.request.mode + ' · ' + new Date(row.created_at).toLocaleString()));
    button.addEventListener('click', async () => { if (busy) return; try { render(await (await api('/api/runs/' + row.id)).json()); status(''); } catch (error) { status(error.message, true); } });
    $('history-list').append(button);
  });
}
$('research-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  busy = true; $('run-button').disabled = true;
  status('Collecting signals, comparing topics and checking evidence…', false, true);
  try {
    const payload = {niche: $('niche').value, audience: $('audience').value, format: $('format').value,
      mode: $('mode').value, days: Number($('days').value), max_videos: Number($('max-videos').value)};
    render(await (await api('/api/research', {method: 'POST', body: JSON.stringify(payload)})).json());
    status('Research saved. Review the critic findings before using a recommendation.'); await history();
  } catch (error) { status(error.message, true); }
  finally { busy = false; $('run-button').disabled = false; }
});
$('mode').addEventListener('change', () => { $('mode-note').textContent = $('mode').value === 'demo' ? 'Demo works offline. All sample videos and statistics are invented for testing.' : 'Live mode uses the server’s API key and a bounded public search sample. Collection may take a minute.'; });
$('unlock').addEventListener('click', () => history().then(() => status('History unlocked.')).catch(e => status(e.message, true)));
$('clear-history').addEventListener('click', async () => {
  if (busy || !confirm('Delete all saved research and observations on this server?')) return;
  try { await api('/api/runs', {method: 'DELETE'}); currentRun = null; $('results').hidden = true; $('empty').hidden = false; await history(); status('History cleared.'); } catch (e) { status(e.message, true); }
});
document.querySelectorAll('[data-export]').forEach(button => button.addEventListener('click', async () => {
  if (!currentRun) return;
  try {
    const kind = button.dataset.export;
    const response = await api('/api/runs/' + currentRun.id + '/export/' + kind);
    const url = URL.createObjectURL(await response.blob()); const a = node('a');
    a.href = url; a.download = 'content-plan.' + kind; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { status(error.message, true); }
}));
(async () => {
  try {
    const config = await (await api('/api/config')).json();
    $('auth-box').hidden = !config.auth_required;
    $('live-option').disabled = !config.live_available;
    if (!config.live_available) $('live-option').textContent = 'Live · API key not configured';
    if (!config.auth_required) await history();
  } catch (e) { status(e.message, true); }
})();
