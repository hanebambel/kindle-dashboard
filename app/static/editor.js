// Kindle dashboard editor. Everything autosaves; saves run one at a time
// through `queue` so a layout PUT never races a widget-config PATCH.
const $ = (sel, root = document) => root.querySelector(sel);
const NAME = document.body.dataset.dashboard;
const API = NAME ? `/api/dashboards/${encodeURIComponent(NAME)}` : null;
const COLS = 12, ROWS = 16;

// ---------- feedback ----------
let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 4000);
}

function setStatus(state) {
  const el = $('#status');
  if (!el) return;
  el.dataset.state = state;
  el.textContent = { saving: 'Saving…', saved: 'All changes saved', error: 'Save failed' }[state];
}

function confirmDialog(title, text) {
  const dlg = $('#confirm-dialog');
  $('#confirm-title').textContent = title;
  $('#confirm-text').textContent = text;
  dlg.returnValue = '';
  dlg.showModal();
  return new Promise(resolve => dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'), { once: true }));
}

async function api(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new Error(detail);
  }
  return res.headers.get('content-type')?.includes('json') ? res.json() : res.text();
}

// ---------- save queue ----------
let queue = Promise.resolve();
function save(fn) {
  setStatus('saving');
  queue = queue.then(fn).then(
    () => { setStatus('saved'); refreshRender(); },
    (err) => { setStatus('error'); toast(err.message); },
  );
  return queue;
}

// ---------- rendered PNG behind the grid ----------
let renderSeq = 0, renderTimer;
function refreshRender() {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(() => {
    const seq = ++renderSeq;
    const img = new Image();
    $('#screen').classList.add('rendering');
    img.onload = img.onerror = () => {
      if (seq !== renderSeq) return; // a newer render superseded this one
      $('#screen').classList.remove('rendering');
      if (img.naturalWidth) $('#render').src = img.src;
    };
    img.src = `/dash/${encodeURIComponent(NAME)}.png?t=${Date.now()}`;
  }, 250);
}

// ---------- grid ----------
let grid;
const configs = {}; // widget id -> config (kept in sync with the server)
let selected = null;

function makeTile(w) {
  const el = document.createElement('div');
  el.className = 'grid-stack-item';
  el.dataset.id = w.id;
  el.dataset.type = w.type;
  el.tabIndex = 0;
  el.setAttribute('role', 'button');
  el.setAttribute('aria-label', `${w.type} widget ${w.id}`);
  for (const k of ['x', 'y', 'w', 'h']) if (w.pos?.[k] != null) el.setAttribute(`gs-${k}`, w.pos[k]);
  if (!w.pos) el.setAttribute('gs-auto-position', 'true');
  const content = document.createElement('div');
  content.className = 'grid-stack-item-content';
  content.append($('#tile-tpl').content.cloneNode(true));
  $('.tile-label', content).textContent = w.type;
  el.append(content);
  return el;
}

function updateDims(el) {
  const n = el.gridstackNode;
  if (n) $('.tile-dims', el).textContent = `${n.w}×${n.h} @ ${n.x},${n.y}`;
}

function currentLayout() {
  return grid.getGridItems().map(el => {
    const n = el.gridstackNode;
    return { id: el.dataset.id, type: el.dataset.type,
             pos: { x: n.x, y: n.y, w: n.w, h: n.h }, config: configs[el.dataset.id] || {} };
  });
}

let layoutTimer;
function saveLayoutSoon() {
  setStatus('saving');
  clearTimeout(layoutTimer);
  layoutTimer = setTimeout(() => save(() => api('PUT', '/layout', { widgets: currentLayout() })), 400);
}

function tileById(id) {
  return grid.getGridItems().find(el => el.dataset.id === id);
}

async function select(id) {
  selected = id;
  for (const el of grid.getGridItems()) el.classList.toggle('selected', el.dataset.id === id);
  const box = $('#widget-config');
  if (!id) {
    box.innerHTML = '<p class="empty">Click a widget on the canvas to configure it.</p>';
    return;
  }
  $('#widget-section').open = true;
  try {
    box.innerHTML = await api('GET', `/widgets/${encodeURIComponent(id)}/config-form`);
  } catch (err) {
    toast(err.message);
  }
}

async function removeWidget(id) {
  const el = tileById(id);
  if (!el || !(await confirmDialog(`Remove ${el.dataset.type} widget?`, 'It disappears from the Kindle on the next refresh.'))) return;
  grid.removeWidget(el); // fires 'removed' -> layout save
  delete configs[id];
  if (selected === id) select(null);
}

function addWidget(type) {
  const ids = grid.getGridItems().map(el => parseInt(el.dataset.id.replace(/\D/g, ''), 10) || 0);
  const id = 'w' + (Math.max(0, ...ids) + 1);
  configs[id] = {};
  const el = makeTile({ id, type });
  el.setAttribute('gs-w', 4);
  el.setAttribute('gs-h', 3);
  grid.el.append(el);
  grid.makeWidget(el);
  if (!el.gridstackNode) return toast('No free space for a 4×3 widget — make room first.');
  updateDims(el);
  // Save now instead of debounced: the config form needs the widget on the server.
  clearTimeout(layoutTimer);
  save(() => api('PUT', '/layout', { widgets: currentLayout() })).then(() => select(id));
}

