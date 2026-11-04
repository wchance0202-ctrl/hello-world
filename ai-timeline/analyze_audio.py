"""
独立分析音频的低频起音（底鼓），用来：
1) 验证 music.wav 的拍点和 beats.json 一致（写回 beats.json 的 verification 字段）
2) 验证成片 mp4 里的音轨没有起始偏移
用法: python3 analyze_audio.py music.wav [--write]
     python3 analyze_audio.py final.mp4
"""
import json, subprocess, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt, find_peaks

SR = 48000

def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<i2").astype(np.float64) / 32768

def low_env(x):
    sos = butter(4, 250 / (SR / 2), "low", output="sos")
    lo = sosfiltfilt(sos, x)
    w = int(0.002 * SR)
    return np.sqrt(np.convolve(lo ** 2, np.ones(w) / w, "same"))

def onset_near(env, t, pre=0.05, post=0.10):
    """在 [t-pre, t+post] 内找低频包络第一次越过窗口峰值 50% 的时刻"""
    a, b = max(0, int((t - pre) * SR)), int((t + post) * SR)
    seg = env[a:b]
    k = np.argmax(seg >= 0.5 * seg.max())
    return (a + k) / SR

def tempo(env):
    hop = 480                                   # 10 ms
    e = env[: len(env) // hop * hop].reshape(-1, hop).mean(1)
    flux = np.maximum(0, np.diff(e))
    flux = flux[int(8 / 0.01):int(23.4 / 0.01)]
    flux = flux - flux.mean()
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    lags = np.arange(len(ac)) * 0.01
    ok = (lags >= 60 / 160) & (lags <= 60 / 80)          # 80–160 BPM 的常规速度范围
    return 60 / lags[ok][np.argmax(ac[ok])]

def main():
    path = sys.argv[1]
    beats = json.load(open("beats.json"))
    x = load(path)
    env = low_env(x)
    # 只检查有底鼓的拍：承段第 1、3 拍(前两小节)和之后所有拍，直到鼓停；以及 drop 段和最后一击
    expect = []
    for i, t in enumerate(beats["beats"]):
        if 8.0 <= t < 12.0 and i % 2 == 1:
            continue
        if (8.0 <= t < beats["drums_stop"]["time"]) or (beats["drop"]["time"] <= t < 28.0) or i == beats["final_hit"]["beat"]:
            expect.append(t)
    errs = []
    for t in expect:
        errs.append(onset_near(env, t) - t)
    errs = np.array(errs) * 1000
    bpm = tempo(env)
    res = {
        "file": path,
        "beats_checked": len(expect),
        "estimated_bpm": round(float(bpm), 2),
        "offset_ms_median": round(float(np.median(errs)), 2),
        "offset_ms_max_abs": round(float(np.max(np.abs(errs))), 2),
        "drop_onset_s": round(float(onset_near(env, beats['drop']['time'])), 4),
    }
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if "--write" in sys.argv:
        beats["verification"] = res
        json.dump(beats, open("beats.json", "w"), ensure_ascii=False, indent=1)
    return res

if __name__ == "__main__":
    main()
