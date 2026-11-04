"""
合成配乐 + 输出 beats.json
四段能量：起(钢琴+铺底) → 承(鼓点进入) → 蓄(上升音效+鼓点加密) → 爆(drop，全部乐器)
用法: python3 music.py  -> music.wav, beats.json
"""
import json
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
BPM = 120
BEAT = 60.0 / BPM            # 0.5 s
BAR = 4 * BEAT               # 2.0 s
BEATS_PER_BAR = 4
TOTAL = 31.0                 # 末尾留 3 秒余音给结尾那句话
N = int(TOTAL * SR)
rng = np.random.default_rng(20221130)   # 固定种子

# 段落（以小节为单位，0 起）
SECTIONS = [
    ("起", 0, 4),    # 0-8s
    ("承", 4, 9),    # 8-18s
    ("蓄", 9, 12),   # 18-24s
    ("爆", 12, 14),  # 24-28s
    ("尾", 14, 15.5),  # 28-31s 收尾和弦余音
]
DROP_BAR = 12
FINAL_BAR = 14

def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}
def n(name):
    """'A4' -> midi"""
    p, o = name[:-1], int(name[-1])
    return 12 * (o + 1) + NOTE[p]

CHORDS = {
    "Am": ["A3", "C4", "E4"], "F": ["F3", "A3", "C4"],
    "C": ["G3", "C4", "E4"], "G": ["G3", "B3", "D4"],
}
ROOT = {"Am": "A1", "F": "F1", "C": "C2", "G": "G1"}
PROG = ["Am", "F", "C", "G"] * 3 + ["Am", "F", "C"]   # 15 小节

def t2i(t):
    return int(round(t * SR))

def bar_t(bar, beat=0.0):
    return bar * BAR + beat * BEAT

# ---------- 合成器 ----------
def env_adsr(length, a, d, s, r, sus_len):
    total = int(length * SR)
    out = np.zeros(total)
    ai, di, si = int(a * SR), int(d * SR), int(sus_len * SR)
    ri = total - ai - di - si
    idx = 0
    seg = [np.linspace(0, 1, max(ai, 1), endpoint=False),
           np.linspace(1, s, max(di, 1), endpoint=False),
           np.full(max(si, 0), s),
           np.linspace(s, 0, max(ri, 1))]
    cat = np.concatenate(seg)[:total]
    out[:len(cat)] = cat
    return out

def piano(freq, dur, vel=0.5):
    t = np.arange(int(dur * SR)) / SR
    sig = np.zeros_like(t)
    for h, amp in enumerate([1.0, 0.45, 0.22, 0.12, 0.06, 0.03], start=1):
        dec = np.exp(-t * (1.6 + 0.9 * h))
        sig += amp * np.sin(2 * np.pi * freq * h * t * (1 + 0.0004 * h)) * dec
    att = np.minimum(1, t / 0.004)
    hammer = rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.04
    rel = np.minimum(1, (dur - t) / 0.08)
    return vel * (sig * att + hammer) * rel

def saw(freq, t, detune=0.0):
    ph = (freq * (1 + detune) * t + rng.random()) % 1.0
    return 2 * ph - 1

def supersaw(freq, dur, voices=7, spread=0.012):
    t = np.arange(int(dur * SR)) / SR
    sig = np.zeros_like(t)
    for v in range(voices):
        d = (v - (voices - 1) / 2) / ((voices - 1) / 2) * spread
        sig += saw(freq, t, d)
    return sig / voices

def lowpass(x, fc, order=2):
    sos = butter(order, min(fc, SR / 2 * 0.95) / (SR / 2), "low", output="sos")
    return sosfilt(sos, x)

def highpass(x, fc, order=2):
    sos = butter(order, fc / (SR / 2), "high", output="sos")
    return sosfilt(sos, x)

def bandpass(x, lo, hi, order=2):
    sos = butter(order, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos")
    return sosfilt(sos, x)

def sweep_lowpass(x, f0, f1):
    """一阶低通，截止频率指数扫频（逐样本）"""
    out = np.empty_like(x)
    fc = f0 * (f1 / f0) ** (np.arange(len(x)) / len(x))
    a = np.exp(-2 * np.pi * fc / SR)
    y = 0.0
    for i in range(len(x)):
        y = (1 - a[i]) * x[i] + a[i] * y
        out[i] = y
    return out

def kick(vel=1.0, punch=1.0):
    dur = 0.45
    t = np.arange(int(dur * SR)) / SR
    f = 45 + 110 * np.exp(-t * 28) * punch
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.25
    return vel * np.tanh(1.6 * (body + click))

def snare(vel=0.6):
    dur = 0.25
    t = np.arange(int(dur * SR)) / SR
    noise = bandpass(rng.standard_normal(len(t)), 1500, 9000) * np.exp(-t * 22)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30)
    return vel * (0.8 * noise + 0.5 * tone)

