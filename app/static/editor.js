const dashboardName = document.getElementById('dashboard-select')?.value;
if (dashboardName) {
  document.getElementById('preview-link').href = '/preview/' + dashboardName;
}

const grid = GridStack.init({
  column: 12,
  cellHeight: 512 / 16,
  margin: 2,
  float: true,
  minRow: 16,
}, '.grid-stack');

grid.on('change', (event, items) => {
  for (const item of items) {
    updateTileDims(item.el);
  }
});

function updateTileDims(el) {
  const x = parseInt(el.getAttribute('gs-x'), 10);
  const y = parseInt(el.getAttribute('gs-y'), 10);
  const w = parseInt(el.getAttribute('gs-w'), 10);
  const h = parseInt(el.getAttribute('gs-h'), 10);
  const dims = el.querySelector('.tile-dims');
  if (dims) dims.textContent = `${w} × ${h} @ (${x},${y})`;
}

let nextId = 1;
let selectedWid = null;

function setSelected(wid) {
  selectedWid = wid;
  for (const el of grid.getGridItems()) {
    el.classList.toggle('selected', el.dataset.id === wid);
  }
}

async function loadDashboard() {
  const res = await fetch('/api/dashboards/' + dashboardName);
  if (!res.ok) return;
  const dash = await res.json();
  grid.removeAll();
  for (const w of dash.widgets) {
    const num = parseInt(w.id.replace(/\D/g, ''), 10);
    if (num >= nextId) nextId = num + 1;
    grid.addWidget(buildItem(w));
  }
  applyThemeToUI(dash.theme || {});
}

function buildItem(w) {
  const el = document.createElement('div');
  el.classList.add('grid-stack-item');
  el.dataset.id = w.id;
  el.dataset.type = w.type;
  el.setAttribute('gs-x', w.pos.x);
  el.setAttribute('gs-y', w.pos.y);
  el.setAttribute('gs-w', w.pos.w);
  el.setAttribute('gs-h', w.pos.h);
  const content = document.createElement('div');
  content.classList.add('grid-stack-item-content');

  const head = document.createElement('div');
  head.classList.add('tile-head');
  const typeSpan = document.createElement('span');
  typeSpan.classList.add('tile-type');
  typeSpan.textContent = w.type;
  const idSpan = document.createElement('span');
  idSpan.classList.add('tile-id');
  idSpan.textContent = w.id;
  head.appendChild(typeSpan);
  head.appendChild(idSpan);

  const dims = document.createElement('div');
  dims.classList.add('tile-dims');
  dims.textContent = `${w.pos.w} × ${w.pos.h} @ (${w.pos.x},${w.pos.y})`;

  const delBtn = document.createElement('button');
  delBtn.type = 'button';
  delBtn.classList.add('tile-delete');
  delBtn.title = 'Delete widget';
  delBtn.textContent = '×';
  delBtn.onclick = (e) => {
    e.stopPropagation();
    removeWidget(w.id);
  };

  content.appendChild(head);
  content.appendChild(dims);
  content.appendChild(delBtn);
  content.onclick = () => {
    setSelected(w.id);
    loadConfigForm(w.id);
    loadWidgetPreview(w.id);
  };
  el.appendChild(content);
  return el;
}

function loadConfigForm(wid) {
  htmx.ajax('GET',
    '/api/dashboards/' + dashboardName + '/widgets/' + wid + '/config-form',
    { target: '#widget-config' });
}

function loadWidgetPreview(wid) {
  const iframe = document.getElementById('widget-preview');
  const section = document.getElementById('widget-preview-section');
  iframe.src = `/api/dashboards/${dashboardName}/widgets/${wid}/preview?t=${Date.now()}`;
  section.style.display = '';
}

