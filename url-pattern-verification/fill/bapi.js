// Read a page's own list API from inside the page (after the page itself has loaded normally in
// Chromium, so any first-party script checks ran as for a normal visitor). GET only.
// Usage: node bapi.js <page_url> <api_template_with_{p}> <from> <to> <out.json> [--stop-empty 1]
const { chromium } = require('playwright');
const fs = require('fs');
const [pageUrl, tpl, from, to, out] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(pageUrl, { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(3000);
  const res = [];
  for (let p = Number(from); p <= Number(to); p++) {
    const url = tpl.replace('{p}', String(p));
    const r = await page.evaluate(async u => {
      try { const x = await fetch(u, { credentials: 'include' }); return { status: x.status, text: await x.text() }; }
      catch (e) { return { status: null, text: String(e) }; }
    }, url);
    let json = null;
    try { json = JSON.parse(r.text); } catch {}
    res.push({ page: p, url, status: r.status, json, text: json ? undefined : r.text.slice(0, 300) });
    if (!json) break;
    const s = JSON.stringify(json);
    if (!/"(id|_id|Id)"/.test(s)) break;
    await page.waitForTimeout(1200);
  }
  fs.writeFileSync(out, JSON.stringify(res));
  console.log(res.map(r => `${r.page}:${r.status}:${r.json ? JSON.stringify(r.json).length : 'nojson'}`).join(' '));
  await browser.close();
})();
