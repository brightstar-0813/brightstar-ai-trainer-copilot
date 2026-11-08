// Service worker: keeps a WebSocket to the local bridge, owns one dedicated
// window/tab per provider, and relays jobs to the content script.
// Connects by itself: reads token from the bridge config HTTP endpoint.
// Opens ChatGPT / Claude the same way Brightstar Bid bot does — reuse a
// logged-in tab, or create one in this Chrome window (side panel Build).

const DEFAULTS = { bridgeUrl: 'ws://127.0.0.1:8765', token: '', apiBase: '' };

try {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
} catch (_) { /* older Chrome */ }
const VERSION = chrome.runtime.getManifest().version;
const CONFIG_POLL_MS = 1500;
const RECONNECT_MS = 2000;

let ws = null;
let reconnectTimer = null;
let configTimer = null;
const state = {
  connected: false,
  error: '',
  current: null,
  paused: false,
  jobsDone: 0,
  waitingForBridge: false,
};
const active = new Map(); // job id -> {provider, tabId}
let selectorsCache = null;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getSettings() {
  const s = await chrome.storage.local.get(['bridgeUrl', 'token', 'tabIds', 'paused']);
  return { ...DEFAULTS, ...s };
}

async function loadSelectors() {
  const stored = await chrome.storage.local.get('selectorsOverride');
  if (stored.selectorsOverride) return stored.selectorsOverride;
  if (!selectorsCache) selectorsCache = await (await fetch(chrome.runtime.getURL('selectors.json'))).json();
  return selectorsCache;
}

function configPorts(settings) {
  const ports = [];
  try {
    const u = new URL((settings.bridgeUrl || DEFAULTS.bridgeUrl).replace(/^ws/, 'http'));
    ports.push(Number(u.port || 8765) + 1);
  } catch (_) { /* ignore */ }
  // Only probe the default copilot port when we still need a first token, or when
  // the stored URL is the default. Avoids clobbering an in-test / custom bridge.
  const hasToken = !!(settings.token && settings.token !== 'change-me');
  const usingDefault = !settings.bridgeUrl || settings.bridgeUrl === DEFAULTS.bridgeUrl;
  if ((!hasToken || usingDefault) && !ports.includes(8766)) ports.push(8766);
  return ports;
}

async function maybeSelfReload(wantVersion) {
  // Bridge advertises the on-disk manifest version. When it differs, reload so
  // Chrome picks up the new files — no chrome://extensions click.
  if (!wantVersion || wantVersion === VERSION) return false;
  if (state.current) return false; // finish the in-flight job first
  const { lastSelfReload = 0 } = await chrome.storage.local.get('lastSelfReload');
  if (Date.now() - lastSelfReload < 20000) return false; // avoid a reload loop
  await chrome.storage.local.set({ lastSelfReload: Date.now() });
  chrome.runtime.reload();
  return true;
}

