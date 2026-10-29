// Independent-open check for hash-route URLs: open each URL on its own (fresh page, no click),
// wait for the route to render, and record whether the clicked card's title appears in the
// rendered text. HTTP status alone cannot tell hash routes apart (same shell for every route).
//
// Usage: node hash_verify.js <targets.json> <out.jsonl> [--wait MS]
// targets.json: [{"entry_id", "url", "expect_text"}]
const { chromium } = require('playwright');
const fs = require('fs');

const [targets, out, ...rest] = process.argv.slice(2);
const opt = { wait: 4000 };
for (let i = 0; i < rest.length; i += 2) opt[rest[i].replace(/^--/, '')] = rest[i + 1];

(async () => {
  const T = JSON.parse(fs.readFileSync(targets, 'utf8'));
  const done = new Set(fs.existsSync(out) ? fs.readFileSync(out, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l).url) : []);
  const browser = await chromium.launch();
  for (const t of T) {
    if (done.has(t.url)) continue;
    const page = await browser.newPage();
    const resp = await page.goto(t.url, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => ({ err: String(e) }));
    await page.waitForTimeout(Number(opt.wait));
    const body = (await page.evaluate(() => document.body ? document.body.innerText : '').catch(() => '')).replace(/\s+/g, ' ');
    // card text may mix dates/tags with the title: any 12-character window of it (after a
    // leading 预览 badge) found in the independently opened page counts as the same item
    const text = (t.expect_text || '').replace(/^\s*预览\s*/, '').trim();
    const windows = [];
    for (let i = 0; i + 12 <= Math.min(text.length, 72); i += 4) windows.push(text.slice(i, i + 12));
    const hit = windows.find(w => w.trim().length >= 8 && body.includes(w));
    const probe = hit || windows[0] || '';
    const rec = { entry_id: t.entry_id, url: t.url, observed_at: new Date().toISOString(), method: 'playwright independent open',
      status: resp && resp.status ? resp.status() : null, final_url: page.url(), title: await page.title().catch(() => null),
      expect_probe: probe, found_text: Boolean(hit) };
    fs.appendFileSync(out, JSON.stringify(rec) + '\n');
    await page.close();
  }
  await browser.close();
})();