def clap(vel=0.6):
    dur = 0.3
    t = np.arange(int(dur * SR)) / SR
    env = np.zeros_like(t)
    for k, off in enumerate([0, 0.011, 0.022, 0.032]):
        tt = np.clip(t - off, 0, None)
        env += (t >= off) * np.exp(-tt * (140 if k < 3 else 18))
    return vel * bandpass(rng.standard_normal(len(t)), 900, 6000) * env * 0.6

def hat(vel=0.25, open_=False):
    dur = 0.25 if open_ else 0.06
    t = np.arange(int(dur * SR)) / SR
    return vel * highpass(rng.standard_normal(len(t)), 7000) * np.exp(-t * (14 if open_ else 70))

def crash(vel=0.5, dur=2.5, decay=1.6):
    t = np.arange(int(dur * SR)) / SR
    return vel * highpass(rng.standard_normal(len(t)), 4500) * np.exp(-t * decay) * np.minimum(1, t / 0.002)

def sub_boom(vel=1.0, dur=1.6):
    t = np.arange(int(dur * SR)) / SR
    f = 32 + 60 * np.exp(-t * 6)
    return vel * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)

def make_reverb_ir(seconds=1.8, seed=7):
    r = np.random.default_rng(seed)
    t = np.arange(int(seconds * SR)) / SR
    ir = r.standard_normal(len(t)) * np.exp(-t * 3.2)
    ir = lowpass(ir, 6000)
    ir[0] = 1.0
    return ir / np.sqrt(np.sum(ir ** 2))

# ---------- 编排 ----------
class Bus:
    def __init__(self):
        self.x = np.zeros(N)
    def add(self, sig, t, gain=1.0):
        i = t2i(t)
        if i >= N:
            return
        j = min(N, i + len(sig))
        self.x[i:j] += gain * sig[: j - i]

piano_bus, pad_bus, drum_bus, bass_bus, synth_bus, fx_bus = (Bus() for _ in range(6))

MELODY = {  # 起段的钢琴旋律（每小节: [(拍, 音)]）
    "Am": [(0, "E5"), (2, "C5"), (3, "A4")],
    "F": [(0, "A4"), (2, "C5"), (3, "F5")],
    "C": [(0, "E5"), (2, "G5"), (3, "E5")],
    "G": [(0, "D5"), (2, "B4"), (3, "G4")],
}

for bar, ch in enumerate(PROG):
    t0 = bar_t(bar)
    notes = CHORDS[ch]
    if bar < FINAL_BAR:
        # 钢琴：起段稀疏；承段改成 8 分音符分解和弦；蓄爆段继续
        if bar < 4:
            for nn in notes:
                piano_bus.add(piano(mtof(n(nn)), 1.9, 0.08 + 0.025 * bar), t0)
            for beat, m in MELODY[ch]:
                piano_bus.add(piano(mtof(n(m)), 1.0, 0.14 + 0.04 * bar), bar_t(bar, beat))
        else:
            arp = notes + [notes[1], notes[2], notes[0] if False else notes[1]] + [notes[2], notes[1]]
            vel = 0.16 + 0.015 * (bar - 4)
            for k in range(8):
                m = n(arp[k % len(arp)]) + 12
                piano_bus.add(piano(mtof(m), 0.6, vel), bar_t(bar, k * 0.5))
        # 铺底 pad：全程，随段落开大低通
        pad_len = BAR + 0.3
        pad = np.zeros(int(pad_len * SR))
        for nn in notes:
            pad += supersaw(mtof(n(nn)), pad_len, voices=5, spread=0.006)
        e = env_adsr(pad_len, 0.6 if bar < 4 else 0.25, 0.2, 0.8, 0.5, pad_len - 1.4)
        fc = 700 if bar < 4 else (1100 if bar < 9 else 1800)
        pad_bus.add(lowpass(pad, fc) * e, t0, (0.05 + 0.012 * bar) if bar < 4 else 0.12)

# 承：鼓点进入
for bar in range(4, 12):
    for beat in range(4):
        t = bar_t(bar, beat)
        if bar < 6 and beat in (1, 3):
            continue                       # 前两小节只打 1、3 拍
        drum_bus.add(kick(0.75 + 0.02 * (bar - 4)), t)
    if bar >= 6:
        for beat in range(4):
            drum_bus.add(hat(0.12 + 0.01 * (bar - 6)), bar_t(bar, beat + 0.5))
    if bar >= 7:
        for beat in (1, 3):
            drum_bus.add(clap(0.42), bar_t(bar, beat))
    # 贝斯
    root = mtof(n(ROOT[PROG[bar]]) + 12)
    if bar < 6:
        b = supersaw(root, BAR, voices=2, spread=0.003)
        bass_bus.add(lowpass(b, 300) * env_adsr(BAR, 0.02, 0.2, 0.7, 0.2, BAR - 0.5), bar_t(bar), 0.35)
    else:
        for k in range(8):
            b = supersaw(root, 0.24, voices=2, spread=0.003)
            bass_bus.add(lowpass(b, 380) * env_adsr(0.24, 0.005, 0.08, 0.6, 0.05, 0.1), bar_t(bar, k * 0.5 + 0.5 * 0), 0.33)

