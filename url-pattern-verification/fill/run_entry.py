#!/usr/bin/env python3
"""Mechanics for one row of the fill-in pass (prompt-fill-regex.md, sections 1.4 and 4).

Input: a decision JSON (one row):
  {"seq", "entry_id", "url", "mode": "regex" | "snapshot" | "empty",
   "members": [...]            # the column's item URLs found (listing, all pages)
   "holdout": [...]            # optional independent positives (sitemap / later pages / other pages)
   "negatives": [...]          # real same-site URLs that must NOT match (entry page, siblings, ...)
   "exclusivity": {...}        # evidence collected (free form, copied to the record)
   "probe_others": [...]       # optional: same-structure URLs NOT in members, to membership-check
   "backlink": "/path"         # optional: path whose link in a page's main content marks membership
   "pattern": "..."            # optional: hand-written pattern (else induced from inference set)
   "basis": "...", "note": "..."}
regex mode: freezes a seeded split (1/4 of members, max 6, when no holdout given) before
induction, induces the pattern from the inference set only (literal where constant, character
class from observed characters otherwise), runs google-re2, opens every positive (identity: 200,
title, final URL == request up to a trailing slash), and checks coverage against all members.
snapshot mode: exact-set pattern of the members; every member opened.
Writes fill/out/<seq>.json and prints a one-line summary.
"""
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import re2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from analyze_r3 import char_class, raw_qsl  # noqa: E402

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
CHROME = re.compile(r"<(header|nav|footer)\b.*?</\1>", re.I | re.S)
OUT = Path(__file__).resolve().parent / "out"
CACHE = Path(__file__).resolve().parent / "identity-cache.jsonl"
SEED = 20261103
_last = {}
_cache = {}
if CACHE.exists():
    for l in CACHE.read_text(encoding="utf-8").split("\n"):
        if l.strip():
            r = json.loads(l)
            _cache[r["url"]] = r


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(sess, url, keep_html=False):
    if url in _cache and not keep_html:
        return _cache[url]
    host = urlsplit(url).netloc
    wait = 1.2 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    rec = {"url": url, "observed_at": now()}
    try:
        r = sess.get(url, timeout=30, allow_redirects=True, stream=True)
        _last[host] = time.time()
        raw = b""
        if "html" in r.headers.get("content-type", ""):
            for chunk in r.iter_content(65536):
                raw += chunk
                if len(raw) > 3_000_000:
                    break
        r.close()
        html = raw.decode(r.encoding or r.apparent_encoding or "utf-8", errors="replace") if raw else ""
        m = TITLE.search(html)
        rec.update(status=r.status_code, final_url=r.url, hops=[h.status_code for h in r.history],
                   title=re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else None,
                   content_type=r.headers.get("content-type", "")[:40])
        if keep_html:
            rec["_html"] = html
    except Exception as e:  # noqa: BLE001
        _last[host] = time.time()
        rec.update(status=None, error=f"{type(e).__name__}: {str(e)[:120]}")
    if not keep_html:
        _cache[url] = rec
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def browser_identity(urls):
    """Open URLs in Chromium (bident.js) for sites that answer plain HTTP with a script check."""
    import subprocess
    need = [u for u in urls if _cache.get(u, {}).get("method") != "browser"]
    if need:
        tmp = OUT.parent / "bident-tmp.json"
        tmp.write_text(json.dumps(need), encoding="utf-8")
        subprocess.run(["node", str(OUT.parent / "bident.js"), str(tmp)], check=False, capture_output=True, timeout=60 * len(need) + 60)
        for l in CACHE.read_text(encoding="utf-8").split("\n"):
            if l.strip():
                r = json.loads(l)
                if r.get("method") == "browser":
                    _cache[r["url"]] = r


SAME_PAGE_SUFFIX = []  # set per decision: redirect targets that are the same page plus a fixed tracking suffix


def identity_ok(rec):
    if rec.get("status") != 200:
        return False
    ct = rec.get("content_type", "")
    is_file = any(k in ct for k in ("pdf", "spreadsheet", "excel", "msword", "presentation", "zip", "octet-stream", "openxmlformats", "vnd.ms-"))
    if not rec.get("title") and not is_file:
        return False
    if any(rec["final_url"] == rec["url"] + sfx for sfx in SAME_PAGE_SUFFIX):
        return True
    return rec["final_url"].rstrip("/") == rec["url"].rstrip("/")


