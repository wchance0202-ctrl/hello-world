#!/usr/bin/env python3
"""Round 2 (2026-10-26, network open): merge this round's evidence into new deliverables.

Offline step. Reads the round-1 ledger (output/entries.json, output/queue.json) and the
round-2 evidence under output/round2/, and writes into output/round2/:
  entries.json, rules.json, queue.json, result-table.csv|xlsx, summary.json
Round-1 files are left untouched.

Only priority-1 queue items were worked this round. Every other path entry gets the
host-level connectivity result and stays "未验证".

Usage: python3 -I apply_round2.py <output_dir>
"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_ledger import COLUMN, RESULT_FIELDS, ROW_NOTE, write_table  # noqa: E402

RUN = "2026-10-26（第 2 轮，网络已放开）"
ENG = "node-re2 1.24.1（validate_patterns.mjs）+ google-re2 1.1.20251105，两者逐对结果一致"
EV = "output/round2/"


def jl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def load(out):
    r2 = out / "round2"
    ctx = {
        "entries": json.loads((out / "entries.json").read_text(encoding="utf-8")),
        "queue": json.loads((out / "queue.json").read_text(encoding="utf-8")),
        "conn": {r["entry_id"]: r for r in jl(r2 / "connectivity.jsonl")},
        "retries": jl(r2 / "connectivity-retries.jsonl"),
        "visits": jl(r2 / "probe/visits.jsonl"),
        "redirects": jl(r2 / "k5-redirects.jsonl"),
        "v2": json.loads((r2 / "tests/v2.node-re2.json").read_text(encoding="utf-8")),
        "v2py": json.loads((r2 / "tests/v2.google-re2.json").read_text(encoding="utf-8")),
        "frozen": json.loads((r2 / "tests/samples-frozen.json").read_text(encoding="utf-8")),
        "frozen2": json.loads((r2 / "tests/samples-frozen-v2.json").read_text(encoding="utf-8")),
        "snap": json.loads((r2 / "tests/forrester-exact-candidates.json").read_text(encoding="utf-8")),
        "excluded": json.loads((r2 / "tests/v2-tests.json").read_text(encoding="utf-8"))["excluded_records"],
        "ident": {r["url"]: r for r in jl(r2 / "tests/identity-checks.jsonl")},
    }
    with gzip.open(r2 / "tests/forrester-snapshot.node-re2.json.gz", "rt", encoding="utf-8") as f:
        ctx["snap_node"] = json.load(f)
    with gzip.open(r2 / "tests/forrester-snapshot.google-re2.json.gz", "rt", encoding="utf-8") as f:
        ctx["snap_py"] = json.load(f)
    return ctx


# ---------------------------------------------------------------- findings (P1 entries)

# Coverage check of the frozen rules against every sitemap member (output/round2/tests/coverage-check*.json*)
COVERAGE = {
    "R2-OPT-GUIDES-DETAIL": {
        "members": 52, "unmatched": 6,
        "example": "…/guides/gartner-emerging-market-quadrant-for-AI-agents-for-marketing；另 5 个 …/{slug}/thank-you 表单完成页",
        "v3": r"^https://www\.optimizely\.com/field-notes/guides/[A-Za-z0-9]+(?:-+[A-Za-z0-9]+)*-?/?$",
        "evidence": EV + "tests/coverage-check.json"},
    "R2-OPT-ARTICLES-DETAIL": {
        "members": 418, "unmatched": 10,
        "example": "…/articles/AI-experimentation、…/articles/opal-ki-workflows-",
        "v3": r"^https://www\.optimizely\.com/field-notes/articles/[A-Za-z0-9]+(?:-+[A-Za-z0-9]+)*-?/?$",
        "evidence": EV + "tests/coverage-check.json"},
}


def wipo_findings(ctx):
    by = defaultdict(list)
    for r in ctx["redirects"]:
        by[r["entry_id"]].append(r)
    out = {}
    for e in ctx["entries"]:
        if not e["entry_id"].startswith("S1-R19-") or e["kind"] != "path_entry":
            continue
        rs = by.get(e["entry_id"], [])
        red = [r for r in rs if r["redirected"]]
        bad = [r for r in rs if r["status"] != 200]
        samples = "；".join(f"{r['url']} →{'/'.join(str(h['status']) for h in r['hops'][:-1])}→ {r['final_url']}"
                           for r in red) or "无"
        out[e["entry_id"]] = {
            "discovery": "部分",
            "discovery_text": (f"部分：入口静态首轮 1 页；入口路径下子链接 {len(rs)} 个逐跳复核"
                               f"（跳转 {len(red)}、非200 {len(bad)}）；子页面栏目归属与下级目录未枚举"),
            "rule": "无规则（门户页，下级为异构子页面，归属待定）",
            "link": "可打开（入口 200）",
            "retained_extra": f"子链接与跳转链见 {EV}k5-redirects.jsonl（entry_id={e['entry_id']}）",
            "notes": [f"[K5 复核] 跳转样本：{samples}"]
                     + [f"[K5] 404：{r['url']}" for r in bad],
            "queue_done": ["K5", "Q1-access"],
        }
    return out


def static_findings(ctx):
    v = {}
    for r in ctx["visits"]:
        if r["relation"] == "entry":
            v[r["entry_id"]] = r
    sm = Counter(r["entry_id"] for r in ctx["redirects"] if r["entry_id"] == "S1-R26-E1")
    mintel_red = [r for r in ctx["redirects"] if r["entry_id"] == "S1-R26-E1" and r["redirected"]]
    F = {}
    F["S1-R26-E1"] = {
        "discovery": "部分",
        "discovery_text": (f"部分：入口静态首轮 1 页；main/body 内入口前缀子链接 {sm['S1-R26-E1']} 个逐跳复核；"
                           "insights 分类/分页/动态加载与全部详情未枚举"),
        "rule": "无规则", "link": "可打开（入口 200）",
        "retained_extra": f"子链接与跳转链见 {EV}k5-redirects.jsonl（entry_id=S1-R26-E1）",
        "notes": ["[K5 已证实] " + "；".join(f"{r['url']} → {r['final_url']}" for r in mintel_red)
                  + "。其中 3 个地区链接（americas/asia/emea）跳到不相关的旧活动/文章页，按跳转源与目标分别登记，不据此泛化"],
        "queue_done": ["K5", "Q1-access"],
    }
    for eid in ("S1-R51-E1", "S1-R51-E2", "S1-R51-E3", "S1-R51-E4", "S1-R51-E6"):
        F[eid] = {
            "discovery": "未验证",
            "discovery_text": "未验证：站点返回 Cloudflare 挑战页（403，cf-mitigated: challenge，标题 Just a moment...），未绕过",
            "rule": "无规则", "link": "访问受限（站点 403 挑战页）",
            "notes": ["[K5] 前轮跳转样本本轮无法复核：入口被站点挑战页拦截（不是代理拒绝）。不使用绕过手段；需要授权会话或改由人工浏览器核验"],
            "queue_done": ["Q1-access"], "queue_blocked": ["K5"],
        }
    for eid in ("S1-R88-E1", "S1-R89-E1", "S1-R89-E2", "S1-R89-E3", "S1-R151-E2", "S1-R151-E3"):
        r = v[eid]
        F[eid] = {
            "discovery": "部分",
            "discovery_text": (f"部分：入口静态首轮 1 页（{r['identity']['text_chars']} 字正文，链接已入 edges）；"
                               "分页/详情/动态未处理"),
            "rule": "无规则", "link": f"可打开（200，标题「{r['identity']['title'][:60]}」）",
            "notes": ["前轮 403 已不复现：本轮 200，正文为真实栏目页而非挑战页"],
            "queue_done": ["Q1-access"],
        }
    return F


def deep_findings(ctx):
    F = {}
    snap_ok = all(r["actual"] == r["expected"] for r in ctx["snap_node"]["tests"]) and \
        all(r["pass"] for r in ctx["snap_py"]["results"])
    F["S1-R50-E3"] = {
        "discovery": "部分",
        "discovery_text": ("部分：根因已查清——列表页底部 More posts 调用 POST go.forrester.com/wp-admin/admin-ajax.php "
                           "action=loadposts&page=N&category=b2b-research，data-pages=62；/page/N/ 地址的静态正文不随页码变化。"
                           "成员集合经 WP REST GET（categories=50231）取得 1,222 篇（X-WP-Total=1222，与 62 页×20 吻合），"
                           "首页 16 篇全部在内；分类计数 1,287 与公开文章数差 65 未解释；loadposts POST 本轮未执行（权限拦截）"),
        "rule": f"候选：精确集合快照 R2-FORR-B2B-SNAP-01..{len(ctx['snap']['patterns']):02d}（有限集合相等{'通过' if snap_ok else '未通过'}）",
        "link": "可打开（入口 200）",
        "retained_extra": f"1,222 个成员见 {EV}evidence/forrester/b2b-research-members.json",
        "notes": ["[K1 根因] 第 2 页与第 1 页相同是因为服务端对 /page/N/ 不分页，真实分页走 admin-ajax loadposts",
                  "详情位于全站共享 /blogs/{slug}/：抽样 6 篇成员页均带 b2b-research 分类标记，4 篇其他分类同结构页无，证实不能泛化",
                  "快照只覆盖 2026-10-26 已确认的 1,222 篇，不覆盖未来文章；成员页落地仅抽查 6/1,222"],
        "queue_done": ["K1", "Q1-access", "Q3-paginate", "Q4-dynamic", "Q5-family"],
    }
    F["S1-R50-E4"] = {
        "discovery": "部分",
        "discovery_text": "部分：/page/2/ 静态返回与第 1 页相同的 16 篇（30/30 链接一致），JS 变量 current_page=2，仅影响 More posts 起始页；同栏目成员见 S1-R50-E3",
        "rule": "无规则（同栏目快照挂在 S1-R50-E3）", "link": "可打开（200，内容与第 1 页相同）",
        "notes": ["[K1] 服务器忽略 /page/N/ 页码的静态列表，不能当新增内容"],
        "queue_done": ["K1", "Q1-access"],
    }
    F["S1-R42-E1"] = {
        "discovery": "部分",
        "discovery_text": ("部分：入口显示「606 Results」，与前轮总数一致；组件 type 参数取值已查清（filter=首次/筛选，loadmore=加载更多）；"
                           "WP REST resource 类型 X-WP-Total=640，与 606 差 34 未解释；本轮未执行 filter_resources POST 与 REST 剩余 6 页（权限拦截）"),
        "rule": "无规则（线索：/resources/{blog|case-study|report|webinar|white-paper}/{slug}/，未测）",
        "link": "可打开（入口 200）",
        "retained_extra": f"首屏 8 条与组件参数见 {EV}evidence/numerator/k2-component-and-counts.json",
        "notes": ["[K2] 前轮未知的 type 取值已确定；URL 正则无法表达 POST body 条件；606 个详情/文件/外站跳转仍未逐项验收"],
        "queue_done": ["Q1-access"], "queue_blocked": ["K2"],
    }
    cs = next(r for r in ctx["v2"]["rules"] if r["id"] == "R2-CS-BLOG-DETAIL")
    F["S1-R121-E1"] = {
        "discovery": "部分",
        "discovery_text": ("部分：静态分页 /blog/page/N/ 共 32 页全部取得（页码连续、无重复页、末页 5 条），唯一详情 277 个；"
                           "sitemap_index.xml 截断（138 条，止于 f 开头）不能作全集对账，其中 6 篇不在列表；"
                           "筛选分支未处理；277 篇详情已逐一落地（274 正常、3 跳转到非文章页）"),
        "rule": f"候选：R2-CS-BLOG-DETAIL（机械门 {cs['mechanical_gate']}，留出 6 正 8 反全部正确）——待你确认范围后可升正式",
        "link": "可打开（入口 200）",
        "retained_extra": (f"277 个详情与 32 个分页见 {EV}probe/pages.jsonl、{EV}tests/identity-checks.jsonl；"
                           "跳转到非文章页的列表链接：" + "；".join(f"{x['url']}" for x in ctx["excluded"])),
        "notes": ["[K3] 本轮静态 HTML 已足够（前轮需渲染的情况不复现）",
                  "3 个列表链接会被候选规则匹配，但落地为 /blog/ 或 /guides/ux-design/，不是文章；是否接受由你决定"],
        "queue_done": ["K3", "Q1-access", "Q3-paginate", "Q5-family", "Q6-validate"],
    }
    yg = {"S1-R45-E1": ("economy", "完整（本次筛选条件下）", "接口 hits=1016，点击 28 次后按钮消失，页面取得 1,015 个内容链接（articles 899、reports 92、case-studies 13、guides 8、events 3），差 1 未解释"),
          "S1-R45-E2": ("consumer", "部分", "接口 hits=2717，本批 45 轮取得约 1,575 个内容链接（articles 1,300、reports 229…），剩余约 1,142 条待续跑"),
          "S1-R45-E3": ("reports", "部分", "接口 article_type=WhitePaperPage，hits=460，页面取得 456 个 /reports/ 链接，差 4 未解释"),
          "S1-R45-E4": ("sectors-consumer", "部分", "静态落地页，无 Load more；主体 30 个链接（articles/business/case-studies 等）")}
    for eid, (k, st, txt) in yg.items():
        F[eid] = {
            "discovery": "部分" if st != "完整（本次筛选条件下）" else "完整（本次筛选条件下）",
            "discovery_text": (f"{st}：浏览器渲染并点击 button.load-more（CSS 隐藏 Cookie 弹层，未点同意）；"
                               f"组件只读 GET api-test.yougov.com/public-content/content（limit=35，offset 递增）；{txt}"),
            "rule": "无规则（详情在全站共享 /articles/、/reports/ 等路径）",
            "link": "可打开（入口 200）",
            "retained_extra": f"成员链接与接口调用见 {EV}evidence/yougov/yg-{k}.json",
            "notes": ["[K4 已证实] 栏目详情落在共享路径，不能仅凭路径认定栏目成员；需要 regex 时只能做精确集合快照",
                      "本轮浏览器加载未再出现 d18w79e3uiqk2z.cloudfront.net 被拦截"]
                     + (["/reports/{id}-{slug} 可能是报告专属路径，列为下一轮候选"] if k == "reports" else []),
            "queue_done": ["K4", "Q1-access", "Q4-dynamic"] + (["Q3-paginate"] if k == "economy" else []),
        }
    for eid, rid, sec in (("S1-R129-E1", "R2-OPT-GUIDES-DETAIL", "guides"),
                          ("S1-R129-E2", "R2-OPT-ARTICLES-DETAIL", "articles")):
        n = 47 if sec == "guides" else 418
        F[eid] = {
            "discovery": "部分",
            "discovery_text": (f"部分：列表页静态与渲染均只展示 8 条（无分页/加载更多）；站点 sitemap 列出英文 {sec} {n} 个；"
                               "成员以 sitemap 为准，但未逐一落地，范围对账未完成"),
            "rule": f"候选（降级）：{rid} 机械门通过，但 sitemap 覆盖检查发现已知漏配（大写/末尾连字符 slug）",
            "link": "可打开（入口 200）",
            "notes": ["[K5 已处理] 列表链接带尾斜杠，308 跳到无尾斜杠最终地址；规则用 /?$ 同时覆盖两种实测形式",
                      "仅英文默认路径；/de/ 等语言版本作反例，不在入口范围"]
                     + (["v1 漏配双连字符 slug（…website--app），v2 放宽为 -+ 后重新冻结留出集"] if sec == "articles" else [])
                     + [f"覆盖检查：sitemap 英文 {sec} 成员中 {COVERAGE[rid]['unmatched']}/{COVERAGE[rid]['members']} 个不匹配，"
                        f"例如 {COVERAGE[rid]['example']}（实测 200，大小写不敏感，小写别名同文）；因此不列正式。"
                        f"v3 候选写法 {COVERAGE[rid]['v3']} 需另取独立样本验证"],
            "queue_done": ["K5", "Q1-access", "Q5-family", "Q6-validate"],
        }
    return F


# ---------------------------------------------------------------- rules

def rules_doc(ctx):
    node = {r["id"]: r for r in ctx["v2"]["rules"]}
    frozen = {r["id"]: r for r in ctx["frozen"]["rules"]}
    frozen.update({r["id"]: r for r in ctx["frozen2"]["rules"]})
    eng = [{"name": "node-re2", "version": ctx["v2"]["engine"]["version"], "runtime": ctx["v2"]["engine"]["runtime"]},
           {"name": "google-re2", "version": ctx["v2py"]["engine"]["version"], "runtime": ctx["v2py"]["engine"]["runtime"]}]

    def rec(rid, status):
        f, n = frozen[rid], node[rid]
        return {"id": rid, "status": status, "entry_ids": f["entry_ids"], "target": f["target"],
                "family": f["family"], "pattern": n["pattern"], "variables": f["variables"],
                "assumptions": f["assumptions"], "history": f.get("history", []),
                "metrics": n["metrics"], "mechanical_gate": n["mechanical_gate"], "checks": n["checks"],
                "engines": eng, "executed_at": ctx["v2"]["observed_at"],
                "tests": f"{EV}tests/v2-tests.json", "results": [f"{EV}tests/v2.node-re2.json", f"{EV}tests/v2.google-re2.json"],
                "frozen": {"v1_sha256": ctx["frozen"]["sha256"], **({"v2_sha256": ctx["frozen2"]["sha256"]} if f.get("history") else {})}}
    formal = []
    opt = []
    for rid in ("R2-OPT-GUIDES-DETAIL", "R2-OPT-ARTICLES-DETAIL"):
        r = rec(rid, "部分验证（候选，已知漏配）")
        r["coverage_check"] = COVERAGE[rid]
        r["why_not_formal"] = "机械门通过，但 sitemap 中已知成员存在漏配（大写字母、末尾连字符 slug），按准入标准不能列正式"
        opt.append(r)
    cs = rec("R2-CS-BLOG-DETAIL", "部分验证（候选）")
    cs["why_not_formal"] = ("3 个列表链接被匹配但落地为非文章页（" + "；".join(x["url"] for x in ctx["excluded"])
                            + "）。是否接受由用户决定；接受则可升正式")
    snap = {"id": "R2-FORR-B2B-SNAP", "status": "候选（精确集合快照）", "entry_ids": ["S1-R50-E3"],
            "target": "Forrester B2B Research 分类 2026-10-26 已确认的 1,222 篇文章（共享 /blogs/{slug}/ 路径）",
            "family": "共享路径精确集合快照", "patterns": ctx["snap"]["patterns"],
            "chunks": len(ctx["snap"]["patterns"]), "unique_url_count": ctx["snap"]["unique_url_count"],
            "finite_set_equality": {"members_matched_exactly_once": 1222, "negatives_matched": 0,
                                    "negatives": 27, "pairs": len(ctx["snap_node"]["tests"]),
                                    "engines": eng, "engines_agree": True},
            "limits": "不覆盖未来文章；成员来自 WP REST，页面落地仅抽查 6 篇；分类计数 1,287 与公开 1,222 差 65 未解释",
            "results": [f"{EV}tests/forrester-snapshot.node-re2.json.gz", f"{EV}tests/forrester-snapshot.google-re2.json.gz"]}
    return {"target_engine": "re2", "generated_at": RUN, "engines": eng,
            "formal": formal, "candidates": [cs, snap] + opt,
            "note": ("本轮 formal 为空：Optimizely 两条规则机械门通过但覆盖检查发现已知漏配，已降级。formal 仅收录：两套 RE2 实测、样本隔离（归纳=列表卡片，留出=sitemap 独立来源）、展示正例落地身份核验、"
                     "留出三指标≥95%、无已知未修复误配/漏配。留出样本量小（6 正 7 反），不外推总体可靠性。")}


# ---------------------------------------------------------------- assemble

def main(out):
    ctx = load(out)
    F = {}
    F.update(wipo_findings(ctx))
    F.update(static_findings(ctx))
    F.update(deep_findings(ctx))
    rules = rules_doc(ctx)
    formal = {r["id"]: r for r in rules["formal"]}
    host_conn = {}
    for eid, c in ctx["conn"].items():
        if eid != "dependency":
            host_conn[c["request_url"].split("/")[2]] = c
    retry = {r["request_url"]: r for r in ctx["retries"]}

    def conn_text(e):
        c = host_conn.get(e["host"])
        tested = c and c["request_url"] == e["raw"]
        if not c:
            return "待核验"
        rr = retry.get(c["request_url"])
        if c["outcome"] != "site_response":
            res = rr["result"] if rr else c.get("error", "")
            ok = rr and rr["result"].startswith("200")
            base = ("可打开（重试 200）" if ok else f"待核验（无站点状态码：{res[:80]}）")
        elif c["site_http_status"] == 200:
            base = "可打开（200）"
        else:
            base = f"访问受限（站点 {c['site_http_status']}{'，挑战页' if c.get('challenge_hint') else ''}，{c.get('server') or ''}）"
        return base if tested else f"待核验（本入口未请求；同 host 首入口 {c['entry_id']}：{base}）"

    entries, queue = [], []
    for e in ctx["entries"]:
        e = dict(e)
        e.pop("access_this_round", None)
        if e["kind"] == "path_entry":
            f = F.get(e["entry_id"])
            if f:
                e.update({"discovery_status": f["discovery"], "rule_status": f["rule"],
                          "link_status": f["link"], "round2": f})
            else:
                e.update({"discovery_status": "未验证", "rule_status": "无规则", "link_status": conn_text(e),
                          "round2": {"discovery_text": "未验证：本轮只处理优先级 1；仅做 host 级连通性测试",
                                     "notes": []}})
        entries.append(e)

    done = {(eid, q) for eid, f in F.items() for q in f.get("queue_done", [])}
    blocked = {(eid, q) for eid, f in F.items() for q in f.get("queue_blocked", [])}
    for q in ctx["queue"]:
        q = dict(q)
        key = (q["entry_id"], q["queue_id"].split("-", 3)[-1])  # e.g. ("S1-R19-E1", "K5"), (.., "Q1-access")
        if key in done:
            q["status"] = "done"
            q["result"] = F[q["entry_id"]]["discovery_text"]
        elif key in blocked:
            q["status"] = "blocked"
            q["result"] = F[q["entry_id"]]["discovery_text"]
        elif q["reason"] == "本轮网络策略拒绝目标站":
            q["reason"] = "网络已放开；本轮只处理优先级 1，尚未执行"
        queue.append(q)
    queue += new_queue_items()

    rows = defaultdict(list)
    for e in entries:
        rows[e["row"]].append(e)
    table = [row_fields(r, sorted(rows[r], key=lambda x: x["entry_index"]), formal) for r in sorted(rows)]

    r2 = out / "round2"
    dump(r2 / "entries.json", entries)
    dump(r2 / "rules.json", rules)
    dump(r2 / "queue.json", queue)
    write_table(r2, table)
    pe = [e for e in entries if e["kind"] == "path_entry"]
    summary = {
        "run": RUN,
        "path_entries": len(pe), "unique_path_urls": len({e["raw"] for e in pe}),
        "entries_by_discovery": dict(Counter(e["discovery_status"] for e in pe)),
        "entries_by_link_status": dict(Counter(e["link_status"].split("（")[0] for e in pe)),
        "formal_rules": len(rules["formal"]), "candidate_rules": len(rules["candidates"]),
        "snapshot_chunks": rules["candidates"][1]["chunks"],
        "test_pairs_generalized": len(ctx["v2"]["tests"]), "test_pairs_snapshot": len(ctx["snap_node"]["tests"]),
        "connectivity_hosts": dict(Counter((c["outcome"] if c["outcome"] != "site_response" else f"site_{c['site_http_status']}")
                                           for c in ctx["conn"].values())),
        "queue": {f"P{p}-{s}": n for (p, s), n in Counter((q["priority"], q["status"]) for q in queue).items()},
    }
    dump(r2 / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


def new_queue_items():
    def q(qid, eid, url, action, reason, prio=1, cursor=None):
        return {"queue_id": qid, "entry_id": eid, "url": url, "action": action, "reason": reason,
                "parent": None, "cursor": cursor, "priority": prio, "status": "pending", "added": "round2"}
    return [
        q("S1-R50-E3-R2a", "S1-R50-E3", "https://go.forrester.com/wp-admin/admin-ajax.php",
          "执行只读 POST action=loadposts page=1..62 category=b2b-research author=all，与 REST 1,222 篇逐一对账",
          "本轮被会话权限分类器拦截；需要你在设置中放行或确认", cursor={"page": 1, "data_pages": 62}),
        q("S1-R50-E3-R2b", "S1-R50-E3", "https://go.forrester.com/wp-json/wp/v2/categories/50231",
          "解释分类计数 1,287 与公开文章 1,222 的 65 篇差额（非公开状态？其他文章类型？）", "范围对账缺口"),
        q("S1-R42-E1-R2a", "S1-R42-E1", "https://www.numerator.com/wp-admin/admin-ajax.php",
          "只读 POST filter_resources（type=filter 后 loadmore，postperpage=8）枚举 606 条；或取 REST resource 剩余 6 页并解释 640−606=34",
          "本轮被会话权限分类器拦截", cursor={"insightsPaged": 1, "rest_page": 2}),
        q("S1-R45-E2-R2a", "S1-R45-E2", "https://yougov.com/content/consumer",
          "继续点击 Load more（或同一组件 GET offset≥1575）直至 hits=2717 对账", "本批 45 轮上限",
          cursor={"offset": 1575, "limit": 35, "hits": 2717}),
        q("S1-R45-E3-R2a", "S1-R45-E3", "https://yougov.com/reports",
          "评估 /reports/{id}-{slug} 是否为 WhitePaperPage 专属路径；冻结样本后做 RE2 验证；解释 460−456=4", "新候选线索"),
        q("S1-R121-E1-R2a", "S1-R121-E1", "https://contentsquare.com/blog/",
          "由你决定：R2-CS-BLOG-DETAIL 匹配 3 个已失效（跳到非文章页）的列表链接是否可接受；接受则升正式", "范围归属需用户决定"),
        q("S1-R129-ALL-R2a", "S1-R129-E1", "https://www.optimizely.com/field-notes/guides",
          "Optimizely guides/articles：按 v3 写法（允许大写与末尾连字符）重新冻结目标，sitemap 已全部读过只能作回归；"
          "另取独立来源（例如一段时间后列表新出现的卡片、站内其他页面引用）作留出；/thank-you 表单完成页归属需你决定",
          "v2 覆盖检查发现已知漏配"),
        q("S1-R121-E1-R2b", "S1-R121-E1", "https://contentsquare.com/blog/",
          "处理博客筛选分支；找到完整 sitemap 或其他全集来源对账 277 + 6", "范围对账缺口", prio=2),
        q("S1-R51-ALL-R2a", "S1-R51-E1", "https://www.gartner.com/en/marketing/insights",
          "Gartner 5 个入口被站点 Cloudflare 挑战页拦截：需授权访问方式或人工浏览器核验；不绕过", "访问受限"),
        q("HOSTS-R2a", "S1-R46-E1", "https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights",
          "McKinsey、Adobe（business.adobe.com）HTTP/2 流被重置，2 次重试均失败；稍后重试", "无站点状态码", prio=2),
        q("HOSTS-R2b", "S1-R3-E1", "https://www.bls.gov/cex/",
          "站点侧 403/429 的 host：bls.gov、bcg.com（Akamai）、campaignlive、lbbonline、searchengineland、vml、crunchbase、pitchbook、dealroom（Cloudflare）、adjust（Vercel 429）、transparency.meta.com（400）",
          "访问受限，按入口逐一确认", prio=2),
        q("S1-R19-ALL-R2a", "S1-R19-E1", "https://www.wipo.int/en/web/",
          "WIPO 门户入口：确定子页面栏目归属与范围后再决定规则/保留；对 /index 跳转按源与目标分别登记", "范围待定", prio=2),
        q("S1-R26-E1-R2a", "S1-R26-E1", "https://www.mintel.com/insights/",
          "Mintel insights 分类、分页与动态加载枚举；/trend-predictions/ 等跳转目标单独登记", "未枚举", prio=2),
    ]


def row_fields(row, es, formal):
    raw = "\n".join(e["raw"] for e in es)
    cell = {"原表行": row, COLUMN: raw}
    fields = {f: "" for f in RESULT_FIELDS}
    pe = [e for e in es if e["kind"] == "path_entry"]
    he = [e for e in es if e["kind"] == "host_exempt"]
    if not pe:
        if he:
            fields["结果类型"] = "host免提"
        return {**cell, **fields}
    pats, ret, samp, types, rv, src, cov, risk = [], [], [], [], [], [], [], [ROW_NOTE]
    for e in pe:
        f = e.get("round2", {})
        eid = e["entry_id"]
        fids = f.get("formal", [])
        for rid in fids:
            pats.append(formal[rid]["pattern"])
            m = formal[rid]["metrics"]["holdout"]
            samp.append(f"{eid} {rid}: " + "；".join(_samples(rid)))
            rv.append(f"{eid} {rid} 已验证：{ENG}；{formal[rid]['executed_at']}；留出 TP{m['TP']}/FP{m['FP']}/FN{m['FN']}/TN{m['TN']}，"
                      f"准确率/精确率/召回率 {m['accuracy']:.0%}/{m['precision']:.0%}/{m['recall']:.0%}（小样本）")
        if not fids:
            rv.append(f"{eid} {e['rule_status']}；链接 {e['link_status']}")
        types.append(f"E{e['entry_index']} " + ("正则+链接保留" if fids else "链接保留"))
        ret.append(f"{eid}: {e['raw']}" + (f"\n  {f['retained_extra']}" if f.get("retained_extra") else ""))
        src.append(f"{eid} = S1!{COLUMN} 第{e['row']}行 第{e['entry_index']}个入口: {e['raw']}")
        cov.append(f"{eid}: {f.get('discovery_text', e['discovery_status'])}；续跑见 {EV}queue.json")
        risk += [f"{eid} {n}" for n in f.get("notes", [])]
    for e in he:
        types.append(f"E{e['entry_index']} host免提")
    fields.update({"Pattern 正则": "\n".join(dict.fromkeys(pats)), "保留链接": "\n".join(ret),
                   "匹配样例": "\n".join(samp), "结果类型": "；".join(types),
                   "规则验证": "\n".join(rv), "来源映射": "\n".join(src),
                   "发现覆盖": "\n".join(cov), "备注与风险": "\n".join(risk)})
    return {**cell, **fields}


SAMPLES = {
    "R2-OPT-GUIDES-DETAIL": ["https://www.optimizely.com/field-notes/guides/ai-playbook/ →308→ https://www.optimizely.com/field-notes/guides/ai-playbook（列表链接，标题 The AI Playbook，200）",
                             "https://www.optimizely.com/field-notes/guides/big-book-of-dxp（留出，标题 The Big Book of DXP，200）"],
    "R2-OPT-ARTICLES-DETAIL": ["https://www.optimizely.com/field-notes/articles/does-llms-txt-work/ →308→ https://www.optimizely.com/field-notes/articles/does-llms-txt-work（列表链接，200）",
                               "https://www.optimizely.com/field-notes/articles/ai-in-commerce（留出，标题 AI in commerce，200）"],
}


def _samples(rid):
    return [s + "；公开访问，2026-10-26" for s in SAMPLES[rid]]


def dump(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
