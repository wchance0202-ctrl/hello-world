#!/usr/bin/env python3
"""Final verification of every row of the fill-in table.

Per row:
  1. syntax   - every line compiles in google-re2, starts with ^, ends with $, no .* / .+
  2. positives- every known real item URL of the row must match (list members, sitemap / search /
                user samples, snapshot lists, jump targets, rules carried from round 3)
  3. negatives- recorded negatives and the host's home page must not match
  4. live     - up to 2 matched positives re-opened today (fresh request, not the cache);
                hash routes and login/JS-gated sites use the browser records already taken
Writes fill/verify-report.json and prints the summary.
Usage: python3 -I fill/verify_all.py [--no-live]
"""
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import re2
import requests

HERE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BLOCKED = {"www.mckinsey.com", "www.bcg.com", "www.gartner.com", "dealroom.co", "searchengineland.com", "www.vml.com",
           "www.adjust.com", "business.adobe.com", "pitchbook.com", "www.campaignlive.com", "transparency.meta.com",
           "www.datastory.com.cn", "www.qixin.com", "www.iyiou.com", "syntun.com.cn", "www.syntun.com.cn", "www.vzkoo.com",
           "www.huiju.cool", "www.csm.com.cn", "www.chinapv.org.cn", "www.weiboyi.com", "qn.taobao.com", "mp.weixin.qq.com",
           "www.coalchina.org.cn", "www.linkflowtech.com"}
BROWSER = {"www.leadleo.com", "e.kuaishou.com", "www.alimama.com", "learn.incopat.com", "e.xiaohongshu.com",
           "e.bilibili.com", "geo.newrank.cn", "e.newrank.cn", "a.huiju.cool", "www.sensorsdata.cn"}


def positives(seq, dec, out, r3):
    ps = set(dec.get("members", []) or []) | set(dec.get("holdout", []) or [])
    for f in dec.get("families", []) or []:
        ps |= set(f.get("members", [])) | set(f.get("holdout", []) or [])
    ps |= set(dec.get("full_list", []) or [])
    ps |= set(out.get("jump_targets", []) or [])
    ps |= set(out.get("redirect_extra", []) or [])
    lp = HERE / "lists" / f"{seq:03d}.txt"
    if lp.exists():
        ps |= {l.strip() for l in lp.read_text(encoding="utf-8").split("\n") if l.strip()}
    cf = dec.get("carried_from")
    for rid in (cf if isinstance(cf, list) else [cf] if cf else []):
        r = r3.get(rid)
        if r:
            ps |= set(r["samples"]["inference"]) | set(r["samples"]["holdout_pos"])
    if dec.get("mode") == "selfpage":
        ps |= set(out.get("pages", []) or [])
    return sorted(ps)


def main(live=True):
    rows = json.loads((HERE / "rows.json").read_text(encoding="utf-8"))
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
    cache = {}
    for l in (HERE / "identity-cache.jsonl").read_text(encoding="utf-8").split("\n"):
        if l.strip():
            x = json.loads(l)
            cache[x["url"]] = x
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    last = {}
    report = []
    for row in rows:
        seq = row["seq"]
        out = json.loads((HERE / "out" / f"{seq:03d}.json").read_text(encoding="utf-8"))
        dec = json.loads((HERE / "dec" / f"{seq:03d}.json").read_text(encoding="utf-8"))
        pat = out.get("pattern") or ""
        lines = [l for l in pat.split("\n") if l]
        rec = {"seq": seq, "site": row["site"], "url": row["url"], "status": out.get("status"), "lines": len(lines)}
        if not lines:
            rec.update(result="无正则")
            report.append(rec)
            continue
        syn_bad = []
        rxs = []
        for l in lines:
            try:
                rxs.append(re2.compile(l))
            except Exception as e:  # noqa: BLE001
                syn_bad.append(f"编译失败 {str(e)[:40]}")
            if not (l.startswith("^") and l.endswith("$")) or ".*" in l or ".+" in l:
                syn_bad.append("格式不符")
        hit = lambda u: any(r.fullmatch(u) for r in rxs)  # noqa: E731
        pos = [u for u in positives(seq, dec, out, r3) if u.startswith("http")]
        dead = {d["url"] for d in out.get("dead_links", [])}
        pos = [u for u in pos if u not in dead]
        pos_fail = [u for u in pos if not hit(u)]
        rec["dead_links"] = len(dead)
        host = urlsplit(row["url"].split("#")[0] if "://" in row["url"] else "https://" + row["url"]).netloc
        negs = set(dec.get("negatives", []) or []) | {f"https://{host}/"}
        if out.get("status", "").startswith("单页") or "也匹配入口页" in (out.get("relax_note") or "") + (dec.get("note") or ""):
            negs.discard(row["url"].split("#")[0])
        neg_fail = [u for u in negs if hit(u) and u.rstrip("/") != row["url"].split("#")[0].rstrip("/")]
        rec.update(syntax="通过" if not syn_bad else "；".join(syn_bad), pos_total=len(pos), pos_fail=pos_fail[:5],
                   pos_fail_n=len(pos_fail), neg_total=len(negs), neg_fail=neg_fail[:5])
        # live spot check
        lv = []
        if live:
            cand = [u for u in pos if hit(u)]
            random.Random(seq).shuffle(cand)
            for u in cand[:2]:
                h = urlsplit(u).netloc
                if h in BLOCKED or h.endswith("weixin.qq.com"):
                    lv.append({"url": u, "result": "本环境无法访问（站点拦截/需登录/网络限制）"})
                    continue
                if h in BROWSER or re.search(r"#!?/", u):
                    c = cache.get(u, {})
                    ok = c.get("status") == 200
                    lv.append({"url": u, "result": ("浏览器记录 200" if ok else "浏览器记录未通过") if c else "需浏览器，未抽查"})
                    continue
                wait = 1.2 - (time.time() - last.get(h, 0))
                if wait > 0:
                    time.sleep(wait)
                try:
                    r = sess.get(u, timeout=25, allow_redirects=True, stream=True)
                    r.close()
                    lv.append({"url": u, "status": r.status_code, "final": r.url,
                               "result": "可打开" if r.status_code == 200 else f"返回 {r.status_code}"})
                except Exception as e:  # noqa: BLE001
                    lv.append({"url": u, "result": f"打开失败 {type(e).__name__}"})
                last[h] = time.time()
        rec["live"] = lv
        ok_static = not syn_bad and not pos_fail and not neg_fail
        rec["result"] = "通过" if ok_static else "有问题"
        report.append(rec)
        print(seq, rec["result"], len(pos), len(pos_fail), len(neg_fail), [x["result"] for x in lv], flush=True)
    (HERE / "verify-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(live="--no-live" not in sys.argv)
