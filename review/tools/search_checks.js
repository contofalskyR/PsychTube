const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext();
  await ctx.route(/^https?:\/\/(?!localhost)/, r => r.abort());
  const p = await ctx.newPage(); await p.goto('http://localhost:8765/#home'); await p.waitForSelector('.masthead');
  for (const q of ['placebo', 'neurons', 'history', 'ai', 'is iq real?']) {
    await p.evaluate(q => { location.hash = '#q-' + encodeURIComponent(q); }, q); await p.waitForTimeout(250);
    const r = await p.evaluate(q => { const titles = [...document.querySelectorAll('#main .card .title')].map(t => t.textContent.toLowerCase());
      const ok = titles.filter(t => t.includes(q.replace('?', '').split(' ')[0])).length;
      return { h1: document.querySelector('#main h1').textContent, inputValue: document.getElementById('q').value, firstTitles: titles.slice(0, 3), titlesContainingTerm: ok, of: titles.length }; }, q);
    console.log(q, JSON.stringify(r));
  }
  await b.close();
})();
