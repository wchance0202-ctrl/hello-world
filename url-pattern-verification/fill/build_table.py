#!/usr/bin/env python3
"""Assemble the fill-in results into the user's table layout, in the user's row order.

Columns: 站点名称｜pattern链接｜黑白名单属性｜正则表达式｜状态｜依据｜备注
Input: fill/rows.json (user order) and fill/out/<seq>.json (one record per row).
Writes fill/result-fill.xlsx and fill/result-fill.csv; prints counts by status.
"""
import csv
import json
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

HERE = Path(__file__).resolve().parent
COLS = ["站点名称", "pattern链接", "黑白名单属性", "正则表达式", "状态", "依据", "备注"]
FILL = {"已验证": "E2F0D9", "候选": "FFF2CC", "快照": "DDEBF7", "留空": "F2F2F2"}


def evidence(r):
    c = r.get("checks") or {}
    parts = []
    if r.get("mode") == "regex" and "inference_pos" in c:
        parts.append(f"样本：归纳 {c['inference_pos']}、留出正例 {c['holdout_pos']}、反例 {c['holdout_neg']}，"
                     f"google-re2 实测{'全部通过' if c.get('all_pass') else '有失败'}；覆盖检查 {c.get('coverage_members')} 个列表成员"
                     + ("无漏配" if not c.get("coverage_missed") else f"漏配 {len(c['coverage_missed'])}"))
    if r.get("families"):
        for i, f in enumerate(r["families"], 1):
            fc = f.get("checks") or {}
            parts.append(f"第 {i} 条：归纳 {fc.get('inference_pos')}、留出 {fc.get('holdout_pos')}、反例 {fc.get('holdout_neg')}，"
                         f"{'通过' if fc.get('all_pass') and not fc.get('coverage_missed') else '未全部通过'}（{f['status']}）")
    if r.get("mode") == "snapshot":
        parts.append(f"逐条打开核验 {r.get('members')} 个，保留 {r.get('kept')} 个" + (f"，剔除 {len(r['dropped'])} 个（打不开或跳转）" if r.get("dropped") else ""))
    if r.get("mode") == "carry":
        cf = r.get("carried_from")
        parts.append("沿用第 3 轮已验证规则 " + ("、".join(cf) if isinstance(cf, list) else str(cf)) + "（样本、落地核验、两套 RE2 记录见 output/round3）")
    ex = (r.get("exclusivity") or {}).get("evidence")
    if ex and r.get("mode") in ("regex",):
        parts.append("专属性：" + ex)
    return "；".join(p for p in parts if p)


def remarks(r):
    out = []
    if r.get("note"):
        out.append(r["note"])
    w = r.get("why_not_verified")
    if w:
        out.append("未达已验证：" + "；".join(w))
    ex = r.get("identity_excluded") or []
    if r.get("families"):
        ex = [x for f in r["families"] for x in f.get("identity_excluded", [])]
    if ex:
        out.append(f"{len(ex)} 个样本落地异常，未作正例")
    return "；".join(out)


def main():
    rows = json.loads((HERE / "rows.json").read_text(encoding="utf-8"))
    table = []
    for row in rows:
        p = HERE / "out" / f"{row['seq']:03d}.json"
        r = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"status": "未处理"}
        table.append({"站点名称": row["site"], "pattern链接": row["url"], "黑白名单属性": "白名单",
                      "正则表达式": r.get("pattern", ""), "状态": r.get("status", "未处理"),
                      "依据": "；".join(x for x in [r.get("basis") or "", evidence(r)] if x),
                      "备注": remarks(r)})
    with open(HERE / "result-fill.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(table)
    wb = Workbook()
    ws = wb.active
    ws.title = "补齐结果"
    ws.append(COLS)
    for t in table:
        ws.append([t[c] for c in COLS])
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFF2CC")
    for col, wd in zip("ABCDEFG", (22, 55, 10, 70, 9, 80, 50)):
        ws.column_dimensions[col].width = wd
    for rr in ws.iter_rows(min_row=2):
        for c in rr:
            c.alignment = Alignment(vertical="top", wrap_text=True)
        rr[3].font = Font(name="Consolas")
        color = FILL.get(rr[4].value)
        if color:
            rr[4].fill = PatternFill("solid", fgColor=color)
    ws.freeze_panes = "C2"
    wb.save(HERE / "result-fill.xlsx")
    print(json.dumps(Counter(t["状态"] for t in table), ensure_ascii=False))


if __name__ == "__main__":
    main()