async function pullConfig() {
  const settings = await getSettings();
  for (const port of configPorts(settings)) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/ext-config`, { cache: 'no-store' });
      if (!res.ok) continue;
      const cfg = await res.json();
      if (!cfg.token || !cfg.bridgeUrl) continue;
      if (await maybeSelfReload(cfg.extensionVersion)) return true;
      const patch = {};
      if (cfg.token !== settings.token) patch.token = cfg.token;
      if (cfg.bridgeUrl !== settings.bridgeUrl) patch.bridgeUrl = cfg.bridgeUrl;
      if (cfg.apiBase && cfg.apiBase !== settings.apiBase) patch.apiBase = cfg.apiBase;
      if (Object.keys(patch).length) await chrome.storage.local.set(patch);
      state.waitingForBridge = false;
      return true;
    } catch (_) { /* try next port */ }
  }
  state.waitingForBridge = true;
  return false;
}

function ensureConfigPoll() {
  if (configTimer) return;
  configTimer = setInterval(async () => {
    // Always poll: picks up token + self-reloads when the on-disk version changes.
    const got = await pullConfig();
    if (state.connected) return;
    // Do not tear down a handshake in flight — that was disconnecting mid-job.
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    if (got) connect({ force: true });
  }, CONFIG_POLL_MS);
}

// ---------------------------------------------------------------- WebSocket
async function connect(opts = {}) {
  const force = !!opts.force;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    if (!force) return;
    // Keep a live socket unless the caller explicitly replaces credentials.
    if (!opts.replace) return;
  }
  if (force && ws) {
    try { ws.onclose = null; ws.close(); } catch (_) { /* ignore */ }
    ws = null;
  }
  await pullConfig();
  const settings = await getSettings();
  state.paused = !!settings.paused;
  if (!settings.token || settings.token === 'change-me') {
    state.connected = false;
    state.error = 'Waiting for the copilot bridge…';
    state.waitingForBridge = true;
    scheduleReconnect();
    return;
  }
  try {
    ws = new WebSocket(settings.bridgeUrl);
  } catch (e) {
    state.error = String(e);
    scheduleReconnect();
    return;
  }
  ws.onopen = () => ws.send(JSON.stringify({
    type: 'hello', role: 'extension', token: settings.token, version: VERSION,
  }));
  ws.onmessage = (ev) => onBridgeMessage(JSON.parse(ev.data));
  ws.onclose = () => {
    state.connected = false;
    if (!state.error || state.error === 'Connected to bridge') {
      state.error = 'Bridge not reachable';
    }
    scheduleReconnect();
  };
  ws.onerror = () => { state.connected = false; };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect({ force: true });
  }, RECONNECT_MS);
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

setInterval(() => send({ type: 'ping' }), 20000);
chrome.alarms.create('jt-keepalive', { periodInMinutes: 0.4 });
chrome.alarms.onAlarm.addListener(() => {
  if (state.connected) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  connect({ force: true });
});

function onBridgeMessage(msg) {
  switch (msg.type) {
    case 'hello_ok':
      state.connected = true;
      state.error = '';
      state.waitingForBridge = false;
      send({ type: 'status', paused: state.paused });
      break;
    case 'open_provider':
      openProviderWindow(msg.provider, msg.url, false);
      break;
    case 'job':
      runJob(msg);
      break;
    case 'cancel': {
      const a = active.get(msg.id);
      if (a) active.delete(msg.id);
      if (state.current && state.current.id === msg.id) state.current = null;
      break;
    }
    default:
  }
}

// ---------------------------------------------------------------- tabs (Brightstar-style session reuse)
async function openProviderWindow(provider, url, focus) {
  const target = url || (provider === 'claude' ? 'https://claude.ai/new' : 'https://chatgpt.com/');
  const tabId = await getProviderTab(provider, target);
  if (focus) {
    const t = await chrome.tabs.get(tabId);
    await chrome.windows.update(t.windowId, { focused: true });
    await chrome.tabs.update(tabId, { active: true });
  }
  return tabId;
}

async function rememberTab(provider, tabId) {
  const { tabIds = {} } = await getSettings();
  tabIds[provider] = tabId;
  await chrome.storage.local.set({ tabIds });
}

function providerUrlPatterns(provider) {
  if (provider === 'claude') return ['https://claude.ai/*'];
  if (provider === 'gpt' || provider === 'chatgpt') {
    return ['https://chatgpt.com/*', 'https://chat.openai.com/*'];
  }
  if (provider === 'mock') return ['http://127.0.0.1:8799/*'];
  return [];
}

async function currentWindowId() {
  try {
    const win = await chrome.windows.getCurrent();
    if (win && typeof win.id === 'number') return win.id;
  } catch (_) { /* no current window */ }
  const all = await chrome.windows.getAll({ windowTypes: ['normal'] });
  return all[0]?.id;
}

async function getProviderTab(provider, url) {
  const { tabIds = {} } = await getSettings();
  const known = tabIds[provider];
  if (known) {
    try {
      const t = await chrome.tabs.get(known);
      if (t) return t.id;
    } catch (_) { /* closed */ }
  }
  const patterns = providerUrlPatterns(provider);
  const windowId = await currentWindowId();
  if (patterns.length) {
    const open = await chrome.tabs.query({ url: patterns });
    // Prefer a tab already in this window (side panel / same profile).
    const preferred = windowId
      ? open.find((t) => t.windowId === windowId) || open[0]
      : open[0];
    if (preferred) {
      await rememberTab(provider, preferred.id);
      return preferred.id;
    }
  }
  if (typeof windowId === 'number') {
    const tab = await chrome.tabs.create({ windowId, url, active: true });
    await rememberTab(provider, tab.id);
    return tab.id;
  }
  // Fallback: open beside the Streamlit dashboard when present.
  const dash = await chrome.tabs.query({
    url: ['http://localhost:8501/*', 'http://127.0.0.1:8501/*'],
  });
  if (dash.length) {
    const tab = await chrome.tabs.create({ windowId: dash[0].windowId, url, active: false });
    await rememberTab(provider, tab.id);
    return tab.id;
  }
  const win = await chrome.windows.create({ url, focused: true, type: 'normal', width: 1100, height: 850 });
  const tabId = win.tabs[0].id;
  await rememberTab(provider, tabId);
  return tabId;
}

/** Bid-bot style: reuse or open ChatGPT/Claude, wait until content script answers. */
async function ensureAiTab(provider, { focus = true } = {}) {
  const p = provider === 'claude' ? 'claude' : 'gpt';
  const url = p === 'claude'
    ? 'https://claude.ai/new'
    : 'https://chatgpt.com/?temporary-chat=true';
  const tabId = await openProviderWindow(p, url, !!focus);
  // Existing ChatGPT tabs often predate an extension reload — navigate so the
  // content script attaches, then inject as a fallback (Bid-bot pattern).
  try {
    await navigate(tabId, url);
  } catch (_) { /* slow SPA; inject path below still helps */ }
  await waitContent(tabId, 45000);
  return tabId;
}

async function injectContent(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content.js'],
    });
    return true;
  } catch (e) {
    state.error = String(e.message || e);
    return false;
  }
}

function waitForComplete(tabId, timeoutMs = 45000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(fn);
      reject(new Error('page load timeout'));
    }, timeoutMs);
    function fn(id, info) {
      if (id === tabId && info.status === 'complete') {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(fn);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(fn);
  });
}

async function navigate(tabId, url) {
  // Always load (or reload) so new_chat clears prior messages on the same URL.
  const loaded = waitForComplete(tabId);
  let tab;
  try { tab = await chrome.tabs.get(tabId); } catch (_) { tab = null; }
  if (tab && (tab.url === url || tab.pendingUrl === url)) {
    await chrome.tabs.reload(tabId);
  } else {
    await chrome.tabs.update(tabId, { url });
  }
  await loaded;
}

async function waitContent(tabId, timeoutMs = 30000) {
  const t0 = Date.now();
  let injected = false;
  while (Date.now() - t0 < timeoutMs) {
    try {
      const r = await chrome.tabs.sendMessage(tabId, { type: 'jt_ping' });
      if (r && r.ok) return r;
    } catch (_) { /* content script not ready */ }
    if (!injected && Date.now() - t0 > 1500) {
      injected = true;
      await injectContent(tabId);
    }
    await sleep(500);
  }
  throw new Error(
    'content script did not respond. Stay on chatgpt.com / claude.ai, reload that tab once, then Build again.'
  );
}

// ---------------------------------------------------------------- jobs
async function runJob(job) {
  const fail = (code, error) => {
    send({ type: 'result', id: job.id, ok: false, code, error });
    finish(job.id);
  };
  try {
    while (state.paused) await sleep(500);
    const selectors = await loadSelectors();
    if (!selectors[job.provider]) return fail('unknown_provider', `no selectors for provider ${job.provider}`);
    const url = job.url || `https://${selectors[job.provider].host}/`;
    const tabId = await getProviderTab(job.provider, url);
    active.set(job.id, { provider: job.provider, tabId });
    state.current = { id: job.id, provider: job.provider, chars: 0 };
    if (job.new_chat) await navigate(tabId, url);
    await waitContent(tabId);
    await chrome.tabs.sendMessage(tabId, { type: 'jt_run', job, selectors: selectors[job.provider] });
  } catch (e) {
    fail('extension_error', String(e.message || e));
  }
}

