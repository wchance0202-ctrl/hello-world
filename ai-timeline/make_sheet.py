"""把每个强拍的单帧拼成接触印样图。用法: python3 make_sheet.py <帧目录> <输出.png>"""
import json, sys, glob, os
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
beats = json.load(open("beats.json"))
fps = 30
files = sorted(glob.glob(os.path.join(src, "f*.png")))
TW, TH, COLS, CAP = 640, 360, 4, 40
rows = (len(files) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * TW + (COLS + 1) * 12, rows * (TH + CAP) + (rows + 1) * 12), (20, 22, 26))
font = ImageFont.truetype("assets/NotoSansSC.ttf", 22)
d = ImageDraw.Draw(sheet)
for k, fpath in enumerate(files):
    f = int(os.path.basename(fpath)[1:5])
    t = f / fps
    bi = min(range(len(beats["beats"])), key=lambda i: abs(beats["beats"][i] - t))
    sec = next((s["name"] for s in beats["sections"] if s["start"] <= t < s["end"]), "尾")
    im = Image.open(fpath).convert("RGB").resize((TW, TH), Image.LANCZOS)
    x = 12 + (k % COLS) * (TW + 12)
    y = 12 + (k // COLS) * (TH + CAP + 12)
    sheet.paste(im, (x, y))
    d.text((x + 4, y + TH + 6), f"{t:5.2f}s  第{bi}拍  帧{f}  [{sec}]", fill=(200, 205, 215), font=font)
sheet.save(out)
print("wrote", out, sheet.size)