def parts(u):
    p = urlsplit(u)
    segs = p.path.split("/")
    return p.scheme + "://" + p.netloc, segs, raw_qsl(p.query), p.path.endswith("/"), p.fragment


def induce(urls):
    base, segs0, q0, slash0, frag0 = parts(urls[0])
    P = [parts(u) for u in urls]
    if any(len(p[1]) != len(segs0) or [k for k, _ in p[2]] != [k for k, _ in q0] or p[0] != base for p in P):
        raise ValueError("members do not share one structure")
    out = []
    for i in range(len(segs0)):
        vals = {p[1][i] for p in P}
        if len(vals) == 1:
            out.append(re.escape(next(iter(vals))))
            continue
        exts = {v.rsplit(".", 1)[1] if "." in v else "" for v in vals}
        if len(exts) == 1 and next(iter(exts)) and all("." in v for v in vals):
            ext = next(iter(exts))
            out.append(char_class({v.rsplit(".", 1)[0] for v in vals}) + re.escape("." + ext))
        else:
            out.append(char_class(vals))
    pat = "^" + re.escape(base) + "/".join(out)
    if q0:
        qs = []
        for i, (k, _) in enumerate(q0):
            vals = {p[2][i][1] for p in P}
            qs.append(re.escape(k) + "=" + (re.escape(next(iter(vals))) if len(vals) == 1 else char_class(vals)))
        pat += r"\?" + "&".join(qs)
    return pat + "$"


def backlinked(sess, url, path):
    rec = fetch(sess, url, keep_html=True)
    html = CHROME.sub(" ", rec.pop("_html", "") or "")
    hit = bool(re.search(r'href=["\'](?:https?://[^/"\']+)?' + re.escape(path) + r'["\'#?/]', html))
    return {"url": url, "status": rec.get("status"), "title": rec.get("title"), "backlink": hit}