function finish(id) {
  active.delete(id);
  if (state.current && state.current.id === id) state.current = null;
}

async function resolveApiBase() {
  const settings = await getSettings();
  if (settings.apiBase) return settings.apiBase.replace(/\/$/, '');
  try {
    const u = new URL((settings.bridgeUrl || DEFAULTS.bridgeUrl).replace(/^ws/, 'http'));
    return `http://127.0.0.1:${Number(u.port || 8765) + 1}`;
  } catch (_) {
    return 'http://127.0.0.1:8766';
  }
}

/** Side panel must not fetch localhost directly — proxy through the worker. */
async function apiFetch(path, opts = {}) {
  await pullConfig();
  const settings = await getSettings();
  const base = await resolveApiBase();
  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };
  if (settings.token) headers.Authorization = `Bearer ${settings.token}`;
  let res;
  try {
    res = await fetch(`${base}${path}`, {
      method: opts.method || 'GET',
      headers,
      body: opts.body,
      cache: 'no-store',
    });
  } catch (e) {
    throw new Error(
      'Bridge API not reachable. In the project folder run: jt bridge serve'
    );
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok && !data.error) {
    data.error = `HTTP ${res.status}`;
    data.ok = false;
  }
  return { status: res.status, data };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'jt_result') {
    if (active.has(msg.id)) {
      send({ type: 'result', id: msg.id, ok: msg.ok, text: msg.text, code: msg.code, error: msg.error });
      if (msg.ok) state.jobsDone += 1;
      finish(msg.id);
    }
  } else if (msg.type === 'jt_progress') {
    if (state.current && state.current.id === msg.id) state.current.chars = msg.chars;
    send({ type: 'progress', id: msg.id, chars: msg.chars, started: msg.started });
  } else if (msg.type === 'getState') {
    sendResponse({ ...state });
  } else if (msg.type === 'reconnect') {
    state.error = '';
    connect({ force: true, replace: true }).then(() => sendResponse({ ok: true, connected: state.connected, error: state.error }));
    return true;
  } else if (msg.type === 'setPaused') {
    state.paused = !!msg.paused;
    chrome.storage.local.set({ paused: state.paused });
    send({ type: 'status', paused: state.paused });
  } else if (msg.type === 'openProvider') {
    openProviderWindow(msg.provider, null, true).then(() => sendResponse({ ok: true }));
    return true;
  } else if (msg.type === 'ensureAiTab') {
    ensureAiTab(msg.provider, { focus: msg.focus !== false })
      .then((tabId) => sendResponse({ ok: true, tabId }))
      .catch((e) => sendResponse({ ok: false, error: String(e.message || e) }));
    return true;
  } else if (msg.type === 'api') {
    apiFetch(msg.path, { method: msg.method, body: msg.body, headers: msg.headers })
      .then((r) => sendResponse(r))
      .catch((e) => sendResponse({ status: 0, data: { ok: false, error: String(e.message || e) } }));
    return true;
  } else if (msg.type === 'dashboard_open') {
    // Copilot page is open in this Chrome: wake the worker and attach to the bridge.
    connect({ force: !state.connected }).then(() => sendResponse({
      connected: state.connected,
      error: state.error,
      waitingForBridge: state.waitingForBridge,
    }));
    return true;
  }
  return false;
});

chrome.tabs.onRemoved.addListener((tabId) => {
  for (const [id, a] of active) {
    if (a.tabId === tabId) {
      send({ type: 'result', id, ok: false, code: 'tab_closed', error: 'provider tab was closed' });
      finish(id);
    }
  }
});

chrome.storage.onChanged.addListener((changes) => {
  const tokenChanged = changes.token && changes.token.oldValue !== changes.token.newValue;
  const urlChanged = changes.bridgeUrl && changes.bridgeUrl.oldValue !== changes.bridgeUrl.newValue;
  if (tokenChanged || urlChanged) {
    state.error = '';
    connect({ force: true, replace: true });
  }
});

ensureConfigPoll();
connect({ force: true });
