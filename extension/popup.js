const $ = (id) => document.getElementById(id);

async function refresh() {
  const st = await chrome.runtime.sendMessage({ type: 'getState' });
  const waiting = !!st.waitingForBridge && !st.connected;
  $('dot').className = 'dot ' + (st.connected ? 'ok' : waiting ? 'wait' : 'bad');
  if (st.connected) {
    $('status').textContent = 'Browser session ready';
  } else if (waiting) {
    $('status').textContent = 'Waiting for copilot…';
  } else {
    $('status').textContent = 'Not connected';
  }
  const bits = [];
  if (st.error) bits.push(st.error);
  if (st.current) bits.push(`Running ${st.current.provider} (${st.current.chars || 0} chars)`);
  bits.push(`${st.jobsDone || 0} jobs done`);
  $('detail').textContent = bits.join(' · ');
  $('pause').textContent = st.paused ? 'Resume' : 'Pause';
  $('pause').dataset.paused = st.paused ? '1' : '';
}

(async () => {
  const s = await chrome.storage.local.get(['bridgeUrl', 'token']);
  $('url').value = s.bridgeUrl || 'ws://127.0.0.1:8765';
  $('token').value = s.token || '';
  await chrome.runtime.sendMessage({ type: 'reconnect' });
  refresh();
  setInterval(refresh, 1500);
})();

$('reconnect').onclick = async () => {
  await chrome.runtime.sendMessage({ type: 'reconnect' });
  refresh();
};
$('pause').onclick = async () => {
  await chrome.runtime.sendMessage({ type: 'setPaused', paused: !$('pause').dataset.paused });
  setTimeout(refresh, 200);
};
$('openClaude').onclick = () => chrome.runtime.sendMessage({ type: 'openProvider', provider: 'claude' });
$('openGpt').onclick = () => chrome.runtime.sendMessage({ type: 'openProvider', provider: 'gpt' });
