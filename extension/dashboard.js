// Runs on the copilot page in the same Chrome that is logged into ChatGPT or Claude.
// Wakes the extension and connects it to the local bridge — no popup, no pasted token.

const POKE_FAST_MS = 2000;
const POKE_SLOW_MS = 15000;

let pokeTimer = null;

function pokeBridge() {
  chrome.runtime.sendMessage({ type: 'dashboard_open' }, (res) => {
    const err = chrome.runtime.lastError;
    if (err) return;
    const connected = !!(res && res.connected);
    clearTimeout(pokeTimer);
    pokeTimer = setTimeout(pokeBridge, connected ? POKE_SLOW_MS : POKE_FAST_MS);
  });
}

pokeBridge();
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') pokeBridge();
});