async function removeWidget(wid) {
  if (!confirm('Delete this widget?')) return;
  const resp = await fetch(`/api/dashboards/${dashboardName}/widgets/${wid}`, { method: 'DELETE' });
  if (!resp.ok) {
    alert('Delete failed: ' + resp.status);
    return;
  }
  const el = grid.getGridItems().find(item => item.dataset.id === wid);
  if (el) grid.removeWidget(el, true);
  if (selectedWid === wid) {
    selectedWid = null;
    document.getElementById('widget-config').innerHTML = '<div class="empty">Select a widget on the canvas.</div>';
    document.getElementById('widget-preview-section').style.display = 'none';
  }
}

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Delete' && e.key !== 'Backspace') return;
  if (!selectedWid) return;
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;
  e.preventDefault();
  removeWidget(selectedWid);
});

window.addWidget = function(type) {
  const id = 'w' + (nextId++);
  const item = buildItem({ id, type, pos: { x: 0, y: 0, w: 4, h: 3 }, config: {} });
  grid.addWidget(item);
  // Persist immediately so the new widget exists for config-form
  saveLayout().then(() => {
    setSelected(id);
    loadConfigForm(id);
    loadWidgetPreview(id);
  });
};

window.saveLayout = async function() {
  const widgets = grid.getGridItems().map(el => ({
    id: el.dataset.id,
    type: el.dataset.type,
    pos: {
      x: parseInt(el.getAttribute('gs-x'), 10),
      y: parseInt(el.getAttribute('gs-y'), 10),
      w: parseInt(el.getAttribute('gs-w'), 10),
      h: parseInt(el.getAttribute('gs-h'), 10),
    },
    config: window._configCache?.[el.dataset.id] || {},
  }));
  // Merge in known configs from server
  const current = await fetch('/api/dashboards/' + dashboardName).then(r => r.ok ? r.json() : { widgets: [] });
  const cfgById = Object.fromEntries(current.widgets.map(w => [w.id, w.config]));
  for (const w of widgets) {
    if (cfgById[w.id]) w.config = cfgById[w.id];
  }
  const resp = await fetch('/api/dashboards/' + dashboardName + '/layout', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ widgets }),
  });
  if (!resp.ok) alert('Save failed: ' + resp.status);
};

// --- Theme picker ---

function applyThemeToUI(theme) {
  const preset = theme.preset || 'default';
  const presetSel = document.getElementById('theme-preset');
  if (presetSel) presetSel.value = preset;
  const fontSel = document.getElementById('theme-font');
  if (fontSel) fontSel.value = theme.font_family || '';
  const scaleInput = document.getElementById('theme-scale');
  if (scaleInput) scaleInput.value = theme.font_scale ?? '';
  setSegActive('theme-border', theme.border_style || '');
  setSegActive('theme-density', theme.density || '');
}

function setSegActive(id, value) {
  const seg = document.getElementById(id);
  if (!seg) return;
  for (const btn of seg.querySelectorAll('button')) {
    btn.classList.toggle('active', btn.dataset.value === value);
  }
}

async function patchTheme(partial) {
  if (!dashboardName) return;
  const resp = await fetch(`/api/dashboards/${dashboardName}/theme`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(partial),
  });
  if (!resp.ok) {
    alert('Theme save failed: ' + resp.status);
    return;
  }
  // Refresh preview if a widget is selected
  if (selectedWid) loadWidgetPreview(selectedWid);
}

function initThemePicker() {
  const presetSel = document.getElementById('theme-preset');
  if (presetSel) presetSel.addEventListener('change', () => patchTheme({ preset: presetSel.value }));

  const fontSel = document.getElementById('theme-font');
  if (fontSel) fontSel.addEventListener('change', () =>
    patchTheme({ font_family: fontSel.value || null }));

  const scaleInput = document.getElementById('theme-scale');
  if (scaleInput) scaleInput.addEventListener('change', () => {
    const v = scaleInput.value;
    patchTheme({ font_scale: v === '' ? null : Number(v) });
  });

  for (const segId of ['theme-border', 'theme-density']) {
    const seg = document.getElementById(segId);
    if (!seg) continue;
    seg.addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn) return;
      const value = btn.dataset.value;
      setSegActive(segId, value);
      const key = segId === 'theme-border' ? 'border_style' : 'density';
      patchTheme({ [key]: value === '' ? null : value });
    });
  }
}

initThemePicker();
loadDashboard();
