// Measures PsychTube's load and render cost under a phone profile with CPU throttling.
// usage: node perf.js <cpuRate> [base]
const { chromium, devices } = require('playwright');
const rate = +(process.argv[2] || 4);
const BASE = process.argv[3] || "http://localhost:8765/";

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['Moto G4'], deviceScaleFactor: 1 });
  // block third-party requests (fonts, thumbnails, players): the sandbox has no network anyway
  await ctx.route(/^https?:\/\/(?!localhost)/, r => r.abort());
  await ctx.addInitScript(() => {
    let _pt;
    Object.defineProperty(window, 'PT', { configurable: true, get() { return _pt; }, set(v) { performance.mark('data-evaluated'); _pt = v; } });
    window.__lt = [];
    try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push(e.duration); }).observe({ type: 'longtask', buffered: true }); } catch (e) {}
    document.addEventListener('DOMContentLoaded', () => {
      const m = document.getElementById('main');
      const mo = new MutationObserver(() => { if (m.children.length) { performance.mark('first-render'); mo.disconnect(); } });
      mo.observe(m, { childList: true });
    });
  });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate });
  await cdp.send('Performance.enable');
  const t0 = Date.now();
  await page.goto(BASE + '#home', { waitUntil: 'load' });
  await page.waitForSelector('.masthead');
  const wall = Date.now() - t0;
  const marks = await page.evaluate(() => {
    const g = n => (performance.getEntriesByName(n)[0] || {}).startTime;
    const res = performance.getEntriesByType('resource').find(r => r.name.endsWith('data.js'));
    return { dataFetched: res && Math.round(res.responseEnd), dataEvaluated: Math.round(g('data-evaluated')), firstRender: Math.round(g('first-render')),
      longTasks: window.__lt.map(Math.round).sort((a, b) => b - a).slice(0, 5), nodes: document.getElementsByTagName('*').length,
      cards: document.querySelectorAll('.card').length, imgs: document.images.length };
  });
  const metrics = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value]));
  console.log(JSON.stringify({ cpuRate: rate, wallMs: wall, ...marks, heapUsedMB: +(metrics.JSHeapUsedSize / 1048576).toFixed(1), heapTotalMB: +(metrics.JSHeapTotalSize / 1048576).toFixed(1), domNodes: metrics.Nodes }));

  const routes = ['#home', '#longs', '#a-brain', '#t-how-the-brain-works', '#courses', '#courses?shelf=all', '#care', '#q-memory', '#s-c-yale-psyc-110-introduction-to-psychology', '#shelf-originals', '#clips'];
  for (const r of routes) {
    const out = await page.evaluate(async (r) => {
      const t = performance.now();
      location.hash = r;
      await new Promise(res => requestAnimationFrame(() => requestAnimationFrame(res)));
      const ms = Math.round(performance.now() - t);
      return { route: r, renderMs: ms, nodes: document.getElementsByTagName('*').length, cards: document.querySelectorAll('.card').length, imgs: document.images.length, htmlKB: Math.round(document.getElementById('main').innerHTML.length / 1024) };
    }, r);
    const m2 = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value]));
    out.heapMB = +(m2.JSHeapUsedSize / 1048576).toFixed(1);
    console.log(JSON.stringify(out));
  }
  // search typing cost: one keystroke after debounce
  const st = await page.evaluate(async () => {
    const q = document.getElementById('q'); const ts = [];
    for (const term of ['me', 'mem', 'memo', 'memory', 'ai', 'replication crisis']) {
      const t = performance.now(); q.value = term; q.dispatchEvent(new Event('input'));
      await new Promise(r => setTimeout(r, 260));
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      ts.push([term, Math.round(performance.now() - t - 220), document.querySelectorAll('#main .card').length]);
    }
    return ts;
  });
  console.log(JSON.stringify({ searchKeystrokeMs: st }));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
