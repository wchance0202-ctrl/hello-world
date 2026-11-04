"""
检查样片的音画同步：
- 视频：读取右上角拍点闪烁方块的亮度，找出亮起的帧
- 音频：从 mp4 解出音轨，找每个底鼓的起音时刻
- 对每一拍比较两者，偏差超过 1 帧(33.3ms)即不合格
用法: python3 check_sync.py <样片.mp4> <样片在原片中的起始秒>
"""
import json, subprocess, sys
import numpy as np
from analyze_audio import load, low_env, onset_near

path, start = sys.argv[1], float(sys.argv[2])
beats = json.load(open("beats.json"))
FPS = 30
# 视频：截取闪烁方块区域 (x 1830..1888, y 26..84)，缩成 1 像素灰度
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "crop=50:50:1834:30,scale=1:1,format=gray",
                      "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
lum = np.frombuffer(raw, np.uint8).astype(float)
flash_frames = np.where(lum > 80)[0]   # 红色(drop)方块灰度约 117
# 音频
env = low_env(load(path))
dur = len(lum) / FPS
rows, worst = [], 0.0
for i, tb in enumerate(beats["beats"]):
    rel = tb - start
    if rel < 0 or rel >= dur - 0.15:
        continue
    vf = flash_frames[np.argmin(np.abs(flash_frames - rel * FPS))] if len(flash_frames) else -1
    has_kick = (start <= tb < beats["drums_stop"]["time"]) or (beats["drop"]["time"] <= tb < 28.0) or i == beats["final_hit"]["beat"]
    at = onset_near(env, rel) if has_kick else None
    v_err = (vf / FPS - rel) * 1000
    a_err = (at - rel) * 1000 if at is not None else None
    av = (at - vf / FPS) * 1000 if at is not None else None
    if av is not None:
        worst = max(worst, abs(av))
    rows.append((i, tb, vf + round(start * FPS), v_err, a_err, av))
print(f"{'拍':>3} {'时间':>7} {'闪烁帧':>6} {'画面偏差ms':>9} {'声音偏差ms':>9} {'音画差ms':>8}")
for i, tb, vf, ve, ae, av in rows:
    print(f"{i:>3} {tb:>7.2f} {vf:>6} {ve:>9.1f} {'-' if ae is None else f'{ae:9.1f}':>9} {'-' if av is None else f'{av:8.1f}':>8}")
print(f"\n视频中亮起的帧数 {len(flash_frames)}，检查拍数 {len(rows)}，最大音画差 {worst:.1f} ms（1 帧 = 33.3 ms）")
print("结论:", "通过" if worst <= 1000 / FPS else "不通过")
