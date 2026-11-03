// Browser identity check: open each URL on its own page and record status, final URL and title.
// For sites that answer plain HTTP clients with a script check (the browser runs it as a
// normal visitor would). Appends to fill/identity-cache.jsonl with method "browser".
// Usage: node bident.js <urls.json>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const urls = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const cache = path.join(__dirname, 'identity-cache.jsonl');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  for (const u of urls) {
    const page = await ctx.newPage();
    let status = null, err = null;
    const resp = await page.goto(u, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(e => { err = String(e).slice(0, 120); });
    if (resp) status = resp.status();
    await page.waitForTimeout(2500);
    const title = await page.title().catch(() => null);
    const rec = { url: u, observed_at: new Date().toISOString(), method: 'browser', status, final_url: page.url(),
      title: title ? title.slice(0, 120) : null, content_type: 'text/html', error: err };
    fs.appendFileSync(cache, JSON.stringify(rec) + '\n');
    console.log(status, (title || '').slice(0, 40), u.slice(0, 90));
    await page.close();
    await new Promise(r => setTimeout(r, 1200));
  }
  await browser.close();
})();
