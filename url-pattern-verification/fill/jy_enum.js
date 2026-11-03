// Page through jazzyear article_list by its own page= URL parameter (normal page loads), collect article_info links.
const { chromium } = require('playwright'); const fs = require('fs');
const [type, out] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch(); const p = await b.newPage(); const all = new Set();
  const C = encodeURIComponent('全部');
  for (let n = 1; n <= 400; n++) {
    const u = `https://www.jazzyear.com/article_list.html?type=${type}&hotest=0&classifyName1=${C}&classifyName2=${C}&classifyName3=${C}&classifyName4=${C}&page=${n}`;
    await p.goto(u, { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
    await p.waitForTimeout(1500);
    const hs = await p.$$eval('a[href*="article_info.html?id="]', as => as.filter(a => !a.closest('header,nav,footer,aside')).map(a => a.href));
    const before = all.size; hs.forEach(h => all.add(h));
    if (all.size === before) { console.log(`type ${type} stop at page ${n}`); break; }
  }
  fs.writeFileSync(out, [...all].join('\n')); console.log(`type ${type}: ${all.size}`); await b.close();
})();
