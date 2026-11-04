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
FILL = {"已放宽": "FFF2CC", "已验证": "E2F0D9", "候选": "FFF2CC", "快照": "DDEBF7", "留空": "F2F2F2", "超范围": "FCE4D6",
        "单页": "EDEDED", "单页（含跳转页）": "E7E6F7", "仅入口页（需登录）": "F2F2F2", "仅入口页（访问受限）": "F2F2F2", "仅入口页（条目不可枚举）": "F2F2F2"}


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
        if cf:
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
    if r.get("relax_note"):
        out.insert(0, "放宽：" + r["relax_note"])
    if r.get("extra_exact_kept"):
        out.append(f"其中一行是 {r["extra_exact_kept"]} 个子页面的精确地址")
    if r.get("redirect_extra"):
        out.append(f"最后一行正则是 {len(r['redirect_extra'])} 个跳转目标（列表链接打开后实际落地的地址）")
    if r.get("redirect_skipped"):
        out.append(f"{len(r['redirect_skipped'])} 个链接跳到验证页、入口页或站点首页/一级列表页，未计入")
    if r.get("full_list_count"):
        out.append(f"本栏目完整清单 {r['full_list_count']} 条见附表「栏目完整清单」")
    if r.get("unverified_kept"):
        out.append(f"{r['unverified_kept']} 个公众号文章无法自动落地核验，按列表保留")
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
    meaning = {
        "已验证": "按严格标准验证：真实样本归纳、留出样本检验、反例不匹配、逐个打开确认、覆盖检查通过",
        "已放宽": "正则正确且能用：RE2 可编译、能匹配见过的真实条目网址、不匹配导航等无关页面；可能同时匹配同站其他栏目的同类页面，部分样本来自搜索引擎",
        "单页（含跳转页）": "链接本身是单个页面：第一行是本页地址，后面是页面里链到的同站页面（逐个打开确认过）",
        "单页": "链接本身是单个页面，页面里没有可收录的同站跳转链接，正则就是本页地址",
        "仅入口页（访问受限）": "网站拦截本环境或网络被拒，只写了入口页地址（待你配合）",
        "仅入口页（需登录）": "内容需登录，只写了入口页地址（待你配合）",
        "留空": "栏目已不存在（页面 404）",
    }
    cnt = Counter(t["状态"] for t in table)
    ws0 = wb.create_sheet("汇总", 0)
    ws0.append(["状态", "行数", "含义"])
    for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
        ws0.append([k, v, meaning.get(k, "")])
    ws0.append(["合计", sum(cnt.values()), ""])
    for c in ws0[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFF2CC")
    ws0.column_dimensions["A"].width = 22
    ws0.column_dimensions["B"].width = 8
    ws0.column_dimensions["C"].width = 110
    for rr in ws0.iter_rows(min_row=2):
        rr[2].alignment = Alignment(wrap_text=True, vertical="top")
    ws2 = wb.create_sheet("栏目完整清单")
    ws2.append(["序号", "站点名称", "pattern链接", "条目URL"])
    for row in rows:
        lp = HERE / "lists" / f"{row['seq']:03d}.txt"
        if lp.exists():
            for u in lp.read_text(encoding="utf-8").split("\n"):
                if u.strip():
                    ws2.append([row["seq"], row["site"], row["url"], u.strip()])
    for col, wd in zip("ABCD", (6, 22, 55, 100)):
        ws2.column_dimensions[col].width = wd
    ws2.freeze_panes = "A2"
    wb.save(HERE / "result-fill.xlsx")
    print(json.dumps(Counter(t["状态"] for t in table), ensure_ascii=False))


if __name__ == "__main__":
    main()
