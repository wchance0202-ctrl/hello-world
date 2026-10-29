// Click probe for pages whose items are not <a href> links (cards opened by script, hash routes).
// Read-only: opens the page, finds clickable content cards in the main area (cursor:pointer,
// visible, with text; header/nav/footer excluded; login/download/contact/submit texts skipped),
// then for each card (fresh page load each time) clicks it once and records where it lands:
// same-tab navigation, hash-route change, or a new tab. Nothing is typed or submitted.
//
// Usage: node click_probe.js <url> <out.json> [--max N] [--wait MS] [--hide CSS]
const { chromium } = require('playwright');
const fs = require('fs');

const [url, out, ...rest] = process.argv.slice(2);
const opt = { max: 12, wait: 4000, hide: null };
for (let i = 0; i < rest.length; i += 2) opt[rest[i].replace(/^--/, '')] = rest[i + 1];
const SKIP = /登录|注册|下载|联系|咨询|提交|购买|立即|申请|试用|预约|sign ?in|log ?in|register|download|contact|submit|buy|subscribe|apply|demo/i;

async function cards(page) {
  return page.$$eval('*', (els, skip) => {
    const re = new RegExp(skip, 'i');
    const out = [];
    const seen = new Set();
    for (const el of els) {
      if (el.closest('header,nav,footer')) continue;
      const cs = getComputedStyle(el);
      if (cs.cursor !== 'pointer' || cs.visibility === 'hidden' || cs.display === 'none') continue;
      const r = el.getBoundingClientRect();
      if (r.width < 120 || r.height < 40) continue;
      const t = (el.innerText || '').trim().replace(/\s+/g, ' ');
      if (t.length < 6 || t.length > 300 || re.test(t.slice(0, 40))) continue;
      // keep the outermost pointer element of a card only
      if (el.parentElement && getComputedStyle(el.parentElement).cursor === 'pointer') continue;
      const key = t.slice(0, 80);
      if (seen.has(key)) continue;
      seen.add(key);
      // the longest line of the card is usually its title: click through that, not a badge like 预览
      const title = (el.innerText || '').split('\n').map(x => x.trim()).sort((a, b) => b.length - a.length)[0] || t;
      out.push({ index: out.length, text: t.slice(0, 120), title: title.slice(0, 40), tag: el.tagName });
    }
    return out;
  }, SKIP.source);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const startedAt = new Date().toISOString();
  const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => ({ err: String(e) }));
  if (opt.hide) await page.addStyleTag({ content: `${opt.hide} { display: none !important; }` }).catch(() => {});
  await page.waitForTimeout(Number(opt.wait));
  const found = (await cards(page)).slice(0, Number(opt.max));
  const clicks = [];
  for (const c of found) {
    const p = await ctx.newPage();
    await p.goto(url, { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
    if (opt.hide) await p.addStyleTag({ content: `${opt.hide} { display: none !important; }` }).catch(() => {});
    await p.waitForTimeout(Number(opt.wait));
    const again = await cards(p);
    const target = again.find(x => x.text === c.text);
    if (!target) { clicks.push({ ...c, result: 'card-not-found-on-reload' }); await p.close(); continue; }
    const before = p.url();
    const popupP = ctx.waitForEvent('page', { timeout: 6000 }).catch(() => null);
    // click the card through its own visible text; the click bubbles to the card's handler
    await p.getByText(target.title, { exact: false }).first()
      .click({ timeout: 8000 }).catch(e => { target.click_error = String(e).slice(0, 120); });
    const popup = await popupP;
    await p.waitForTimeout(3000);
    let landed = p.url(), page_title = await p.title().catch(() => null), via = landed !== before ? 'same-tab' : 'none';
    if (popup) {
      await popup.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
      landed = popup.url(); page_title = await popup.title().catch(() => null); via = 'new-tab';
      await popup.close().catch(() => {});
    }
    clicks.push({ ...c, before, landed, via, page_title });  // c.title stays the card's own title
    await p.close();
  }
  const result = { url, observed_at: startedAt, method: 'playwright-chromium click probe',
    status: resp && resp.status ? resp.status() : null, error: resp && resp.err || null,
    final_url: page.url(), title: await page.title(), cards_found: found.length, clicks };
  fs.writeFileSync(out, JSON.stringify(result, null, 1));
  console.log(JSON.stringify({ url, cards: found.length, landed: clicks.filter(c => c.via && c.via !== 'none').length }));
  await browser.close();
})();
