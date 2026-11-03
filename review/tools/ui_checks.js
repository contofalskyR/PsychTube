// Verifies suspected UI bugs in a real browser. usage: node uicheck.js
const { chromium } = require('playwright');
const BASE = 'http://localhost:8765/';
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route(/^https?:\/\/(?!localhost)/, r => r.abort());
  const page = await ctx.newPage();
  const errors = [], dialogs = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('dialog', d => { dialogs.push(d.message()); d.dismiss(); });
  const go = async h => { await page.evaluate(h => { location.hash = h; }, h); await page.waitForTimeout(150); };
  await page.goto(BASE + '#home'); await page.waitForSelector('.masthead');
  const out = {};

  // 1. clips page: nested/unclosed thumb markup
  await go('#clips');
  out.clips = await page.evaluate(() => { const a = document.querySelector('.row-item a.thumb'); return a ? { nestedThumbDiv: !!a.querySelector('div.thumb'), outer: a.outerHTML.slice(0, 160) } : null; });

  // 2. shelf status chip link -> care page
  await go('#shelf-originals');
  const href = await page.evaluate(() => { const a = document.querySelector('.shelf-foot a.status'); return a && a.getAttribute('href'); });
  await go(href);
  out.shelfStatusLink = { href, findingsShown: await page.evaluate(() => document.querySelectorAll('.care-list').length), pressed: await page.evaluate(() => [...document.querySelectorAll('.seg [aria-pressed="true"]')].map(x => x.textContent)) };

  // 3. skip link from a watch page
  await go('#v-IGQmdoK_ZfY');
  const before = await page.evaluate(() => location.hash);
  await page.keyboard.press('Tab'); // focus skip link (first focusable)
  const focused = await page.evaluate(() => document.activeElement.className + ' ' + document.activeElement.getAttribute('href'));
  await page.keyboard.press('Enter'); await page.waitForTimeout(200);
  out.skipLink = { focused, before, after: await page.evaluate(() => location.hash), onHome: await page.evaluate(() => !!document.querySelector('.masthead')) };

  // 4. home canon row vs canon page
  await go('#home');
  const homeCanon = await page.evaluate(() => { const s = [...document.querySelectorAll('.section')].find(x => /The canon/.test(x.querySelector('h2')?.textContent || '')); return s ? [...s.querySelectorAll('.card')].map(c => c.dataset.id) : []; });
  await go('#canon');
  const pageCanon = await page.evaluate(() => [...document.querySelectorAll('.card')].slice(0, 12).map(c => c.dataset.id));
  out.canon = { overlap: homeCanon.filter(x => pageCanon.includes(x)).length, homeFirst: homeCanon.slice(0, 3), pageFirst: pageCanon.slice(0, 3) };

  // 5. "N vouches" on a video nobody recommended (nrec 0, 10 references)
  await go('#q-Capuchin monkey fairness');
  out.vouchCount = await page.evaluate(() => { const c = [...document.querySelectorAll('.card')].find(c => c.dataset.id === '-KSryJXDpZo'); return c && c.querySelector('.vouch').textContent.trim(); });

  // 6. Debunk tag on a replicated finding
  await go('#q-How Goals Erase Framing Effects');
  out.debunk = await page.evaluate(() => { const c = [...document.querySelectorAll('.card')].find(c => c.dataset.id === '0NM-oLagC1c'); return c && (c.querySelector('.tag') || {}).textContent; });

  // 7. malformed percent-escape in the hash
  errors.length = 0;
  await page.evaluate(() => { location.hash = '#q-%E0%A4%A'; }); await page.waitForTimeout(200);
  out.malformedHash = { errors: errors.slice(), mainText: await page.evaluate(() => document.getElementById('main').textContent.slice(0, 60)) };

  // 8. numeric channel names on a course page
  await go('#s-c-neuroscience-of-human-movement');
  out.numericChannel = await page.evaluate(() => [...document.querySelectorAll('.lectures li')].slice(0, 1).map(li => li.textContent.replace(/\s+/g, ' ').slice(0, 80)));
  await go('#v-wlIwaE1Qm3M');
  out.numericChannelWatch = await page.evaluate(() => document.querySelector('.meta span') && document.querySelector('.meta span').textContent);

  // 9. third-party video shown as an institution's lecture
  await go('#v-rhgwIhB58PA');
  out.veritasium = await page.evaluate(() => { const b = document.querySelector('.box.inst'); return b && b.textContent.replace(/\s+/g, ' ').slice(0, 220); });
  await go('#v-t6RCTP4fc9Q');
  out.hubermanInStanford = await page.evaluate(() => { const b = document.querySelector('.box.inst'); return b && b.textContent.replace(/\s+/g, ' ').slice(0, 200); });

  // 10. hash-route injection attempts
  errors.length = 0;
  for (const h of ['#q-<img src=x onerror=alert(1)>', '#q-"><svg onload=alert(2)>', '#t-memory?sort="><img src=x onerror=alert(3)>', '#v-<img src=x onerror=alert(4)>', '#courses?shelf=<img src=x onerror=alert(5)>&level="><b>x', '#care?status="><img src=x onerror=alert(6)>', '#pathways?p=<img src=x onerror=alert(7)>', '#s-<img src=x onerror=alert(8)>']) {
    await go(h);
  }
  await page.waitForTimeout(300);
  out.injection = { dialogs: dialogs.slice(), injectedImgs: await page.evaluate(() => document.querySelectorAll('img[src="x"]').length) };

  // 11. focus after route change
  await go('#home');
  await page.focus('.rail a[data-nav="topics"]'); await page.keyboard.press('Enter'); await page.waitForTimeout(200);
  out.focusAfterNav = await page.evaluate(() => ({ tag: document.activeElement.tagName, cls: document.activeElement.className, text: (document.activeElement.textContent || '').trim().slice(0, 20) }));

  // 12. segmented control as role=button link: does Space activate it?
  await go('#t-memory');
  await page.focus('.seg a.segbtn:nth-child(3)');
  const h0 = await page.evaluate(() => location.hash);
  await page.keyboard.press('Space'); await page.waitForTimeout(200);
  out.segSpace = { before: h0, after: await page.evaluate(() => location.hash), scrolled: await page.evaluate(() => window.scrollY) };

  // 13. "Clear history" also wipes lecture progress
  await page.evaluate(() => { localStorage.setItem('pt:progress', JSON.stringify({ 'IGQmdoK_ZfY': { t: 30, d: 90, done: false, ts: Date.now() } })); localStorage.setItem('pt:history', JSON.stringify([{ id: 'IGQmdoK_ZfY', ts: Date.now() }])); });
  await page.goto(BASE + '?r=1#home'); await page.waitForSelector('.masthead');
  await go('#history');
  await page.click('#clearBtn'); await page.waitForTimeout(200);
  out.clearHistory = { progressAfter: await page.evaluate(() => localStorage.getItem('pt:progress')), confirmAsked: dialogs.length };

  // 14. theme flash: light setting, what does the first paint use?
  await page.evaluate(() => localStorage.setItem('pt:settings', JSON.stringify({ theme: 'light' })));
  const p2 = await ctx.newPage();
  await p2.route('**/data.js', async r => { await new Promise(res => setTimeout(res, 1500)); r.continue(); });
  await p2.goto(BASE + '#home', { waitUntil: 'commit' });
  await p2.waitForTimeout(500);
  out.themeFlash = await p2.evaluate(() => ({ dataTheme: document.documentElement.getAttribute('data-theme'), bodyBg: getComputedStyle(document.body).backgroundColor, mainEmpty: !document.getElementById('main') || !document.getElementById('main').children.length }));
  await p2.close();

  // 15. ArrowRight on a focused <video> (archive.org lecture) is hijacked
  await page.evaluate(() => localStorage.removeItem('pt:settings'));
  await page.goto(BASE + '?r=2#home'); await page.waitForSelector('.masthead');
  const arch = await page.evaluate(() => (window.PT.videos.find(v => v.p === 'archive' && v.f) || {}).id);
  await go('#v-' + arch);
  await page.waitForSelector('video#player');
  await page.focus('video#player');
  await page.keyboard.press('ArrowRight'); await page.waitForTimeout(100);
  out.videoArrow = await page.evaluate(() => ({ active: document.activeElement.tagName + '.' + document.activeElement.className }));

  out.pageErrors = errors;
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
