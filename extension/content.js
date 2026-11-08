// Content script for claude.ai, chatgpt.com (and the local mock chat page).
// Receives {type:'jt_run', job, selectors}, types the prompt, waits for the reply, and
// reports back to the service worker with {type:'jt_result'}.
(() => {
  if (window.__jtLoaded) return;
  window.__jtLoaded = true;

  const host = location.hostname;
  const PROVIDER = host.endsWith('claude.ai') ? 'claude'
    : host.endsWith('chatgpt.com') ? 'gpt'
    : host === '127.0.0.1' ? 'mock' : null;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);

  function qs(list, root = document) {
    for (const s of list || []) {
      try { const el = root.querySelector(s); if (el) return el; } catch (_) { /* bad selector */ }
    }
    return null;
  }
  function qsa(list, root = document) {
    for (const s of list || []) {
      try { const els = root.querySelectorAll(s); if (els.length) return [...els]; } catch (_) { /* bad selector */ }
    }
    return [];
  }
  function visibleBtn(list) {
    for (const s of list || []) {
      try {
        for (const el of document.querySelectorAll(s)) if (visible(el)) return el;
      } catch (_) { /* bad selector */ }
    }
    return null;
  }
  function buttonByText(patterns) {
    const res = (patterns || []).map((p) => new RegExp(p, 'i'));
    for (const b of document.querySelectorAll('button')) {
      if (!visible(b)) continue;
      const t = (b.innerText || b.getAttribute('aria-label') || '').trim();
      if (t && res.some((r) => r.test(t))) return b;
    }
    return null;
  }

  // ---- DOM -> markdown (keeps fenced code blocks intact so JSON survives) --------------
  const BLOCK = new Set(['p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'table', 'blockquote']);
  function md(node) {
    if (node.nodeType === 3) return node.textContent;
    if (node.nodeType !== 1) return '';
    const tag = node.tagName.toLowerCase();
    if (['button', 'svg', 'style', 'script', 'textarea'].includes(tag)) return '';
    if (tag === 'pre') {
      const code = node.querySelector('code');
      let lang = '';
      const m = code && /language-([\w-]+)/.exec(code.className || '');
      if (m) lang = m[1];
      const txt = (code || node).textContent.replace(/\n$/, '');
      return '\n```' + lang + '\n' + txt + '\n```\n';
    }
    if (tag === 'br') return '\n';
    let out = '';
    for (const c of node.childNodes) out += md(c);
    if (tag === 'code') return '`' + out + '`';
    if (/^h[1-6]$/.test(tag)) return '\n' + '#'.repeat(+tag[1]) + ' ' + out.trim() + '\n';
    if (tag === 'li') return '\n- ' + out.trim();
    if (tag === 'strong' || tag === 'b') return '**' + out + '**';
    if (BLOCK.has(tag)) return '\n' + out + '\n';
    return out;
  }
  const toMarkdown = (el) => md(el).replace(/\n{3,}/g, '\n\n').trim();

  // ---- typing into the editor --------------------------------------------------------
  const norm = (s) => s.replace(/\s+/g, '');

  async function setEditorText(editor, text) {
    editor.focus();
    if (editor.tagName === 'TEXTAREA' || editor.tagName === 'INPUT') {
      const proto = editor.tagName === 'TEXTAREA' ? HTMLTextAreaElement : HTMLInputElement;
      Object.getOwnPropertyDescriptor(proto.prototype, 'value').set.call(editor, text);
      editor.dispatchEvent(new Event('input', { bubbles: true }));
      return;
    }
    const current = () => norm(editor.innerText || editor.textContent || '');
    const want = norm(text).length;
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editor);
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand('delete', false, null);
    document.execCommand('insertText', false, text);
    await sleep(300);
    if (current().length >= want * 0.97) return;
    // Fallback: synthetic paste, which ProseMirror-based editors handle natively.
    editor.focus();
    const range2 = document.createRange();
    range2.selectNodeContents(editor);
    sel.removeAllRanges();
    sel.addRange(range2);
    document.execCommand('delete', false, null);
    const dt = new DataTransfer();
    dt.setData('text/plain', text);
    editor.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    await sleep(500);
    if (current().length < want * 0.9) throw new Error('could not insert prompt text into the editor');
  }

  // ---- helpers over page state -------------------------------------------------------
  function limitHit(sel) {
    const pats = (sel.limit_patterns || []).map((p) => new RegExp(p, 'i'));
    for (const a of qsa(sel.alerts)) {
      const t = a.innerText || '';
      if (t && pats.some((r) => r.test(t))) return t.trim().slice(0, 200);
    }
    return null;
  }

  /** True when the assistant text already contains parseable ```json … ``` (or a root object). */
  function looksCompleteJson(text) {
    if (!text || text.length < 40) return false;
    const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
    const raw = fence ? fence[1] : (text.match(/(\{[\s\S]*\})\s*$/) || [])[1];
    if (!raw) return false;
    try {
      const v = JSON.parse(raw.trim());
      return v && typeof v === 'object';
    } catch (_) {
      return false;
    }
  }

  async function runJob(job, sel) {
    const progress = (extra) => chrome.runtime.sendMessage({ type: 'jt_progress', id: job.id, ...extra }).catch(() => {});
    const timeoutMs = (job.timeout || 300) * 1000;
    const t0 = Date.now();

    // 1. editor
    let editor = null;
    for (let i = 0; i < 60 && !(editor = qs(sel.editor)); i++) await sleep(500);
    if (!editor) {
      const e = new Error(`editor not found on ${location.href} (not logged in, or selectors changed)`);
      e.code = /login|auth/.test(location.href) ? 'not_logged_in' : 'no_editor';
      throw e;
    }

    const assistants = () => qsa(sel.assistant_message);
    const users = () => qsa(sel.user_message);
    let beforeCount = assistants().length;
    let beforeText = beforeCount ? assistants()[beforeCount - 1].innerText : '';
    const beforeUsers = users().length;

    // 2. type + send
    await setEditorText(editor, job.prompt);
    let sent = false;
    for (let attempt = 0; attempt < 5 && !sent; attempt++) {
      await sleep(400);
      const btn = visibleBtn(sel.send_button);
      if (btn && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true') btn.click();
      else editor.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
      await sleep(1200);
      const editorEmpty = norm(editor.innerText || editor.value || '').length < 5;
      sent = users().length > beforeUsers || editorEmpty || !!visibleBtn(sel.stop_button);
    }
    if (!sent) throw Object.assign(new Error('prompt was typed but could not be sent'), { code: 'send_failed' });

    // 3. wait for the reply to finish
    const parts = [];
    let lastText = '';
    let stableSince = Date.now();
    let started = false;
    let lastProgress = 0;
    while (Date.now() - t0 < timeoutMs) {
      await sleep(600);
      const msgs = assistants();
      const last = msgs[msgs.length - 1];
      const text = last ? toMarkdown(last) : '';
      const changedMsg = msgs.length > beforeCount || (last && last.innerText !== beforeText);
      if (changedMsg && text) started = true;
      if (text !== lastText) { lastText = text; stableSince = Date.now(); }

      if (Date.now() - lastProgress > 5000) { lastProgress = Date.now(); progress({ chars: text.length, started }); }

      const limit = limitHit(sel);
      if (limit && (!started || text.length < 200)) throw Object.assign(new Error('usage limit: ' + limit), { code: 'usage_limit' });

      // Stop button = hard streaming. Sticky .result-streaming alone must not block forever
      // (ChatGPT often leaves that class after the JSON is already on screen).
      const hardStreaming = !!visibleBtn(sel.stop_button);
      const softStreaming = qs(sel.streaming) !== null;
      if (!started) continue;
      if (hardStreaming) continue;
      const jsonDone = looksCompleteJson(text);
      const needStable = jsonDone ? 1500 : (softStreaming ? 4500 : 2500);
      if (Date.now() - stableSince < needStable) continue;

      const cont = buttonByText(sel.continue_text);
      if (cont) {
        parts.push(text);
        cont.click();
        beforeCount = msgs.length;
        beforeText = last ? last.innerText : '';
        started = false;
        lastText = '';
        stableSince = Date.now();
        continue;
      }
      parts.push(text);
      // join continuation parts; a part that extends the previous one replaces it
      const out = [];
      for (const p of parts) {
        if (out.length && p.startsWith(out[out.length - 1])) out[out.length - 1] = p; else out.push(p);
      }
      return out.join('\n');
    }
    throw Object.assign(new Error('timed out waiting for the reply'), { code: 'timeout' });
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === 'jt_ping') {
      sendResponse({ ok: true, provider: PROVIDER, url: location.href });
      return false;
    }
    if (msg.type === 'jt_run') {
      sendResponse({ started: true });
      runJob(msg.job, msg.selectors)
        .then((text) => chrome.runtime.sendMessage({ type: 'jt_result', id: msg.job.id, ok: true, text }))
        .catch((e) => chrome.runtime.sendMessage({
          type: 'jt_result', id: msg.job.id, ok: false, code: e.code || 'content_error', error: String(e.message || e),
        }));
      return false;
    }
    return false;
  });
})();