# 蓄：军鼓加密 4分→8分→16分，上升音效，第 47 拍(0 起)后鼓全部停，只留上升音
roll = {9: 1.0, 10: 0.5, 11: 0.25}
for bar, step in roll.items():
    k = 0
    while k * step < 4:
        beat = k * step
        t = bar_t(bar, beat)
        if t < bar_t(11, 3):               # 23.5s 起鼓停
            prog = (t - bar_t(9)) / (6.0)
            drum_bus.add(snare(0.18 + 0.4 * prog), t)
        k += 1
riser_t0, riser_t1 = bar_t(9), bar_t(DROP_BAR)
rl = riser_t1 - riser_t0
tt = np.arange(int(rl * SR)) / SR
noise = rng.standard_normal(len(tt))
riser = sweep_lowpass(noise, 300, 12000) * (tt / rl) ** 2
pitch = 180 * (1400 / 180) ** (tt / rl)
riser += 0.25 * np.sin(2 * np.pi * np.cumsum(pitch) / SR) * (tt / rl) ** 1.5
fx_bus.add(riser, riser_t0, 0.22)
# 反向镲：最后一拍膨胀进 drop
rc = crash(1.0, 0.5)[::-1]
fx_bus.add(rc, bar_t(DROP_BAR) - 0.5, 0.35)

# 爆：drop
DROP = bar_t(DROP_BAR)
fx_bus.add(crash(0.55, 3.0), DROP)
fx_bus.add(sub_boom(0.75, 1.0), DROP)
for bar in range(DROP_BAR, FINAL_BAR):
    ch = PROG[bar]
    for beat in range(4):
        t = bar_t(bar, beat)
        drum_bus.add(kick(1.0, 1.2), t)
        drum_bus.add(hat(0.2, open_=True), bar_t(bar, beat + 0.5))
        for s in range(4):
            drum_bus.add(hat(0.06), bar_t(bar, beat + s * 0.25))
    for beat in (1, 3):
        drum_bus.add(clap(0.6), bar_t(bar, beat))
        drum_bus.add(snare(0.35), bar_t(bar, beat))
    # 超锯齿和弦（侧链）
    L = BAR
    chord = np.zeros(int(L * SR))
    for nn in CHORDS[ch]:
        chord += supersaw(mtof(n(nn) + 12), L) + 0.5 * supersaw(mtof(n(nn)), L)
    synth_bus.add(lowpass(chord, 5200) * env_adsr(L, 0.005, 0.1, 0.85, 0.05, L - 0.2), bar_t(bar), 0.16 + 0.14 * (bar - DROP_BAR))
    if bar > DROP_BAR:
        fx_bus.add(crash(0.5, 2.0, 2.2), bar_t(bar))
        drum_bus.add(sub_boom(0.5, 0.8), bar_t(bar))
    # 贝斯
    root = mtof(n(ROOT[ch]) + 12)
    for k in range(8):
        b = supersaw(root, 0.24, voices=3, spread=0.004)
        bass_bus.add(lowpass(b, 600) * env_adsr(0.24, 0.003, 0.06, 0.7, 0.05, 0.1), bar_t(bar, k * 0.5), 0.42 + 0.10 * (bar - DROP_BAR))
    # 主旋律
    LEAD = {"Am": ["A5", "C6", "E6", "C6", "B5", "C6", "E6", "A6"],
            "F": ["A5", "C6", "F6", "E6", "C6", "A5", "C6", "G6"]}[ch]
    for k, m in enumerate(LEAD):
        l = supersaw(mtof(n(m)), 0.45, voices=5, spread=0.008)
        synth_bus.add(lowpass(l, 7000) * env_adsr(0.45, 0.004, 0.15, 0.4, 0.15, 0.1), bar_t(bar, k * 0.5), 0.10 + 0.07 * (bar - DROP_BAR))

# 尾：28s 收尾大和弦 + 余音
FINAL = bar_t(FINAL_BAR)
fl = TOTAL - FINAL
fch = np.zeros(int(fl * SR))
for m in ["C3", "G3", "C4", "E4", "G4", "C5", "E5"]:
    fch += supersaw(mtof(n(m)), fl, voices=5, spread=0.008)
