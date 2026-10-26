#!/usr/bin/env python3
"""Round 3 (full run): final ledger, rules, queue and result table for all 268 path entries.

Offline. Combines:
  output/entries.json                        round-1 ledger (ids, rows, raw values)
  output/round2/rules.json, entries.json     round-2 manual findings (priority-1 items)
  output/round3/probe/*, render/*, families.json, samples-frozen.json, coverage.json,
  output/round3/tests/r3.node-re2.json, r3.google-re2.json
Writes into output/round3/: entries.json, rules.json, queue.json, result-table.csv|xlsx,
retained/<entry_id>.txt, summary.json

Formal admission (per extract-url-patterns): node-re2 mechanical gate passed, google-re2
agrees on every pair, coverage check without misses (all listing members of the family and
all same-structure sitemap URLs match), no induction sample redirected to another page, and
the rule matches nothing on the host sitemap outside its structural family.

Usage: python3 -I apply_round3.py <output_dir>
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_ledger import COLUMN, RESULT_FIELDS, ROW_NOTE, write_table  # noqa: E402

RUN = "2026-10-26（第 3 轮：全量）"
EV = "output/round3/"


# Facts established by hand (round 2 / this round) that the automatic checks cannot see.
RULE_OVERRIDES = {
    "R3-S1-R121-E1-F1": "第 2 轮已知 3 个列表链接被匹配但跳到非文章页（/blog/、/guides/ux-design/），是否接受由用户决定",
}
DISCOVERY_OVERRIDES = {
    "S1-R50-E3": ("部分", "页面 More posts 点到按钮消失，列表 1,221 篇，全部在 WP REST 1,222 篇内；未在列表出现的 1 篇已定位"
                          "（id 122415，2018-05-09）；分类计数 1,287 与公开 1,222 差 65 未解释"),
    "S1-R45-E1": ("部分", "Load more 点到按钮消失：接口 hits=1016，页面内容链接 1,015，差 1 未解释"),
    "S1-R45-E2": ("部分", "Load more 点到按钮消失（76 次）：接口 hits=2717，页面内容链接 2,660，差 57 未解释"),
}


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").split("\n") if l.strip()] if p.exists() else []


def main(out):
    r3 = out / "round3"
    base = json.loads((out / "entries.json").read_text(encoding="utf-8"))
    r2e = {e["entry_id"]: e for e in json.loads((out / "round2/entries.json").read_text(encoding="utf-8"))}
    r2rules = json.loads((out / "round2/rules.json").read_text(encoding="utf-8"))
    fams = {r["entry_id"]: r for r in json.loads((r3 / "families.json").read_text(encoding="utf-8"))}
    frozen = json.loads((r3 / "samples-frozen.json").read_text(encoding="utf-8"))
    v2p = r3 / "samples-frozen-v2.json"
    if v2p.exists():
        newer = {r["id"]: r for r in json.loads(v2p.read_text(encoding="utf-8"))["rules"]}
        frozen["rules"] = [newer.get(r["id"], r) for r in frozen["rules"]]
    cov = json.loads((r3 / "coverage.json").read_text(encoding="utf-8"))
    node = json.loads((r3 / "tests/r3.node-re2.json").read_text(encoding="utf-8"))
    py = json.loads((r3 / "tests/r3.google-re2.json").read_text(encoding="utf-8"))
    visits = jl(r3 / "probe/visits.jsonl")
    summ = {s["entry_id"]: s for s in json.loads((r3 / "probe/probe-summary.json").read_text(encoding="utf-8"))}
    render = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in (r3 / "render").glob("S1-*.json")}
    sm_trunc = {x["host"] for x in json.loads((r3 / "sitemaps/_summary.json").read_text(encoding="utf-8"))
                if x["truncated"]} if (r3 / "sitemaps/_summary.json").exists() else set()

    agree = {}
    pyres = {(r["rule_id"], r["url"], r["split"]): r for r in py["results"]}
    for t in node["tests"]:
        p = pyres.get((t["rule_id"], t["url"], t["split"]))
        agree.setdefault(t["rule_id"], True)
        if not p or p["actual"] != t["actual"]:
            agree[t["rule_id"]] = False
    nrule = {r["id"]: r for r in node["rules"]}
    eng = [{"name": "node-re2", "version": node["engine"]["version"]},
           {"name": "google-re2", "version": py["engine"]["version"]}]

    rules_formal, rules_cand, rules_fail = [], [], []
    by_entry_rules = defaultdict(list)
    for fr in frozen["rules"]:
        rid = fr["id"]
        nr, cv = nrule[rid], cov[rid]
        reasons = []
        if nr["mechanical_gate"] != "passed":
            reasons.append("机械门未通过：" + "、".join(gate_failures(nr)))
        if not agree.get(rid):
            reasons.append("两套引擎结果不一致")
        if cv["listing_missed"]:
            reasons.append(f"列表成员漏配 {len(cv['listing_missed'])}")
        if cv["sitemap_missed_count"]:
            reasons.append(f"sitemap 同结构 URL 漏配 {cv['sitemap_missed_count']}")
        if fr["inference_redirected_away"]:
            reasons.append(f"归纳样本跳到其他页面 {len(fr['inference_redirected_away'])}")
        if cv["matched_outside_structure"]:
            reasons.append(f"匹配到家族结构外的 sitemap URL {len(cv['matched_outside_structure'])}")
        if rid in RULE_OVERRIDES:
            reasons.append(RULE_OVERRIDES[rid])
        h = nr["metrics"]["holdout"]
        rec = {"id": rid, "entry_ids": fr["entry_ids"], "target": fr["target"], "family": fr["family"],
               "pattern": fr["pattern"], "variables": fr["variables"], "literals": fr["literals"],
               "slash_mode": fr["slash_mode"], "holdout_source": fr["holdout_source"],
               "metrics": nr["metrics"], "checks": nr["checks"], "engines": eng, "engines_agree": agree.get(rid),
               "coverage": {k: (v if not isinstance(v, list) else v[:20]) for k, v in cv.items()},
               "samples": {"inference": fr["inference"], "holdout_pos": fr["holdout_pos"], "holdout_neg": fr["holdout_neg"],
                           "regression_pos": fr.get("regression_pos", []), "regression_neg": fr.get("regression_neg", [])},
               "version": fr.get("version", 1), "history": fr.get("history", [])}
        if not reasons:
            rec["status"] = "已验证"
            rules_formal.append(rec)
        elif nr["mechanical_gate"] != "passed" and (h["FN"] or h["FP"]):
            rec["status"] = "验证不通过"
            rec["why"] = reasons
            rules_fail.append(rec)
        else:
            rec["status"] = "部分验证（候选）"
            rec["why"] = reasons
            rules_cand.append(rec)
        by_entry_rules[fr["entry_ids"][0]].append(rec)

    dropped = defaultdict(list)
    for d in frozen.get("dropped", []):
        dropped[d["entry_id"]].append(d)

    entries, queue = [], []
    (r3 / "retained").mkdir(exist_ok=True)
    for e in base:
        e = {k: v for k, v in e.items() if k not in ("access_this_round",)}
        if e["kind"] != "path_entry":
            entries.append(e)
            continue
        eid = e["entry_id"]
        v0 = next((v for v in visits if v["entry_id"] == eid and v["relation"] == "entry"), None)
        fr = fams.get(eid, {})
        ident = (v0 or {}).get("identity") or {}
        status = (v0 or {}).get("status")
        blocked = status != 200 or ident.get("challenge_hint")
        rs = by_entry_rules.get(eid, [])
        formal_ids = [r["id"] for r in rs if r["status"] == "已验证"]
        r2 = r2e.get(eid, {}).get("round2") or {}
        notes = list(r2.get("notes", []))
        if blocked:
            if status in (403, 429, 400):
                link = f"访问受限（站点 {status}{'，挑战页' if ident.get('challenge_hint') else ''}：{(ident.get('title') or '')[:40]}）"
            else:
                link = f"待核验（无站点状态码：{((v0 or {}).get('error') or '未请求')[:80]}）"
            disc = "未验证"
            disc_text = f"未验证：入口{link}；未使用任何绕过手段"
        else:
            link = f"可打开（200，标题「{(ident.get('title') or '')[:50]}」）"
            s = summ.get(eid, {})
            pend = len(s.get("pagination_pending", []))
            pages = s.get("pages_requested", 0)
            rd = render.get(eid)
            rd_txt = ""
            if rd:
                rounds = rd.get("rounds", [])
                clicked = sum(1 for x in rounds if x.get("clicked"))
                rd_txt = f"；浏览器渲染 {len(rounds)} 轮、点击加载更多 {clicked} 次、渲染后链接 {len(rd.get('anchors', []))}"
            gaps = [(r["id"], cov[r["id"]]["sitemap_not_in_listing"]) for r in rs if cov.get(r["id"])]
            gap_n = sum(g for _, g in gaps)
            thin_unresolved = ident.get("thin_static_html") and not rd
            fam_n = len(fr.get("families", []))
            n_links = fam_n + len(fr.get("outside_prefix", [])) + len(fr.get("under_prefix_singletons", []))
            complete = pend == 0 and not thin_unresolved and gap_n == 0 and n_links > 0 and \
                (not rd or not rd.get("rounds") or not rd["rounds"][-1].get("clicked"))
            reconciled = fam_n > 0 and all(cov[r["id"]]["sitemap_same_structure"] > 0 for r in rs if cov.get(r["id"]))
            # sitemap members the listing does not show: explained when the host sitemap is complete
            # (not truncated) and a formal rule matches every same-structure sitemap URL of that family
            gap_explained = gap_n > 0 and e["host"] not in sm_trunc and all(
                r["status"] == "已验证" and not cov[r["id"]]["sitemap_missed_count"]
                for r in rs if cov.get(r["id"]) and cov[r["id"]]["sitemap_not_in_listing"])
            complete_merged = (pend == 0 and not thin_unresolved and gap_explained and
                               (not rd or not rd.get("rounds") or not rd["rounds"][-1].get("clicked")))
            if complete:
                disc = "完整" if reconciled else "完整（枚举结束，无独立全集对账）"
            elif complete_merged:
                disc = "完整（列表+sitemap 合并枚举）"
            else:
                disc = "部分"
            disc_text = (f"{disc}：静态请求 {pages} 页（入口+分页），未完成分页 {pend}{rd_txt}；"
                         f"前缀 {fr.get('prefix')} 下家族 {fam_n} 个、成员 {sum(len(f['members']) for f in fr.get('families', []))}；"
                         f"前缀外同站链接 {len(fr.get('outside_prefix', []))}、文件 {len(fr.get('files', []))}")
            if gaps:
                disc_text += "；sitemap 中同结构但不在列表的 URL：" + "、".join(f"{rid.rsplit('-', 1)[-1]}={n}" for rid, n in gaps)
            if fam_n == 0:
                disc_text += "；未发现可归纳的下级家族（下级链接不足 3 个同结构或均在前缀外）"
            if r2.get("discovery_text"):
                disc_text += f"\n  第 2 轮人工复核：{r2['discovery_text']}"
            if eid in DISCOVERY_OVERRIDES:
                disc, why = DISCOVERY_OVERRIDES[eid]
                disc_text = f"{disc}：{why}\n  " + disc_text
        # retained links: everything known that no formal rule covers
        import re2
        frx = [re2.compile(r["pattern"]) for r in rs if r["status"] == "已验证"]
        known = []
        for f in fr.get("families", []):
            known += [(u, f"family {f['id']}") for u in f["members"]]
        known += [(u, "under_prefix_other") for u in fr.get("under_prefix_singletons", [])]
        known += [(u, "outside_prefix_same_site") for u in fr.get("outside_prefix", [])]
        known += [(u, "file") for u in fr.get("files", [])]
        retained = [(u, why) for u, why in dict(known).items() if not any(x.fullmatch(u) for x in frx)]
        rp = r3 / "retained" / f"{eid}.txt"
        rp.write_text("".join(f"{u}\t{why}\n" for u, why in retained), encoding="utf-8")
        rule_status = "；".join(f"{r['id']} {r['status']}" + (f"（{'；'.join(r['why'])}）" if r.get("why") else "")
                                for r in rs) or "无规则"
        if r2.get("rule"):
            rule_status += f"；第 2 轮：{r2['rule']}"
        for d in dropped.get(eid, []):
            notes.append(f"{d['id']} 未成规则：{d['why']}")
        e.update({"discovery_status": disc, "rule_status": rule_status, "link_status": link,
                  "round3": {"discovery_text": disc_text, "rules": [r["id"] for r in rs], "formal": formal_ids,
                             "retained_count": len(retained), "retained_file": f"{EV}retained/{eid}.txt",
                             "prefix": fr.get("prefix"), "notes": notes}})
        entries.append(e)
        queue += queue_for(e, rs, cov, summ.get(eid, {}), blocked, r2)

    # round-2 candidates (manual) stay listed
    for c in r2rules["candidates"]:
        c = dict(c)
        c["round"] = 2
        rules_cand.append(c)
    rules = {"target_engine": "re2", "generated_at": RUN, "engines": eng,
             "formal": rules_formal, "candidates": rules_cand, "failed": rules_fail,
             "note": "formal 只收录满足准入的规则；留出样本量小，不外推总体可靠性；自动归纳的栏目边界是入口路径前缀"}

    rows = defaultdict(list)
    for e in entries:
        rows[e["row"]].append(e)
    formal = {r["id"]: r for r in rules_formal}
    table = [row_fields(r, sorted(rows[r], key=lambda x: x["entry_index"]), formal) for r in sorted(rows)]
    dump(r3 / "entries.json", entries)
    dump(r3 / "rules.json", rules)
    dump(r3 / "queue.json", queue)
    write_table(r3, table)
    pe = [e for e in entries if e["kind"] == "path_entry"]
    summary = {"run": RUN, "path_entries": len(pe),
               "discovery": dict(Counter(e["discovery_status"] for e in pe)),
               "link": dict(Counter(e["link_status"].split("（")[0] for e in pe)),
               "entries_with_formal_rule": sum(1 for e in pe if e.get("round3", {}).get("formal")),
               "rules_formal": len(rules_formal), "rules_candidate": len(rules_cand), "rules_failed": len(rules_fail),
               "retained_links": sum(e.get("round3", {}).get("retained_count", 0) for e in pe),
               "test_pairs": len(node["tests"]), "queue_open": len(queue),
               "queue_by_reason": dict(Counter(q["reason"] for q in queue))}
    dump(r3 / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


def gate_failures(nr):
    c, h = nr["checks"], nr["metrics"]["holdout"]
    bad = []
    if c["inference_positives"] < 3:
        bad.append(f"归纳正例 {c['inference_positives']}<3")
    if c["holdout_positives"] < 1:
        bad.append("无独立留出正例（sitemap、后续分页、其他页面、详情页链接均无同结构样本）")
    if c["holdout_negatives"] < 3:
        bad.append(f"留出反例 {c['holdout_negatives']}<3")
    if c["duplicate_samples"]:
        bad.append("样本重复")
    if c["observed_split_overlap"]:
        bad.append("留出与归纳/回归重叠")
    if not c["positives_have_identity"]:
        bad.append("有正例未完成落地身份核验")
    if not c["all_labeled_tests_pass"]:
        bad.append(f"标注测试有失败（留出 FN{h['FN']}/FP{h['FP']}）")
    if c["holdout_positives"] >= 1 and any(x is not None and x < 0.95 for x in (h["accuracy"], h["precision"], h["recall"])):
        bad.append("留出指标 <95%")
    return bad or ["其他"]


def queue_for(e, rs, cov, s, blocked, r2):
    eid, url = e["entry_id"], e["raw"]
    q = []

    def add(kind, action, reason, cursor=None):
        q.append({"queue_id": f"{eid}-R3-{kind}", "entry_id": eid, "url": url, "action": action,
                  "reason": reason, "cursor": cursor, "status": "pending"})
    if blocked:
        add("access", "站点拦截或无响应：需要授权的访问方式、白名单或人工浏览器核验；不绕过", "访问受限")
        return q
    if s.get("pagination_pending") and e["discovery_status"] == "部分":
        add("paginate", f"继续分页 {len(s['pagination_pending'])} 个待访问页", "单入口 300 页上限",
            cursor=s["pagination_pending"][:5])
    for r in rs:
        c = cov[r["id"]]
        if c["sitemap_not_in_listing"] and e["discovery_status"] == "部分":
            add(f"gap-{r['id'].rsplit('-', 1)[-1]}",
                f"{r['id']}：sitemap 有 {c['sitemap_not_in_listing']} 个同结构 URL 不在列表中，确认是否为本栏目成员/列表未展示",
                "范围对账缺口")
        if r["status"] != "已验证":
            add(f"rule-{r['id'].rsplit('-', 1)[-1]}", f"{r['id']}：{'；'.join(r.get('why', []))}", "规则未达正式准入")
    if r2.get("queue_blocked"):
        add("r2", "第 2 轮受阻项（见 round2/queue.json）", "权限拦截/挑战页")
    return q


def row_fields(row, es, formal):
    cell = {"原表行": row, COLUMN: "\n".join(e["raw"] for e in es)}
    fields = {f: "" for f in RESULT_FIELDS}
    pe = [e for e in es if e["kind"] == "path_entry"]
    he = [e for e in es if e["kind"] == "host_exempt"]
    if not pe:
        if he:
            fields["结果类型"] = "host免提"
        return {**cell, **fields}
    pats, ret, samp, types, rv, src, cov, risk = [], [], [], [], [], [], [], [ROW_NOTE]
    for e in pe:
        x, eid = e["round3"], e["entry_id"]
        for rid in x["formal"]:
            r = formal[rid]
            pats.append(r["pattern"])
            h = r["metrics"]["holdout"]
            ex = r["samples"]["holdout_pos"][:1] + r["samples"]["inference"][:1]
            samp.append(f"{eid} {rid}: " + "；".join(ex) + "（已落地核验 200，公开访问，2026-10-26）")
            rv.append(f"{eid} {rid} 已验证：node-re2 {r['engines'][0]['version']} + google-re2 {r['engines'][1]['version']} 逐对一致；"
                      f"留出({r['holdout_source']}) TP{h['TP']}/FP{h['FP']}/FN{h['FN']}/TN{h['TN']}；"
                      f"覆盖检查：列表 {r['coverage']['listing_members']} 个、sitemap 同结构 {r['coverage']['sitemap_same_structure']} 个全部匹配")
        rv.append(f"{eid} 规则：{e['rule_status']}；链接 {e['link_status']}")
        types.append(f"E{e['entry_index']} " + ("正则+链接保留" if x["formal"] else "链接保留"))
        ret.append(f"{eid}: {e['raw']}\n  其余 {x['retained_count']} 个未被正式规则覆盖的已知目标见 {x['retained_file']}")
        src.append(f"{eid} = S1!{COLUMN} 第{e['row']}行 第{e['entry_index']}个入口: {e['raw']}")
        cov.append(f"{eid}: {x['discovery_text']}；续跑见 {EV}queue.json")
        risk += [f"{eid} {n}" for n in x["notes"]]
        if x.get("prefix") == "/":
            risk.append(f"{eid} 入口为站点首页，自动归纳范围为全站")
    for e in he:
        types.append(f"E{e['entry_index']} host免提")
    fields.update({"Pattern 正则": "\n".join(dict.fromkeys(pats)), "保留链接": "\n".join(ret),
                   "匹配样例": "\n".join(samp), "结果类型": "；".join(types), "规则验证": "\n".join(rv),
                   "来源映射": "\n".join(src), "发现覆盖": "\n".join(cov), "备注与风险": "\n".join(risk)})
    return {**cell, **fields}


def dump(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
