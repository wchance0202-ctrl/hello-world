#!/usr/bin/env python3
"""Build the hand-off task list for the entries both batches left unfinished.

One row per (entry, task). Task types:
  T1  入口未打开（访问受限 / 超时 / 证书 / 代理 / 挑战页）
  T2  页面没有标准链接（脚本组件渲染）
  T3  边界内没有可归纳的下级家族（条目可能在边界外，需重判栏目边界）
  T4  列表只取到首屏或前几屏（脚本翻页 / 加载更多未到底）
  T5  Hash 路由列表的翻页 / 加载更多未枚举
  T6  分页未翻完（单入口 300 页上限）
  T7  sitemap 对账缺口（同结构 URL 不在列表里）
  T8  规则未达正式准入（候选）
  T9  规则验证不通过（同级栏目页被匹配）
  T10 已交付规则范围超界（入口边界退化为站点根 /，或用变量覆盖了栏目标识）

Usage: python3 -I build_handoff.py <out_dir>
Writes remaining-tasks.csv / remaining-tasks.xlsx / remaining-tasks.json, and appendix.md (the
per-entry list grouped by task type, appended to the hand-off prompt). Prints counts.
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
BATCHES = (("第一批", ROOT / "output/round3"), ("第二批", ROOT / "batch2/output/round3"))
COLS = ["task_id", "批次", "entry_id", "原表行", "入口URL", "任务类型", "要做什么", "当前发现覆盖", "当前链接状态",
        "上一轮使用的边界", "相关规则（ID｜状态｜正则）", "上一轮记录"]
TYPE_NAME = {
    "T1": "入口未打开", "T2": "无标准链接（脚本渲染）", "T3": "边界内无下级家族", "T4": "列表未枚举到底",
    "T5": "Hash 路由翻页未枚举", "T6": "分页未翻完", "T7": "sitemap 对账缺口", "T8": "规则未达准入（候选）",
    "T9": "规则验证不通过（同级栏目）", "T10": "已交付规则范围超界",
}
TODO = {
    "T1": "以正常身份打开（公司网络/授权账号/人工过验证），按完整流程第 1–13 步处理；仍打不开就写访问受限并附原因与时间",
    "T2": "浏览器打开，用开发者工具 Network 看页面自己的只读数据请求，或逐个点击卡片记录落地 URL；按第 1 节判定每个落地 URL 属于 A/B/C",
    "T3": "重判栏目边界（第 1.3 节，特别是“列表页名”形式的末段）；条目在边界外且无法证明专属本栏目时，作为 B 类保留链接（精确清单），不写正则",
    "T4": "在浏览器里翻页 / 点加载更多直到到底（按钮消失或连续 3 次无新内容），核对页面显示的总数；再按第 5–12 步重新归纳与验证",
    "T5": "在浏览器里翻完该 Hash 路由列表（翻页 / 加载更多 / 滚动），点击取得更多落地 URL，每个都单独打开核验身份；补齐变量取值后重新验证",
    "T6": "从上一轮停下的位置继续翻页直到最后一页，对账总数；补入成员后重跑覆盖检查",
    "T7": "逐个判断 sitemap 中多出来的同结构 URL 是否属于本栏目（打开看面包屑 / 栏目标签 / 是否出现在列表的后续页）；属于的补进覆盖，不属于的说明原因",
    "T8": "补齐缺的准入条件（见“上一轮记录”）：找独立留出样本、补落地核验、去重；补不齐就保持候选并写明缺什么",
    "T9": "这类规则匹配到了同级栏目页（C 类）。不要放宽或改标签：改为保留链接，或找到本栏目专属的标识后重写",
    "T10": "按第 1.3 节重新确定栏目标识：详情 URL 带本栏目标识（如 catid=20）时把它写成字面量；不带时改为 B 类保留链接；重新验证后替换原规则",
}


def load(d):
    E = {e["entry_id"]: e for e in json.loads((d / "entries.json").read_text(encoding="utf-8"))}
    Q = json.loads((d / "queue.json").read_text(encoding="utf-8"))
    R = json.loads((d / "rules.json").read_text(encoding="utf-8"))
    return E, Q, R


def overreach(r):
    """Formal rule whose boundary fell back to the site root, or which shares one pattern across columns."""
    return " 入口前缀 / 下" in r.get("target", "")


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for batch, d in BATCHES:
        E, Q, R = load(d)
        by_rule = defaultdict(list)
        for kind in ("formal", "candidates", "failed"):
            for r in R[kind]:
                for eid in r.get("entry_ids", []):
                    by_rule[eid].append((kind, r))
        qby = defaultdict(list)
        for q in Q:
            qby[q["entry_id"]].append(q)
        tasks = defaultdict(list)  # eid -> [(type, note)]
        for eid, e in E.items():
            if e["kind"] != "path_entry":
                continue
            disc = e.get("discovery_status", "")
            text = (e.get("round3") or {}).get("discovery_text", "").split("\n")[0]
            if disc == "未验证":
                tasks[eid].append(("T1", e.get("link_status", "")))
            elif disc == "部分":
                if text.startswith("部分：Hash"):
                    tasks[eid].append(("T5", text))
                elif "没有可枚举的标准链接" in text:
                    tasks[eid].append(("T2", text))
                elif "未发现可归纳的下级家族" in text:
                    tasks[eid].append(("T3", text))
                elif not qby.get(eid):
                    tasks[eid].append(("T4", text + "；浏览器渲染只取到首屏或前几屏，未确认到底"))
            for q in qby.get(eid, []):
                t = {"访问受限": "T1", "权限拦截/挑战页": "T1", "单入口 300 页上限": "T6",
                     "范围对账缺口": "T7", "规则未达正式准入": "T8"}[q["reason"]]
                if t == "T1" and any(x[0] == "T1" for x in tasks[eid]):
                    continue
                tasks[eid].append((t, q["action"]))
            for kind, r in by_rule.get(eid, []):
                if kind == "failed":
                    tasks[eid].append(("T9", f"{r['id']}：" + "；".join(r.get("why", []) or r.get("why_not_verified", []))))
                elif kind == "formal" and overreach(r):
                    tasks[eid].append(("T10", f"{r['id']}：边界退化为站点根 /，正则 {r['pattern']} 会匹配其他栏目的页面"))
        # failed rules supersede the T8 queue line for the same rule
        for eid, ts in tasks.items():
            if any(t == "T9" for t, _ in ts):
                failed_ids = {n.split("：", 1)[0] for t, n in ts if t == "T9"}
                tasks[eid] = [(t, n) for t, n in ts if not (t == "T8" and n.split("：", 1)[0] in failed_ids)]
        for eid in sorted(tasks, key=lambda x: (E[x]["row"], E[x]["entry_index"])):
            e = E[eid]
            rules = "\n".join(f"{r['id']}｜{r['status'] if 'status' in r else kind}｜{r.get('pattern', '')}"
                              for kind, r in by_rule.get(eid, []))
            seen = set()
            for i, (t, note) in enumerate(tasks[eid], 1):
                if (t, note) in seen:
                    continue
                seen.add((t, note))
                rows.append({"task_id": f"{eid}-{t}-{i}", "批次": batch, "entry_id": eid, "原表行": e["row"],
                             "入口URL": e["raw"], "任务类型": f"{t} {TYPE_NAME[t]}", "要做什么": TODO[t],
                             "当前发现覆盖": e.get("discovery_status", ""), "当前链接状态": e.get("link_status", ""),
                             "上一轮使用的边界": (e.get("round3") or {}).get("prefix") or "",
                             "相关规则（ID｜状态｜正则）": rules, "上一轮记录": note[:600]})
    (out / "remaining-tasks.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / "remaining-tasks.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "剩余任务"
    ws.append(COLS)
    for r in rows:
        ws.append([r[c] for c in COLS])
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFF2CC")
    for col, wd in zip("ABCDEFGHIJKL", (26, 8, 13, 7, 50, 24, 60, 22, 30, 28, 70, 60)):
        ws.column_dimensions[col].width = wd
    for rr in ws.iter_rows(min_row=2):
        for c in rr:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    ws2 = wb.create_sheet("任务类型说明")
    ws2.append(["任务类型", "要做什么"])
    for t, n in TYPE_NAME.items():
        ws2.append([f"{t} {n}", TODO[t]])
    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 120
    wb.save(out / "remaining-tasks.xlsx")
    md = ["## 附录：剩余任务逐条清单", "",
          "完整字段（上一轮记录、相关规则的正则）见随附的 `remaining-tasks.xlsx`。同一入口可能有多条任务。", ""]
    for t, n in TYPE_NAME.items():
        sub = [r for r in rows if r["任务类型"].split(" ")[0] == t]
        if not sub:
            continue
        md += [f"### {t} {n}（{len(sub)} 条）", "", f"要做什么：{TODO[t]}", "",
               "| task_id | 原表行 | 入口 URL | 上一轮记录（摘要） |", "|---|---|---|---|"]
        for r in sub:
            note = r["上一轮记录"].replace("|", "\\|").replace("\n", " ")[:160]
            md.append(f"| {r['task_id']} | {r['批次']} {r['原表行']} | {r['入口URL']} | {note} |")
        md.append("")
    (out / "appendix.md").write_text("\n".join(md), encoding="utf-8")
    cnt = Counter((r["批次"], r["任务类型"]) for r in rows)
    ents = Counter(b for b, _ in {(r["批次"], r["entry_id"]) for r in rows})
    print(json.dumps({"tasks": len(rows), "entries": dict(ents),
                      "by_type": {f"{b} {t}": n for (b, t), n in sorted(cnt.items())}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