tt = np.arange(len(fch)) / SR
synth_bus.add(lowpass(fch, 4500) * np.exp(-tt * 1.3) * np.minimum(1, tt / 0.004), FINAL, 0.13)
for m in ["C3", "C4", "E4", "G4", "C5"]:
    piano_bus.add(piano(mtof(n(m)), fl, 0.32), FINAL)
drum_bus.add(kick(1.0, 1.3), FINAL)
fx_bus.add(crash(0.28, fl, 2.8), FINAL)
fx_bus.add(sub_boom(0.8, 2.5), FINAL)

# ---------- 侧链 & 混音 ----------
duck = np.ones(N)
for bar in range(DROP_BAR, FINAL_BAR):
    for beat in range(4):
        i = t2i(bar_t(bar, beat))
        L = int(0.22 * SR)
        j = min(N, i + L)
        curve = 1 - 0.55 * np.exp(-np.arange(j - i) / (0.06 * SR))
        duck[i:j] = np.minimum(duck[i:j], curve)

ir_l, ir_r = make_reverb_ir(seed=7), make_reverb_ir(seed=8)
def verb(x, ir, wet):
    return x + wet * fftconvolve(x, ir)[:N]

dry = (piano_bus.x * 1.0, pad_bus.x * duck, drum_bus.x, bass_bus.x * duck, synth_bus.x * duck, fx_bus.x)
pan = [(-0.15), (0.0), (0.0), (0.0), (0.1), (0.0)]
wet = [0.35, 0.3, 0.12, 0.0, 0.25, 0.2]
L = np.zeros(N)
R = np.zeros(N)
for x, p, w in zip(dry, pan, wet):
    L += verb(x, ir_l, w) * (1 - p)
    R += verb(x, ir_r, w) * (1 + p)
mix = np.stack([L, R], axis=1)
mix = np.tanh(mix * 0.8) / 0.8          # 轻度饱和，只削最尖的峰
# 结尾 0.4s 淡出，防止爆音
fade = int(0.4 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]

# 响度标准化：BS.1770 K 计权 + 门限，目标 -14 LUFS，峰值不超过 -1 dBFS
from scipy.signal import lfilter
def lufs(x):
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621]
    y = lfilter(b2, a2, lfilter(b1, a1, x, axis=0), axis=0)
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    z = np.array([np.mean(y[i:i + blk] ** 2, axis=0).sum() for i in range(0, len(y) - blk, hop)])
    lk = -0.691 + 10 * np.log10(z + 1e-12)
    z = z[lk > -70]
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    z = z[-0.691 + 10 * np.log10(z) > rel]
    return -0.691 + 10 * np.log10(z.mean())
TARGET_LUFS = -14.0
mix = mix * 10 ** ((TARGET_LUFS - lufs(mix)) / 20)
peak = np.max(np.abs(mix))
if peak > 0.89:
    mix = mix / peak * 0.89
print("loudness: %.2f LUFS, peak %.2f dBFS" % (lufs(mix), 20 * np.log10(np.max(np.abs(mix)))))

# 写 wav (16-bit)
import wave
with wave.open("music.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())

# ---------- beats.json ----------
nbeats = int(TOTAL / BEAT)
beats = [round(k * BEAT, 6) for k in range(nbeats)]
downbeats = [i for i in range(nbeats) if i % BEATS_PER_BAR == 0]
out = {
    "source": "synthesized (music.py)",
    "sample_rate": SR,
    "bpm": BPM,
    "beat_sec": BEAT,
    "beats_per_bar": BEATS_PER_BAR,
    "duration": TOTAL,
    "beats": beats,                      # 第 i 拍（0 起）的秒数
    "downbeats": downbeats,              # 强拍（每小节第 1 拍）的拍序号
    "sections": [{"name": nm, "start": bar_t(a), "end": min(TOTAL, bar_t(b)),
                  "start_beat": int(a * 4), "end_beat": int(b * 4)} for nm, a, b in SECTIONS],
    "drop": {"time": DROP, "beat": DROP_BAR * 4},
    "drums_stop": {"time": bar_t(11, 3), "beat": 11 * 4 + 3},
    "final_hit": {"time": FINAL, "beat": FINAL_BAR * 4},
}
# 每小节 RMS（用来验证能量单调上升）
rms = []
for bar in range(15):
    a, b = t2i(bar_t(bar)), t2i(min(TOTAL, bar_t(bar + 1)))
    rms.append(round(float(np.sqrt(np.mean(mix[a:b] ** 2))), 4))
out["bar_rms"] = rms
with open("beats.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("bar RMS:", rms)
print("drop at", DROP, "s; final at", FINAL, "s")
