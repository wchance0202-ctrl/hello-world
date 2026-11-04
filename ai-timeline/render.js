// 无头浏览器逐帧截图 → ffmpeg 合成 mp4 并合入音轨
// 用法:
//   node render.js video  <开始秒> <结束秒> <输出.mp4> [--debug]
//   node render.js stills <输出目录> <秒1,秒2,...> [--debug]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');

const ROOT = __dirname;
const MIME = { '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.ttf': 'font/ttf', '.png': 'image/png' };

function serve() {
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
      if (!p.startsWith(ROOT) || !fs.existsSync(p)) { rsp.writeHead(404); return rsp.end(); }
      rsp.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
      fs.createReadStream(p).pipe(rsp);
    });
    srv.listen(0, '127.0.0.1', () => res(srv));
  });
}

async function open(debug) {
  const srv = await serve();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => { console.error('PAGE ERROR', e); process.exit(1); });
  await page.goto(`http://127.0.0.1:${srv.address().port}/index.html${debug ? '?debug=1' : ''}`);
  await page.evaluate(() => window.__ready);
  const fps = await page.evaluate(() => CONFIG.fps);
  return { srv, browser, page, fps };
}

async function frame(page, t) {
  const url = await page.evaluate(t => { window.draw(t); return document.getElementById('c').toDataURL('image/png'); }, t);
  return Buffer.from(url.split(',')[1], 'base64');
}

(async () => {
  const [mode, ...args] = process.argv.slice(2);
  const debug = args.includes('--debug');
  const { srv, browser, page, fps } = await open(debug);
  if (mode === 'stills') {
    const [dir, list] = args;
    fs.mkdirSync(dir, { recursive: true });
    for (const s of list.split(',')) {
      const f = Math.round(parseFloat(s) * fps);
      fs.writeFileSync(path.join(dir, `f${String(f).padStart(4, '0')}.png`), await frame(page, f / fps));
    }
  } else if (mode === 'video') {
    const [t0s, t1s, out] = args;
    const f0 = Math.round(parseFloat(t0s) * fps), f1 = Math.round(parseFloat(t1s) * fps);
    // 音频从 f0/fps 开始截取（wav 输入端 -ss 是采样级精确的），视频第 0 帧 = 原片第 f0 帧
    const ff = spawn('ffmpeg', ['-y', '-v', 'error',
      '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
      '-ss', (f0 / fps).toFixed(6), '-t', ((f1 - f0) / fps).toFixed(6), '-i', path.join(ROOT, 'music.wav'),
      '-map', '0:v', '-map', '1:a',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', String(fps),
      '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t = Date.now();
    for (let f = f0; f < f1; f++) {
      const buf = await frame(page, f / fps);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if ((f - f0) % 60 === 0) process.stdout.write(`frame ${f}/${f1} (${((Date.now() - t) / 1000).toFixed(0)}s)\n`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('wrote', out);
  }
  await browser.close(); srv.close();
})();
