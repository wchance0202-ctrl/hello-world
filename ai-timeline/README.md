# AI 三年大事记（31 秒）

三年多，AI 从会聊天走到了会干活。

## 交付物
- `final.mp4`：1920×1080，30fps，31 秒，带音轨
- `beats.json`：BPM、每一拍、强拍、段落、drop、最后一击的时间，外加对音频的独立核验结果（`verification`）
- `storyboard.md`：分镜表
- `events.md`：事件清单、选取理由、来源链接
- `review/`：接触印样图（每个强拍一帧）、带拍点闪烁的 18–31 秒样片

## 重新生成
```bash
pip install numpy scipy pillow       # Playwright + Chromium、ffmpeg 需已安装
python3 music.py                     # → music.wav, beats.json
python3 analyze_audio.py music.wav --write   # 独立检测底鼓起音，核验拍点并写回 beats.json
node render.js video 0 31 final.mp4          # 逐帧截图 → mp4 + 音轨
node render.js video 18 31 sample.mp4 --debug   # 带拍点闪烁和帧号的样片
python3 check_sync.py sample.mp4 18          # 样片音画同步检查（偏差 > 1 帧判不合格）
```
在浏览器里预览：在本目录起一个静态服务器（例如 `python3 -m http.server`），打开 `index.html`，控制台里调用 `draw(12.3)` 查看任意时刻的画面；地址加 `?debug=1` 显示拍点叠加层。

## 修改
颜色、缓动强度、转场窗口和预备量、每段的镜头推进量、时间轴间距、事件文字，都在 `index.html` 顶部的 `CONFIG` 里。
镜头只写“第几拍”（或 `'drop'`、`'final_hit'`），具体秒数一律从 `beats.json` 取。
画面只由 `t` 计算，不读系统时间，不用 requestAnimationFrame、CSS 过渡和计时器，随机数用固定种子。
