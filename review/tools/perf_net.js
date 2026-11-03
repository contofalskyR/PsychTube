// Time-to-content under network + CPU throttling. usage: node perf_net.js <profile> <cpuRate>
const { chromium, devices } = require('playwright');
const PROFILES = {   // Chrome DevTools / Lighthouse presets
  'slow4g': { latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8 },
  'fast4g': { latency: 40, downloadThroughput: 9e6 / 8, uploadThroughput: 1.5e6 / 8 },
  '3g': { latency: 300, downloadThroughput: 750e3 / 8, uploadThroughput: 250e3 / 8 },
};
const prof = process.argv[2] || 'slow4g', rate = +(process.argv[3] || 4);
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['Moto G4'], deviceScaleFactor: 1 });
  await ctx.route(/^https?:\/\/(?!localhost)/, r => r.abort());
  await ctx.addInitScript(() => {
    const mo = new MutationObserver(() => { const m = document.getElementById('main'); if (m && m.children.length) { performance.mark('first-render'); mo.disconnect(); } });
    mo.observe(document, { childList: true, subtree: true });
  });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', { offline: false, ...PROFILES[prof] });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate });
  await page.goto('http://localhost:8766/#home', { waitUntil: 'load', timeout: 120000 });
  const r = await page.evaluate(() => {
    const fcp = (performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime;
    const res = performance.getEntriesByType('resource').find(x => x.name.endsWith('data.js'));
    return { fcpMs: Math.round(fcp), dataJsTransferKB: res && Math.round(res.transferSize / 1024), dataJsDoneMs: res && Math.round(res.responseEnd),
      catalogVisibleMs: Math.round((performance.getEntriesByName('first-render')[0] || {}).startTime) };
  });
  console.log(JSON.stringify({ profile: prof, cpuRate: rate, ...r }));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
