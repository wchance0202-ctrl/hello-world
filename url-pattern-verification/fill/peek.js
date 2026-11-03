// Quick read-only look at one page in Chromium: title, final URL, main-content anchors grouped by
// URL structure, visible pagination / load-more controls, and the page's own XHR/fetch URLs.
// Optionally clicks a control by its visible text N times (e.g. 加载更多, 下一页) — display
// controls only; never forms. Default Playwright UA (HeadlessChrome), no disguise.
//
// Usage: node peek.js <url> [--wait MS] [--click TEXT] [--times N] [--scroll N] [--out file.json]
const { chromium } = require('playwright');
const fs = require('fs');

const [url, ...rest] = process.argv.slice(2);
const opt = { wait: 4000, click: null, times: 0, scroll: 2, out: null, all: null, pagenums: 0, next: null, maxpages: 60 };
for (let i = 0; i < rest.length; i += 2) opt[rest[i].replace(/^--/, '')] = rest[i + 1];

function key(u) {
  let p;
  try { p = new URL(u); } catch { return null; }
  const segs = p.pathname.split('/').filter(Boolean);
  const out = segs.map((s, i) => {
    const last = i === segs.length - 1;
    const m = last ? s.match(/^(.*?)(\.[a-z0-9]+)?$/i) : [s, s, ''];
    const stem = m[1], ext = m[2] || '';
    if (/^[0-9]+$/.test(stem)) return '{n}' + ext;
    if (last || /^[0-9a-f]{12,}$/i.test(stem)) return '{x}' + ext;
    return s;
  });
  let k = p.host + '/' + out.join('/') + (p.pathname.endsWith('/') && segs.length ? '/' : '');
  if (p.search) k += '?' + p.search.slice(1).split('&').map(kv => kv.split('=')[0] + (kv.includes('=') ? '={v}' : '')).join('&');
  if (/^#!?\//.test(p.hash)) k += p.hash.replace(/=[^&]*/g, '={v}');
  return k;
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const xhr = new Set();
  page.on('request', r => { if (['xhr', 'fetch'].includes(r.resourceType())) xhr.add(r.method() + ' ' + r.url().slice(0, 200)); });
  const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => ({ err: String(e) }));
  await page.waitForTimeout(Number(opt.wait));
  for (let i = 0; i < Number(opt.scroll); i++) { await page.mouse.wheel(0, 4000); await page.waitForTimeout(800); }
  const clicks = [];
  for (let i = 0; i < Number(opt.times); i++) {
    const el = page.getByText(opt.click, { exact: true }).last();
    const ok = await el.click({ timeout: 6000 }).then(() => true).catch(() => false);
    clicks.push(ok);
    if (!ok) break;
    await page.waitForTimeout(2500);
  }
  const collect = () => page.evaluate(() => [...document.querySelectorAll('a[href]')]
    .filter(a => !a.closest('header,nav,footer,aside,[role=navigation],[role=banner],[role=contentinfo]'))
    .map(a => ({ href: a.href, text: (a.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40), region: 'main' })));
  const acc = new Map();
  const pageLog = [];
  if (Number(opt.pagenums) || opt.next) {
    for (const a of await collect()) acc.set(a.href, a);
    for (let i = 2; i <= (opt.next ? Number(opt.maxpages) : Number(opt.pagenums)); i++) {
      const before = acc.size;
      const target = opt.next ? page.getByText(opt.next, { exact: true }).last() : page.getByText(String(i), { exact: true }).last();
      const ok = await target.click({ timeout: 6000 }).then(() => true).catch(() => false);
      if (!ok) { pageLog.push(`p${i}:noclick`); break; }
      await page.waitForTimeout(2500);
      for (const a of await collect()) acc.set(a.href, a);
      pageLog.push(`p${i}:+${acc.size - before}`);
      if (opt.next && acc.size === before) break;
    }
    console.log('pages:', pageLog.join(' '));
  }
  const data = await page.evaluate(() => {
    const region = el => el.closest('header,nav,footer,aside,[role=navigation],[role=banner],[role=contentinfo]') ? 'chrome' : 'main';
    const as = [...document.querySelectorAll('a[href]')].map(a => ({ href: a.href, text: (a.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40), region: region(a) }));
    const ctrls = [...document.querySelectorAll('a,button,span,div,li')].filter(e => e.children.length === 0)
      .map(e => (e.innerText || '').trim()).filter(t => /^(下一页|加载更多|查看更多|更多|load more|show more|more|next|›|»|>|\d{1,3})$/i.test(t));
    return { as, ctrls: [...new Set(ctrls)].slice(0, 30), h1: (document.querySelector('h1') || {}).innerText || null };
  });
  const groups = {};
  for (const a of acc.size ? [...acc.values(), ...data.as] : data.as) {
    if (a.region !== 'main' || !/^https?:/.test(a.href)) continue;
    const k = key(a.href.split('#')[0] === a.href ? a.href : (/#!?\//.test(new URL(a.href).hash) ? a.href : a.href.split('#')[0]));
    if (!k) continue;
    (groups[k] = groups[k] || new Map()).set(a.href, a.text);
  }
  const res = { url, status: resp && resp.status ? resp.status() : null, error: resp && resp.err || null, final: page.url(),
    title: await page.title(), h1: data.h1, clicks, ctrls: data.ctrls,
    groups: Object.entries(groups).sort((a, b) => b[1].size - a[1].size).map(([k, m]) => ({ key: k, n: m.size, samples: [...m].slice(0, opt.all ? 9999 : 3) })),
    xhr: [...xhr].slice(0, 40) };
  if (opt.out) fs.writeFileSync(opt.out, JSON.stringify(res, null, 1));
  console.log(`${res.status} ${res.final} | ${res.title} | h1=${(res.h1 || '').slice(0, 40)} | clicks=${JSON.stringify(clicks)}`);
  console.log('ctrls:', JSON.stringify(res.ctrls));
  for (const g of res.groups.slice(0, 14)) console.log(`  ${String(g.n).padStart(4)} ${g.key.slice(0, 100)}  e.g. ${g.samples[0][0].slice(0, 100)} [${g.samples[0][1]}]`);
  console.log('xhr:', res.xhr.filter(x => !/\.(js|css|png|jpg|svg|woff)/.test(x)).slice(0, 12).join('\n     '));
  await browser.close();
})();
