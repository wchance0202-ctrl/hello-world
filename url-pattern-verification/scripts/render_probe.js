// Rendered-DOM probe (Playwright, pre-installed Chromium). Read-only interactions only:
// scroll, and click buttons whose text is "load more"/"show more"/"more posts"/"see more".
// Records anchors after each round, the XHR/fetch requests the page itself made
// (method + URL, no bodies or headers), and stops when a round adds no new anchors.
//
// Usage: node render_probe.js <url> <out.json> [--rounds N] [--prefix /path/] [--selector CSS]
// --selector clicks that element each round instead of matching button text.
// --api SUBSTR records, for responses whose URL contains SUBSTR, the full request URL and
//   the JSON top-level keys plus any numeric total/count fields (no bodies kept).
// --hide CSS hides overlays (e.g. a consent banner) with a style rule; nothing is clicked on them.
const { chromium } = require('playwright');
const fs = require('fs');

const [url, out, ...rest] = process.argv.slice(2);
const opt = { rounds: 30, prefix: null, selector: null, hide: null, api: null };
for (let i = 0; i < rest.length; i += 2) opt[rest[i].replace(/^--/, '')] = rest[i + 1];
const MORE = /^(load more|show more|more posts|see more|view more|load more articles)$/i;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ userAgent:
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36' });
  const requests = [];
  page.on('request', r => { if (['xhr', 'fetch'].includes(r.resourceType()))
    requests.push({ method: r.method(), url: r.url().slice(0, 400) }); });
  const api = [];
  page.on('response', async r => {
    if (!opt.api || !r.url().includes(opt.api)) return;
    try {
      const j = await r.json();
      const nums = {};
      const walk = (o, path, depth) => { if (!o || typeof o !== 'object' || depth > 2) return;
        for (const [k, v] of Object.entries(o)) {
          if (typeof v === 'number' && /total|count|offset|limit|page|hits/i.test(k)) nums[path + k] = v;
          else if (v && typeof v === 'object' && !Array.isArray(v)) walk(v, path + k + '.', depth + 1);
        } };
      walk(j, '', 0);
      const arr = Array.isArray(j) ? j : Object.values(j).find(Array.isArray) || [];
      api.push({ url: r.url(), status: r.status(), keys: Array.isArray(j) ? ['<array>'] : Object.keys(j), numbers: nums, items: arr.length });
    } catch (e) { api.push({ url: r.url(), status: r.status(), error: String(e).slice(0, 120) }); }
  });
  const startedAt = new Date().toISOString();
  const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => ({ err: String(e) }));
  if (opt.hide) await page.addStyleTag({ content: `${opt.hide} { display: none !important; }` }).catch(() => {});
  const anchors = async () => page.$$eval('a[href]', as => as.map(a => ({
    href: a.href, text: (a.innerText || '').trim().slice(0, 120),
    region: (a.closest('header,nav,footer,aside,main') || {}).tagName || 'BODY' })));
  const rounds = [];
  let seen = new Set();
  for (let i = 0; i < Number(opt.rounds); i++) {
    const as = await anchors();
    const fresh = as.filter(a => !seen.has(a.href) && (!opt.prefix || new URL(a.href).pathname.startsWith(opt.prefix)));
    fresh.forEach(a => seen.add(a.href));
    as.forEach(a => seen.add(a.href));
    rounds.push({ round: i, anchors: as.length, new_in_prefix: fresh.length });
    if (i > 0 && fresh.length === 0 && !(opt.selector && rounds[i - 1].clicked === opt.selector)) break;
    let clicked = null;
    if (opt.selector) {
      const b = await page.$(opt.selector);
      if (b && await b.isVisible().catch(() => false)) {
        await b.scrollIntoViewIfNeeded().catch(() => {});
        await b.click({ timeout: 10000 }).then(() => { clicked = opt.selector; }).catch(e => { clicked = 'click-failed: ' + String(e).slice(0, 120); });
      }
    }
    const btns = opt.selector ? [] : await page.$$('button, a[role=button], div[role=button], a, div.loadmore, span');
    for (const b of btns) {
      const t = ((await b.innerText().catch(() => '')) || '').trim();
      if (MORE.test(t) && await b.isVisible().catch(() => false)) { await b.click().catch(() => {}); clicked = t; break; }
    }
    await page.mouse.wheel(0, 20000);
    await page.waitForTimeout(2500);
    rounds[rounds.length - 1].clicked = clicked;
    if (!clicked && i > 2 && fresh.length === 0) break;
  }
  const final = await anchors();
  const result = {
    url, observed_at: startedAt, method: 'playwright-chromium', final_url: page.url(),
    status: resp && resp.status ? resp.status() : null, error: resp && resp.err || null,
    title: await page.title(), h1: await page.$eval('h1', h => h.innerText.trim()).catch(() => null),
    rounds, requests, api, anchors: final,
  };
  fs.writeFileSync(out, JSON.stringify(result, null, 1));
  console.log(JSON.stringify({ url, status: result.status, title: result.title,
    anchors: final.length, rounds: rounds.length, xhr: requests.length }));
  await browser.close();
})();