def run_regex(d, sess, members, rec):
    hold = sorted(set(d.get("holdout", [])) - set(members))
    src = "independent"
    if not hold:
        k = min(6, max(1, len(members) // 4))
        hold = sorted(random.Random(f"{SEED}-{d['entry_id']}").sample(members, k)) if len(members) >= 4 else []
        src = "listing_split"
    inf_all = [u for u in members if u not in hold]
    inf = inf_all if len(inf_all) <= 12 else sorted(random.Random(f"{SEED}i-{d['entry_id']}").sample(inf_all, 12))
    frozen = {"inference": inf, "holdout_pos": hold, "holdout_neg": d.get("negatives", []), "holdout_source": src}
    rec["frozen_sha256"] = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
    # induction uses every non-holdout member (characters observed in the listing), never holdout
    pat = d.get("pattern") or induce(inf_all)
    rx = re2.compile(pat)
    if d.get("browser"):
        browser_identity(inf + hold)
    tests = [(u, True, "inference") for u in inf] + [(u, True, "holdout") for u in hold] + \
            [(u, False, "holdout") for u in d.get("negatives", [])]
    res, excluded = [], []
    for u, exp, split in tests:
        if exp:
            ir = fetch(sess, u)
            if not identity_ok(ir):
                excluded.append({"url": u, "status": ir.get("status"), "final": ir.get("final_url"), "split": split})
                continue
        res.append({"url": u, "expected": exp, "actual": rx.fullmatch(u) is not None, "split": split})
    fails = [r for r in res if r["expected"] != r["actual"]]
    n = lambda split, exp: sum(1 for r in res if r["split"] == split and r["expected"] == exp)  # noqa: E731
    cov_miss = [u for u in members + hold if not rx.fullmatch(u)]
    checks = {"inference_pos": n("inference", True), "holdout_pos": n("holdout", True),
              "holdout_neg": n("holdout", False), "all_pass": not fails, "coverage_missed": cov_miss[:20],
              "coverage_members": len(members)}
    excl = d.get("exclusivity", {})
    if d.get("probe_others") and d.get("backlink"):
        ctrl = [backlinked(sess, u, d["backlink"]) for u in members[:3]]
        oth = [backlinked(sess, u, d["backlink"]) for u in d["probe_others"][:10]]
        excl["membership_probe"] = {"controls": ctrl, "others": oth}
    ok = (checks["inference_pos"] >= 3 and checks["holdout_pos"] >= 1 and checks["holdout_neg"] >= 3
          and not fails and not cov_miss and excl.get("proved", False))
    rec.update(pattern=pat, status="已验证" if ok else "候选", checks=checks, failures=fails,
               identity_excluded=excluded, frozen=frozen, engine={"name": "google-re2"}, exclusivity=excl)
    if not ok:
        why = []
        if checks["inference_pos"] < 3: why.append(f"归纳正例 {checks['inference_pos']}<3")
        if checks["holdout_pos"] < 1: why.append("无留出正例")
        if checks["holdout_neg"] < 3: why.append(f"反例 {checks['holdout_neg']}<3")
        if fails: why.append(f"测试失败 {len(fails)} 对")
        if cov_miss: why.append(f"覆盖漏配 {len(cov_miss)}")
        if not excl.get("proved"): why.append("专属性未证明：" + excl.get("why_not", "缺证据"))
        rec["why_not_verified"] = why


def main(dec_path):
    d = json.loads(Path(dec_path).read_text(encoding="utf-8"))
    SAME_PAGE_SUFFIX[:] = d.get("same_page_suffix", [])
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    rec = {k: d.get(k) for k in ("seq", "entry_id", "url", "mode", "basis", "note", "exclusivity")}
    rec["observed_at"] = now()
    members = sorted(set(d.get("members", [])))
    if d["mode"] == "empty":
        rec.update(pattern="", status="留空")
    elif d["mode"] == "carry":
        # rule verified in an earlier round; evidence referenced, not re-run here
        rx = re2.compile(d["pattern"])
        negfail = [u for u in d.get("negatives", []) if rx.fullmatch(u)]
        posfail = [u for u in d.get("members", []) if not rx.fullmatch(u)]
        rec.update(pattern=d["pattern"], status=d["status"] if not (negfail or posfail) else "候选",
                   carried_from=d.get("carried_from"), checks={"members": len(d.get("members", [])), "pos_fail": posfail,
                                                               "neg": len(d.get("negatives", [])), "neg_fail": negfail})
    elif d["mode"] == "snapshot":
        pat = "^(?:" + "|".join(re.escape(u) for u in members) + ")$"
        if d.get("browser"):
            browser_identity(members)
        ids = [fetch(sess, u) for u in members]
        bad = [i for i in ids if not identity_ok(i)]
        keep = [u for u, i in zip(members, ids) if identity_ok(i)]
        pat = "^(?:" + "|".join(re.escape(u) for u in keep) + ")$" if keep else ""
        rx = re2.compile(pat) if pat else None
        negfail = [u for u in d.get("negatives", []) if rx and rx.fullmatch(u)]
        rec.update(pattern=pat, status="快照" if pat and not negfail else "留空", members=len(members),
                   kept=len(keep), dropped=[{"url": i["url"], "status": i.get("status"), "final": i.get("final_url")} for i in bad],
                   negatives=d.get("negatives", []), negatives_matched=negfail)
    elif d.get("families"):
        subs = []
        allm = [u for f in d["families"] for u in f["members"]]
        for i, f in enumerate(d["families"], 1):
            fd = dict(d, **f, entry_id=f"{d['entry_id']}-F{i}")
            fd["negatives"] = d.get("negatives", []) + [u for u in allm if u not in f["members"]][:6]
            fd["exclusivity"] = dict(d.get("exclusivity", {}), **f.get("exclusivity", {}))
            sub = {}
            run_regex(fd, sess, sorted(set(f["members"])), sub)
            subs.append(sub)
        order = ["已验证", "候选"]
        rec.update(pattern="\n".join(x["pattern"] for x in subs), families=subs,
                   status=max((x["status"] for x in subs), key=order.index),
                   checks={"families": len(subs)}, why_not_verified=[w for x in subs for w in x.get("why_not_verified", [])] or None)
    else:
        run_regex(d, sess, members, rec)
    OUT.mkdir(exist_ok=True)
    (OUT / f"{d['seq']:03d}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"seq": d["seq"], "status": rec["status"], "pattern": rec.get("pattern", "")[:140],
                      "checks": {k: v for k, v in (rec.get("checks") or {}).items() if k != "coverage_missed"},
                      "why": rec.get("why_not_verified"), "excluded": len(rec.get("identity_excluded", []))},
                     ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
