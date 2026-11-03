const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext();
  const STUB = `window.YT = { PlayerState: {UNSTARTED:-1, ENDED:0, PLAYING:1, PAUSED:2, BUFFERING:3, CUED:5},
    Player: function (el, opts) { const box = document.getElementById(el); box.innerHTML = '<iframe id="ytstub"></iframe>'; window.__yt = { created: (window.__yt && window.__yt.created || 0) + 1, destroyed: (window.__yt && window.__yt.destroyed) || 0 };
      this.getCurrentTime = () => 300; this.getDuration = () => 3600; this.seekTo = () => {}; this.playVideo = () => {};
      this.destroy = () => { window.__yt.destroyed++; box.innerHTML = ''; };
      setTimeout(() => opts.events.onStateChange({ data: 1 }), 50); } };`;
  await ctx.route('https://www.youtube.com/iframe_api', r => r.fulfill({ contentType: 'application/javascript', body: STUB }));
  await ctx.route(/^https?:\/\/(?!localhost|www\.youtube\.com\/iframe_api)/, r => r.abort());
  const p = await ctx.newPage();
  await p.goto('http://localhost:8765/#v-NNnIGh9g6fA'); await p.waitForSelector('#ytstub');
  const before = await p.evaluate(() => ({ ...window.__yt, iframe: !!document.getElementById('ytstub') }));
  // simulate switching to another tab / locking the phone, then coming back
  await p.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); });
  await p.waitForTimeout(100);
  await p.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange')); });
  await p.waitForTimeout(300);
  const after = await p.evaluate(() => ({ ...window.__yt, iframe: !!document.getElementById('ytstub'), playerBoxHTML: document.getElementById('playerBox').innerHTML.slice(0, 60) }));
  console.log(JSON.stringify({ before, afterTabSwitch: after }));
  // search stemming false positives
  const s = await p.evaluate(() => {
    const out = {};
    for (const q of ['placebo', 'neurons', 'history', 'ai']) {
      location.hash = '#q-' + q;
      const h1 = document.querySelector('#main h1').textContent;
      const titles = [...document.querySelectorAll('#main .card .title')].map(t => t.textContent);
      out[q] = { h1, withTerm: titles.filter(t => t.toLowerCase().includes(q)).length, sample: titles.slice(0, 4) };
    }
    return out;
  });
  console.log(JSON.stringify(s, null, 1));
  await b.close();
})();
