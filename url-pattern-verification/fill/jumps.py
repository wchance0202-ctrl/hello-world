#!/usr/bin/env python3
"""Single-page rows: add the pages the page itself links to ("跳转页") and where they land.

For every row whose status is 单页: take the same-site links in the page's main content
(rendered in Chromium, scratchpad single/<seq>.json, plus the static crawl), drop the entry itself,
plain in-page anchors and non-page links, open each target once (identity check as elsewhere),
and add one exact-list line with the targets that open normally plus the URL each one lands on
when it redirects. Links to other sites are counted, not added. The entry page line stays first.
Status becomes 单页（含跳转页） when at least one target was added.
Usage: python3 -I fill/jumps.py <rendered_dir>
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_entry as RE  # noqa: E402
from links import links  # noqa: E402

SKIP = re.compile(r"^(mailto:|tel:|javascript:)|/(login|logout|register|signin|signup|cart|search)(\b|/|\?)|\.(jpg|jpeg|png|gif|svg|webp|css|js)$", re.I)
# site chrome that is not the page's own content: legal, company, account, help pages
CHROME_WORDS = re.compile(r"(privacy|cookie|agreement|terms|legal|compliance|disclaimer|infringement|law\.html|aboutus|about-us|/about/?$|/about/|about\.html|contact|careers|jobs|join|recovery|account|help|support|faq|sitemap|copyright|beian|icp|policy)", re.I)


def site(host):
    p = host.split(".")
    return ".".join(p[-3:]) if len(p) > 2 and p[-2] in ("com", "org", "net", "gov", "edu") else ".".join(p[-2:])


def main(rdir):
    rdir = Path(rdir)
    rows = {r["seq"]: r for r in json.loads((HERE / "rows.json").read_text(encoding="utf-8"))}
    sess = requests.Session()
    sess.headers.update({"User-Agent": RE.UA})
    # template links: present in the main content of 3+ other entry pages of the same host
    ents = {}
    for d0 in ("output/round3", "batch2/output/round3"):
        for e in json.loads((HERE.parent / d0 / "entries.json").read_text(encoding="utf-8")):
            if e["kind"] == "path_entry":
                ents[e["entry_id"]] = e["host"]
    by_host = {}
    for eid, h in ents.items():
        by_host.setdefault(h, []).append(eid)
    single_hosts = {urlsplit(r["url"]).netloc for r in rows.values()}
    want = [eid for h in single_hosts for eid in by_host.get(h, [])]
    L = links(want)
    for p in sorted((HERE / "out").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("status") not in ("单页", "单页（含跳转页）"):
            continue
        seq = d["seq"]
        entry = rows[seq]["url"].split("#")[0]
        own = site(urlsplit(entry).netloc)
        cand = set()
        rf = rdir / f"{seq}.json"
        eid0 = rows[seq]["entry_ids"][0]
        rendered = json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else {}
        if rendered.get("status") == 200:
            # rendered main content only (header/nav/footer/aside elements excluded by the renderer)
            for g in rendered.get("groups", []):
                cand |= {u for u, _ in g["samples"]}
        else:
            cand |= L.get(eid0, set())
        sib = [x for x in by_host.get(ents.get(eid0), []) if x != eid0]
        tcount = {}
        for x in sib:
            for u in L.get(x, set()):
                tcount[u] = tcount.get(u, 0) + 1
        template = {u for u, n in tcount.items() if n >= 3}
        clean, external = set(), set()
        for u in cand:
            if not u.startswith("http") or SKIP.search(u):
                continue
            u = u if re.search(r"#!?/", u) else u.split("#")[0]
            if u.rstrip("/") == entry.rstrip("/") or u in template:
                continue
            if urlsplit(u).path in ("", "/") or CHROME_WORDS.search(urlsplit(u).path + "?" + urlsplit(u).query):
                continue
            (clean if site(urlsplit(u).netloc) == own else external).add(u)
        kept, landed, dropped = [], set(), []
        for u in sorted(clean):
            rec = RE.fetch(sess, u)
            if rec.get("status") == 200 and (rec.get("title") or "html" not in rec.get("content_type", "html")):
                kept.append(u)
                f = rec.get("final_url") or u
                if f.rstrip("/") != u.rstrip("/") and site(urlsplit(f).netloc) == own:
                    landed.add(f)
            else:
                dropped.append(u)
        base = d.get("pattern_jump_base") or d.get("pattern_base") or d.get("pattern")
        d["pattern_jump_base"] = base
        targets = sorted(set(kept) | landed)
        d["jump_targets"] = targets
        d["jump_dropped"] = dropped
        d["jump_external"] = len(external)
        d["jump_template_excluded"] = len([u for u in cand if u in template])
        if targets:
            d["pattern"] = base + "\n^(?:" + "|".join(re.escape(u) for u in targets) + ")$"
            d["status"] = "单页（含跳转页）"
        else:
            d["pattern"] = base
            d["status"] = "单页"
        d["pattern_base"] = d["pattern"]  # redirects.py builds on this, so the jump line is kept
        d.pop("redirect_extra", None)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(seq, d["status"], "targets", len(targets), "dropped", len(dropped), "external", len(external))


if __name__ == "__main__":
    main(sys.argv[1])
