const dashboardName = document.getElementById('dashboard-select')?.value;
if (dashboardName) {
  document.getElementById('preview-link').href = '/preview/' + dashboardName;
}

const grid = GridStack.init({
  column: 12,
  cellHeight: 1024 / 16,
  margin: 2,
  float: true,
}, '.grid-stack');

let nextId = 1;

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
  content.textContent = w.type + ' (' + w.id + ')';
  content.style.cursor = 'pointer';
  content.onclick = () => loadConfigForm(w.id);
  el.appendChild(content);
  return el;
}

function loadConfigForm(wid) {
  htmx.ajax('GET',
    '/api/dashboards/' + dashboardName + '/widgets/' + wid + '/config-form',
    { target: '#widget-config' });
}

window.addWidget = function(type) {
  const id = 'w' + (nextId++);
  const item = buildItem({ id, type, pos: { x: 0, y: 0, w: 4, h: 3 }, config: {} });
  grid.addWidget(item);
  // Persist immediately so the new widget exists for config-form
  saveLayout().then(() => loadConfigForm(id));
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

loadDashboard();
