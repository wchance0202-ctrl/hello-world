#!/usr/bin/env python3
"""Full table over every path entry of both batches (535), not only the 265 fill-in rows.

Per entry:
  - entry is one of the 265 fill-in rows -> today's result (fill/out), positives/negatives as in verify_all
  - otherwise -> round-3 rules of that entry (formal, candidates, failed, hash-frozen):
                 regex lines, positives = inference + holdout_pos + regression_pos,
                 negatives = holdout_neg + regression_neg; review notes from handoff/fill-list.xlsx
  - neither  -> no regex in this repository (reason from the round-3 ledger)
Every example is re-tested now with google-re2 full match.
Sheets: 汇总, 总表, 正反例明细. Writes fill/full-table.xlsx and fill/full-table.csv.
Usage: python3 -I fill/build_full.py
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import re2
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_combined as BC  # noqa: E402
import verify_all as V  # noqa: E402

BATCHES = (("第一批", ROOT / "output/round3"), ("第二批", ROOT / "batch2/output/round3"))
SHOW = 5
# round-3 rules corrected today (the old character class missed real holdout items)
OVERRIDE = {"R3-S1-R18-E6-F1": r"^https://www\.itu\.int/en/ITU\-T/[a-zA-Z0-9-]+/Pages/[A-Za-z0-9-]+\.aspx$"}


def r3_rules(d):
    R = json.loads((d / "rules.json").read_text(encoding="utf-8"))
    by = {}
    for k, lab in (("formal", None), ("candidates", None), ("failed", None)):
        for r in R.get(k, []):
            s = r.get("samples") or {}
            pats = [OVERRIDE.get(r["id"]) or r["pattern"]] if r.get("pattern") else list(r.get("patterns") or [])
            if not pats:
                continue
            item = {"pattern": "\n".join(pats), "status": r["status"], "kind": k, "id": r["id"],
                    "pos": (s.get("inference") or []) + (s.get("holdout_pos") or []) + (s.get("regression_pos") or []),
                    "neg": (s.get("holdout_neg") or []) + (s.get("regression_neg") or [])}
            for eid in r["entry_ids"]:
                by.setdefault(eid, []).append(item)
    hf = d / "hash-frozen.json"
    if hf.exists():
        for r in json.loads(hf.read_text(encoding="utf-8"))["rules"]:
            for eid in r.get("entry_ids") or [r.get("entry_id")]:
                if any(x["pattern"] == r["pattern"] for x in by.get(eid, [])):
                    continue
                by.setdefault(eid, []).append({"pattern": r["pattern"], "status": "已验证（Hash 路由，浏览器取样）", "kind": "formal",
                                               "id": r["id"], "pos": (r.get("inference") or []) + (r.get("holdout_pos") or []),
                                               "neg": r.get("holdout_neg") or []})
    return by


def main():
    rows = json.loads((HERE / "rows.json").read_text(encoding="utf-8"))
    fill_by_eid = {r["entry_ids"][0]: r for r in rows}
    site_by_host = {}
    for r in rows:
        site_by_host.setdefault(urlsplit(r["url"] if "://" in r["url"] else "https://" + r["url"]).netloc, r["site"])
    rep = {r["seq"]: r for r in json.loads((HERE / "verify-report.json").read_text(encoding="utf-8"))}
    r3 = BC.load_r3()
    review = {}
    wbr = load_workbook(ROOT / "handoff/fill-list.xlsx", read_only=True)
    for x in list(wbr["已填需复核"].iter_rows(values_only=True))[1:]:
        review[x[1]] = f"{x[4]}；建议：{x[5]}"
    out_rows, detail = [], []
    for bname, d in BATCHES:
        by = r3_rules(d)
        for e in json.loads((d / "entries.json").read_text(encoding="utf-8")):
            if e["kind"] != "path_entry":
                continue
            eid = e["entry_id"]
            host = e["host"]
            rec = {"批次": bname, "原表行": e["row"], "entry_id": eid, "pattern链接": e["raw"],
                   "站点名称": site_by_host.get(host, host)}
            if eid in fill_by_eid:
                fr = fill_by_eid[eid]
                seq = fr["seq"]
                out = json.loads((HERE / "out" / f"{seq:03d}.json").read_text(encoding="utf-8"))
                dec = json.loads((HERE / "dec" / f"{seq:03d}.json").read_text(encoding="utf-8"))
                lines = [l for l in (out.get("pattern") or "").split("\n") if l]
                dead = {x["url"] for x in out.get("dead_links", [])}
                pos = [u for u in V.positives(seq, dec, out, r3) if u.startswith("http") and u not in dead]
                entry = fr["url"].split("#")[0].rstrip("/")
                negs = set(dec.get("negatives", []) or []) | {f"https://{host}/"}
                negs = sorted(u for u in negs if u.rstrip("/") != entry)
                lv = "；".join(x["result"] for x in rep.get(seq, {}).get("live", []))
                rec.update(站点名称=fr["site"], 来源=f"今天 265 行（第 {seq} 行）", 状态=out.get("status"), 备注="")
            elif (ROOT / "fill2/out" / f"{eid}.json").exists():
                f2 = json.loads((ROOT / "fill2/out" / f"{eid}.json").read_text(encoding="utf-8"))
                lines = [l for l in (f2.get("pattern") or "").split("\n") if l]
                pos, negs = f2.get("positives", []), f2.get("negatives", [])
                lv = "；".join(x["result"] for x in f2.get("live", []))
                rec.update(站点名称=f2.get("site") or rec["站点名称"], 来源="补做（放宽，fill2）", 状态=f2.get("status"), 备注=f2.get("basis", ""))
            else:
                rules = by.get(eid, [])
                lines, pos, negs = [], [], []
                tests = []  # each sample is tested against its own rule, as in round 3
                for r in rules:
                    for pl in r["pattern"].split("\n"):
                        if pl not in lines:
                            lines.append(pl)
                    own = [re2.compile(pl) for pl in r["pattern"].split("\n")]
                    tests += [("正例", u, own) for u in r["pos"] if u not in pos]
                    pos += [u for u in r["pos"] if u not in pos]
                    tests += [("反例", u, own) for u in r["neg"] if u not in negs]
                    negs += [u for u in r["neg"] if u not in negs]
                st = sorted({r["status"] for r in rules})
                lv = ""
                note = review.get(eid, "")
                if not rules:
                    dt = ((e.get("round3") or {}).get("discovery_text") or "") if isinstance(e.get("round3"), dict) else ""
                    note = dt.split("\n")[0][:200]
                rec.update(来源="之前几轮（第 3 轮规则）" if rules else "之前几轮，未出正则", 状态="；".join(st) if st else "无正则", 备注=note)
            if eid in fill_by_eid or rec["来源"].startswith("补做"):
                allrx = [re2.compile(l) for l in lines]
                tests = [("正例", u, allrx) for u in pos] + [("反例", u, allrx) for u in negs]
            pos_ok, neg_ok = [], []
            for typ, u, rxs in tests:
                m = any(r.fullmatch(u) for r in rxs)
                good = m if typ == "正例" else not m
                (pos_ok if typ == "正例" else neg_ok).append(u) if good else None
                res = ("匹配 ✓" if m else "未匹配 ✗") if typ == "正例" else ("不匹配 ✓" if not m else "误匹配 ✗")
                detail.append([bname, e["row"], rec["站点名称"], e["raw"], typ, u, res])
            if not lines:
                verdict = "无正则"
            elif rec["来源"].startswith(("今天", "补做")):
                verdict = "正确且能用" if len(pos_ok) == len(pos) and len(neg_ok) == len(negs) else "有问题"
            else:
                ok = len(pos_ok) == len(pos) and len(neg_ok) == len(negs)
                kinds = {r["kind"] for r in by.get(eid, [])}
                good = kinds == {"formal"}
                if "failed" in kinds and not ok:
                    verdict = "验证不通过（不建议用）"
                else:
                    verdict = ("正确且能用" if good else "能用（候选，证据不足）") if ok else "样本测试有失败"
                if rec["备注"] and good and ok:
                    verdict = "能用（有复核意见）"
            ex = "\n".join(pos[:SHOW]) + (f"\n……共 {len(pos)} 个，见「正反例明细」" if len(pos) > SHOW else "")
            rec.update(正则表达式="\n".join(lines), 正则行数=len(lines), 正例数=len(pos), 正例匹配=f"{len(pos_ok)}/{len(pos)}" if lines else "—",
                       正例示例=ex, 反例数=len(negs), 反例不匹配=f"{len(neg_ok)}/{len(negs)}" if lines else "—", 反例="\n".join(negs),
                       今日抽查打开=lv, 结论=verdict)
            out_rows.append(rec)
    cols = ["批次", "原表行", "entry_id", "站点名称", "pattern链接", "来源", "状态", "正则表达式", "正则行数", "正例数", "正例匹配",
            "正例示例", "反例数", "反例不匹配", "反例", "今日抽查打开", "结论", "备注"]
    with open(HERE / "full-table.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "汇总"
    ws = wb.create_sheet("总表")
    ws.append(cols)
    for r in out_rows:
        ws.append([r[c] for c in cols])
    wd = wb.create_sheet("正反例明细")
    wd.append(["批次", "原表行", "站点名称", "pattern链接", "类型", "示例URL", "检测结果"])
    for x in detail:
        wd.append(x)
    cnt = Counter((r["来源"].split("（")[0].split("，")[0], r["结论"]) for r in out_rows)
    ws0.append(["来源", "结论", "行数"])
    for (a, b), n in sorted(cnt.items()):
        ws0.append([a, b, n])
    ws0.append(["合计", "", len(out_rows)])
    ws0.append([])
    ws0.append(["正例总数", sum(r["正例数"] for r in out_rows)])
    ws0.append(["反例总数", sum(r["反例数"] for r in out_rows)])
    ws0.append(["测试失败数", sum(1 for x in detail if "✗" in x[6])])
    widths = {ws0: (26, 26, 10), ws: (7, 7, 12, 20, 50, 20, 18, 70, 7, 7, 9, 70, 7, 9, 60, 40, 16, 50),
              wd: (7, 7, 20, 50, 6, 100, 10)}
    for s, wds in widths.items():
        for c in s[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="FFF2CC")
        for i, w in enumerate(wds):
            s.column_dimensions[chr(65 + i)].width = w
    for s in (ws, wd):
        s.freeze_panes = "F2" if s is ws else "E2"
        s.auto_filter.ref = s.dimensions
    for rr in ws.iter_rows(min_row=2):
        for c in rr:
            c.alignment = Alignment(vertical="top", wrap_text=True)
        rr[7].font = Font(name="Consolas")
    wb.save(HERE / "full-table.xlsx")
    for (a, b), n in sorted(cnt.items()):
        print(a, b, n)
    print("rows", len(out_rows), "pos", sum(r["正例数"] for r in out_rows), "neg", sum(r["反例数"] for r in out_rows),
          "fail", sum(1 for x in detail if "✗" in x[6]))


if __name__ == "__main__":
    main()
