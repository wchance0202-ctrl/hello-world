#!/usr/bin/env python3
"""List the rows of the fill-in table that are still unfinished (entry-only, candidate, empty),
with what blocks each one and the known clue, for the hand-off prompt.

Writes handoff/unfinished.xlsx, handoff/unfinished.csv and handoff/unfinished-appendix.md;
prompt-unfinished.md = handoff/prompt-unfinished-body.md + the appendix.
Usage: python3 -I fill/build_unfinished.py
"""
import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
# verified rows that still carry a caveat (sampled first screen only, page types left out, literal year, ...)
CAVEAT = {24: "条目是按钮没有 URL，正则只覆盖列表页；需确认条目是否真的没有独立地址",
          33: "样本只来自首屏卡片（翻页控件对脚本点击无效）", 34: "样本只来自首屏卡片（翻页控件对脚本点击无效）",
          35: "样本只来自首屏卡片，末段 /1 只见过一个取值", 37: "样本只来自首屏卡片（翻页控件对脚本点击无效）",
          39: "样本只来自首屏卡片（翻页控件对脚本点击无效）", 108: "样本只来自首屏卡片（翻页控件对脚本点击无效）",
          111: "样本只来自首屏卡片（翻页控件对脚本点击无效）"}
COLS = ["序号", "类别", "站点名称", "pattern链接", "当前状态", "当前正则", "不确定在哪里", "要做什么"]
CAT = {"单页": "B 单页待复核", "快照": "C 快照待补全", "超范围": "D 超范围待收窄", "已验证": "E 已验证但有保留"}
TODO = {
    "单页": "复核这个页面是否真的没有下级条目（翻页、加载更多、点击卡片都试一遍）；有就按全流程提取，没有就保持单页",
    "快照": "核对清单是否完整（翻页、加载更多到底，对照 sitemap）；能找到栏目标识或专属路径就改成通用正则，否则更新快照",
    "超范围": "寻找能区分本栏目的办法（URL 中的栏目标识、专属子路径、栏目自己的 sitemap 等）；找到就改成精确正则，找不到保持超范围并更新完整清单",
    "已验证": "针对“不确定在哪里”补样本或补漏掉的页面类型；规则需要修改的，按 v2 流程（旧留出转回归、取新留出）重测",
    "仅入口页（访问受限）": "用正常身份打开（公司网络或本人浏览器）；能打开就按全流程提取下级条目的正则；仍打不开写明原因",
    "仅入口页（需登录）": "用有权限的账号登录后按全流程提取；没有账号就保持现状并注明",
    "仅入口页（条目不可枚举）": "浏览器逐个点击卡片或看网络请求，取得条目地址后按全流程提取",
    "候选": "补齐备注里缺的证据（打开核验、更多样本、专属性证明），能补齐就改为已验证",
    "留空": "确认页面是否已搬迁；找到新地址就按全流程提取，否则保持留空",
}
HINT = {
    "Gartner": "已知部分 /insights/ 列表链接会跳到 /research/、/articles/ 等路径，跳转前后都要覆盖",
    "Dealroom": "companies/、investors/ 是数据库应用页，需订阅账号，内容是数据记录",
    "McKinsey": "此前连接超时，可能只是本环境网络问题",
    "Adobe": "此前连接超时，入口是 .html 文件形式，边界取同名目录或上级目录",
    "头豹研究院": "详情结构已知：/wiki/topic/{24位十六进制}、/video/details/{…}、/article/details/{…}、/report/details/{…}；未登录只显示 5 条",
    "中国煤炭工业协会": "详情是 index.php?m=content&c=index&a=show&catid={栏目}&id={数字}，catid 必须写成本栏目（及其子栏目）的固定值；站点曾持续返回 502",
    "LinkFlow": "课程详情 /courses/{数字}、/courses/{slug} 曾持续返回 500",
    "Hootsuite": "资源链接 /resource/{slug}/ 打开都 301 跳回 /resources/（资源改为表单领取）",
    "MobTech": "报告 PDF 在 cdn-static-oss.mob.com，曾返回 404",
    "微播易": "此前是本环境网络策略拒绝，不是网站拦截",
    "Search Engine Land": "5 个入口都在 /library/guide 或 /guide 下，注意入口之间的包含关系",
    "Circana": "Wix 页面，条目不是普通链接，也没有独立 sitemap",
    "哔哩哔哩营销": "/case/ 已返回 404，需在 e.bilibili.com 上找案例栏目的新地址",
}


def main():
    table = list(csv.DictReader(open(ROOT / "fill/result-fill.csv", encoding="utf-8-sig")))
    out = []
    for i, r in enumerate(table, 1):
        if r["状态"] == "已验证" and i not in CAVEAT:
            continue
        if r["状态"] == "已放宽":
            continue
        why = r["依据"].split("；")[0][:160]
        if r["备注"]:
            why += "；" + r["备注"][:160]
        hint = HINT.get(r["站点名称"].split("（")[0].split(" ")[0]) or HINT.get(r["站点名称"]) or ""
        if r["站点名称"] == "Dealroom" and not any(k in r["pattern链接"] for k in ("companies", "investors")):
            hint = ""
        if r["状态"] == "已验证":
            why = CAVEAT[i]
        cat = CAT.get(r["状态"], "A 未完成")
        out.append({"序号": i, "类别": cat, "站点名称": r["站点名称"], "pattern链接": r["pattern链接"], "当前状态": r["状态"],
                    "当前正则": r["正则表达式"], "不确定在哪里": why + (f"；线索：{hint}" if hint else ""),
                    "要做什么": TODO.get(r["状态"], "")})
    hd = ROOT / "handoff"
    with open(hd / "unfinished.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    wb = Workbook()
    ws = wb.active
    ws.title = "未完成"
    ws.append(COLS)
    for r in out:
        ws.append([r[c] for c in COLS])
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFF2CC")
    for col, wd in zip("ABCDEFGH", (6, 16, 22, 60, 20, 60, 80, 50)):
        ws.column_dimensions[col].width = wd
    for rr in ws.iter_rows(min_row=2):
        for c in rr:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "C2"
    wb.save(hd / "unfinished.xlsx")
    md = ["## 附录：需要处理的 %d 行（按原表顺序）" % len(out), "",
          "完整字段（当前正则、不确定在哪里）见随附的 `unfinished.xlsx`。", "",
          "| 序号 | 类别 | 站点名称 | pattern链接 | 当前状态 | 不确定在哪里 / 线索 |", "|---|---|---|---|---|---|"]
    for r in out:
        w = r["不确定在哪里"]
        note = w.split("线索：")[1] if "线索：" in w else (w if r["类别"].startswith("E") else "")
        md.append(f"| {r['序号']} | {r['类别']} | {r['站点名称']} | {r['pattern链接']} | {r['当前状态']} | {note.replace('|', '/')[:120]} |")
    (hd / "unfinished-appendix.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    body = (hd / "prompt-unfinished-body.md").read_text(encoding="utf-8")
    (hd / "prompt-unfinished.md").write_text(body + "\n" + "\n".join(md) + "\n", encoding="utf-8")
    print(len(out))


if __name__ == "__main__":
    main()
