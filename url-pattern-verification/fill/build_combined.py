#!/usr/bin/env python3
"""One combined workbook: per row the pattern link, the regex, and every positive / negative
example used in the final verification, each re-tested against the regex now.

Sheets:
  总表      - one row per table row: link, status, regex, counts, a few examples, verification result
  正反例明细 - one row per example: 正例 (real item link, must match) / 反例 (must not match), tested now
Writes fill/combined.xlsx. Usage: python3 -I fill/build_combined.py
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import re2
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_all as V  # noqa: E402

SHOW = 5  # examples shown in the 总表 cell


def load_r3():
    r3 = {}
    for d0 in ("output/round3", "batch2/output/round3"):
        R = json.loads((HERE.parent / d0 / "rules.json").read_text(encoding="utf-8"))
        for k in ("formal", "candidates"):
            for r in R[k]:
                if r.get("samples"):
                    r3[r["id"]] = r
        hf = HERE.parent / d0 / "hash-frozen.json"
        if hf.exists():
            for r in json.loads(hf.read_text(encoding="utf-8"))["rules"]:
                if r.get("id"):
                    r3[r["id"]] = {"samples": {"inference": r.get("inference", []), "holdout_pos": r.get("holdout_pos", [])}}
    return r3


def main():
    rows = json.loads((HERE / "rows.json").read_text(encoding="utf-8"))
    rep = {r["seq"]: r for r in json.loads((HERE / "verify-report.json").read_text(encoding="utf-8"))}
    r3 = load_r3()
    wb = Workbook()
    ws = wb.active
    ws.title = "总表"
    cols = ["序号", "站点名称", "pattern链接", "状态", "正则表达式", "正则行数", "正例数", "正例匹配", "正例（示例）",
            "反例数", "反例不匹配", "反例（全部）", "已失效链接", "今日抽查打开", "结论"]
    ws.append(cols)
    wd = wb.create_sheet("正反例明细")
    wd.append(["序号", "站点名称", "pattern链接", "类型", "示例URL", "检测结果"])
    tot = {"pos": 0, "neg": 0, "bad": 0}
    for row in rows:
        seq = row["seq"]
        out = json.loads((HERE / "out" / f"{seq:03d}.json").read_text(encoding="utf-8"))
        dec = json.loads((HERE / "dec" / f"{seq:03d}.json").read_text(encoding="utf-8"))
        lines = [l for l in (out.get("pattern") or "").split("\n") if l]
        v = rep.get(seq, {})
        if not lines:
            ws.append([seq, row["site"], row["url"], out.get("status"), "", 0, 0, "—", "", 0, "—", "", "", "—", "无正则（栏目已不存在）"])
            continue
        rxs = [re2.compile(l) for l in lines]
        hit = lambda u: any(r.fullmatch(u) for r in rxs)  # noqa: E731
        dead = {d["url"] for d in out.get("dead_links", [])}
        pos = [u for u in V.positives(seq, dec, out, r3) if u.startswith("http") and u not in dead]
        host = urlsplit(row["url"].split("#")[0] if "://" in row["url"] else "https://" + row["url"]).netloc
        entry = row["url"].split("#")[0].rstrip("/")
        negs = set(dec.get("negatives", []) or []) | {f"https://{host}/"}
        if out.get("status", "").startswith("单页") or "也匹配入口页" in (out.get("relax_note") or "") + (dec.get("note") or ""):
            negs.discard(row["url"].split("#")[0])
        negs = sorted(u for u in negs if u.rstrip("/") != entry)
        pos_ok = [u for u in pos if hit(u)]
        neg_ok = [u for u in negs if not hit(u)]
        for u in pos:
            wd.append([seq, row["site"], row["url"], "正例", u, "匹配 ✓" if hit(u) else "未匹配 ✗"])
        for u in negs:
            wd.append([seq, row["site"], row["url"], "反例", u, "不匹配 ✓" if not hit(u) else "误匹配 ✗"])
        tot["pos"] += len(pos)
        tot["neg"] += len(negs)
        tot["bad"] += len(pos) - len(pos_ok) + len(negs) - len(neg_ok)
        ok = len(pos_ok) == len(pos) and len(neg_ok) == len(negs)
        lv = "；".join(x["result"] for x in v.get("live", [])) or "—"
        ex = "\n".join(pos[:SHOW]) + (f"\n……共 {len(pos)} 个，见「正反例明细」" if len(pos) > SHOW else "")
        ws.append([seq, row["site"], row["url"], out.get("status"), "\n".join(lines), len(lines), len(pos),
                   f"{len(pos_ok)}/{len(pos)}", ex, len(negs), f"{len(neg_ok)}/{len(negs)}", "\n".join(negs),
                   len(dead) or "", lv, "正确且能用" if ok else "有问题"])
    for s, widths in ((ws, (6, 20, 50, 14, 70, 7, 7, 9, 70, 7, 9, 60, 8, 40, 11)), (wd, (6, 20, 50, 6, 100, 10))):
        for c in s[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="FFF2CC")
        for i, w in enumerate(widths):
            s.column_dimensions[chr(65 + i)].width = w
        s.freeze_panes = "D2"
    for rr in ws.iter_rows(min_row=2):
        for c in rr:
            c.alignment = Alignment(vertical="top", wrap_text=True)
        rr[4].font = Font(name="Consolas")
    wd.auto_filter.ref = wd.dimensions
    ws.auto_filter.ref = ws.dimensions
    wb.save(HERE / "combined.xlsx")
    print(json.dumps(tot))


if __name__ == "__main__":
    main()
