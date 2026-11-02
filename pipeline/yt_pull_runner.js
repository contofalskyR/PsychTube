// Pull many YouTube playlists in full from a youtube.com tab (paste into the console or run with the
// browser tool). Needs pipeline/yt_helpers.js loaded first (window.__playlistFull, window.__gzb64).
//
//   window.__pullStart(pids, {delay: 700})      start (or resume) a background job over these playlist ids
//   window.__pullStatus()                        {queued, done, errors, running, last}
//   window.__pullChunks(300000)                  gzip+base64 of window.__courses2, split into ~300 KB parts
//
// Results live in window.__courses2 = {pid: {title, desc, count, owner, ownerId, items:[...]}} and failures
// in window.__courses2_err = {pid: message}; both survive between calls as long as the tab stays open.
// The job never awaits inside the tool call that starts it, so the call returns at once and the tool's
// timeout does not matter; poll __pullStatus() instead.
(() => {
  const S = (window.__pullState = window.__pullState || { queue: [], running: false, last: null, started: 0 });
  window.__courses2 = window.__courses2 || {};
  window.__courses2_err = window.__courses2_err || {};
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  async function loop(delay) {
    S.running = true;
    while (S.queue.length) {
      const pid = S.queue.shift();
      if (window.__courses2[pid] || window.__courses2_err[pid]) continue;
      try {
        const r = await window.__playlistFull(pid);
        if (!r || !r.items || !r.items.length) window.__courses2_err[pid] = "empty";
        else window.__courses2[pid] = r;
      } catch (e) {
        window.__courses2_err[pid] = String(e && e.message || e);
        if (/LOGIN_REQUIRED|429|bot/i.test(String(e))) { S.running = false; S.last = "stopped: " + String(e); return; }
      }
      S.last = pid;
      await sleep(delay + Math.random() * delay);
    }
    S.running = false;
  }

  window.__pullStart = (pids, opt = {}) => {
    const seen = new Set(S.queue);
    for (const p of pids) if (!seen.has(p) && !window.__courses2[p] && !window.__courses2_err[p]) { S.queue.push(p); seen.add(p); }
    if (!S.running) { S.started = Date.now(); loop(opt.delay || 700); }
    return window.__pullStatus();
  };
  window.__pullStatus = () => ({ queued: S.queue.length, done: Object.keys(window.__courses2).length, errors: Object.keys(window.__courses2_err).length,
    running: S.running, last: S.last, minutes: Math.round((Date.now() - S.started) / 6000) / 10,
    lectures: Object.values(window.__courses2).reduce((a, c) => a + ((c.items || []).length), 0) });
  window.__pullRetryErrors = () => { const e = Object.keys(window.__courses2_err).filter(p => window.__courses2_err[p] !== "empty"); window.__courses2_err = {}; return window.__pullStart(e); };
  window.__pullChunks = async (size = 300000) => {
    const b64 = await window.__gzb64(JSON.stringify({ pulled: new Date().toISOString().slice(0, 10), courses: window.__courses2, errors: window.__courses2_err }));
    const parts = [];
    for (let i = 0; i < b64.length; i += size) parts.push(b64.slice(i, i + size));
    window.__pullParts = parts;
    return { parts: parts.length, bytes: b64.length };
  };
  return "runner ready";
})();