function initGrid(dash) {
  grid = GridStack.init({
    column: COLS, minRow: ROWS, maxRow: ROWS,
    cellHeight: (512 - 2) / ROWS, margin: 1, float: true,
    resizable: { handles: 'e,se,s' },
  }, '.grid-stack');
  for (const w of dash.widgets) {
    configs[w.id] = w.config;
    const el = makeTile(w);
    grid.el.append(el);
    grid.makeWidget(el);
    updateDims(el);
  }
  grid.on('change', (_e, items) => { items.forEach(i => updateDims(i.el)); saveLayoutSoon(); });
  grid.on('added removed', saveLayoutSoon);

  grid.el.addEventListener('click', (e) => {
    const del = e.target.closest('.tile-delete');
    const tile = e.target.closest('.grid-stack-item');
    if (del && tile) return removeWidget(tile.dataset.id);
    if (tile) select(tile.dataset.id);
  });
  grid.el.addEventListener('keydown', (e) => {
    const tile = e.target.closest('.grid-stack-item');
    if (!tile) return;
    const n = tile.gridstackNode;
    const moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(tile.dataset.id); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); removeWidget(tile.dataset.id); }
    else if (moves[e.key]) {
      e.preventDefault();
      const [dx, dy] = moves[e.key];
      grid.update(tile, {
        x: Math.min(Math.max(n.x + dx, 0), COLS - n.w),
        y: Math.min(Math.max(n.y + dy, 0), ROWS - n.h),
      });
      tile.focus();
    }
  });
}

// ---------- widget config form (autosave on change) ----------
function readForm(form) {
  const config = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    config[el.name] = el.type === 'checkbox' ? el.checked : el.value;
  }
  return config;
}

document.addEventListener('change', (e) => {
  const form = e.target.closest('#widget-form');
  if (!form) return;
  const id = form.dataset.wid;
  save(async () => {
    const res = await api('PATCH', `/widgets/${encodeURIComponent(id)}`, { config: readForm(form) });
    configs[id] = res.config;
  });
});
document.addEventListener('submit', (e) => {
  if (e.target.id === 'widget-form') e.preventDefault();
});
document.addEventListener('click', (e) => {
  const rm = e.target.closest('[data-remove]');
  if (rm) removeWidget(rm.dataset.remove);
  const add = e.target.closest('[data-add]');
  if (add) addWidget(add.dataset.add);
});

// ---------- theme ----------
function applyTheme(theme) {
  $('#theme-preset').value = theme.preset || 'default';
  $('#theme-font').value = theme.font_family || '';
  $('#theme-scale').value = theme.font_scale ?? '';
  for (const seg of document.querySelectorAll('.seg[data-theme-key]')) {
    const v = theme[seg.dataset.themeKey] || '';
    for (const b of seg.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.value === v));
  }
}

function applyDither(value) {
  for (const b of document.querySelectorAll('#dither button')) b.setAttribute('aria-pressed', String(b.dataset.value === value));
}

function patchTheme(partial) {
  save(async () => applyTheme((await api('PATCH', '/theme', partial)).theme));
}

function initTheme() {
  $('#theme-preset').addEventListener('change', e => patchTheme({ preset: e.target.value }));
  $('#theme-font').addEventListener('change', e => patchTheme({ font_family: e.target.value || null }));
  $('#theme-scale').addEventListener('change', e => {
    const v = e.target.value;
    patchTheme({ font_scale: v === '' ? null : Number(v) });
  });
  $('#dither').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (b) save(async () => applyDither((await api('PATCH', '', { dither: b.dataset.value })).dither));
  });
  for (const seg of document.querySelectorAll('.seg[data-theme-key]')) {
    seg.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (b) patchTheme({ [seg.dataset.themeKey]: b.dataset.value || null });
    });
  }
}

// ---------- dashboards: switch, create, delete ----------
$('#dashboard-select')?.addEventListener('change', async (e) => {
  clearTimeout(layoutTimer);
  if (grid && $('#status')?.dataset.state === 'saving') await save(() => api('PUT', '/layout', { widgets: currentLayout() }));
  location.href = '/editor?name=' + encodeURIComponent(e.target.value);
});

for (const btn of document.querySelectorAll('[data-open]')) {
  btn.addEventListener('click', () => { $('#new-error').textContent = ''; $('#' + btn.dataset.open).showModal(); });
}
for (const btn of document.querySelectorAll('[data-close]')) {
  btn.addEventListener('click', () => btn.closest('dialog').close());
}

$('#new-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  if (!form.reportValidity()) return;
  const res = await fetch('/api/dashboards', { method: 'POST', body: new FormData(form) });
  if (res.ok) {
    location.href = '/editor?name=' + encodeURIComponent((await res.json()).name);
  } else {
    let detail = res.statusText;
    try { detail = (await res.json()).detail; } catch {}
    $('#new-error').textContent = typeof detail === 'string' ? detail : 'Invalid name';
  }
});

$('#delete-dashboard')?.addEventListener('click', async () => {
  if (!(await confirmDialog(`Delete “${NAME}”?`, 'The dashboard and its layout are removed permanently.'))) return;
  try {
    await api('DELETE', '');
    location.href = '/editor';
  } catch (err) {
    toast(err.message);
  }
});

// ---------- boot ----------
if (NAME) {
  initTheme();
  api('GET', '').then((dash) => {
    initGrid(dash);
    applyTheme(dash.theme || {});
    applyDither(dash.dither || 'fs');
    refreshRender();
  }).catch(err => toast('Could not load dashboard: ' + err.message));
}
