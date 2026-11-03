#!/usr/bin/env python3
"""Per-entry URL-structure report for the fill-in pass.

For every entry of both batches (so cross-entry checks see all columns of a site), collect the
links found in the main content (static edges in body/main regions + rendered anchors in BODY/MAIN)
of the entry's own pages, group them by a structure key (numeric segments -> {n}, last segment ->
{x}, query values -> {v}) and report, per structure: distinct URLs, whether it is under the entry
prefix, how many OTHER entries of the same host also show that structure in their main content,
and how many sitemap URLs of the host have that structure.

Usage: python3 -I structs.py <rows.json> <out.json>
"""
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
BATCHES = [ROOT / "output/round3", ROOT / "batch2/output/round3"]
MAIN = {"body", "main", "BODY", "MAIN"}
SKIP_EXT = re.compile(r"\.(?:js|css|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|mp4|mp3)$", re.I)


def ok(u):
    try:
        urlsplit(u)
        return u.startswith("http")
    except ValueError:
        return False


def key(u):
    p = urlsplit(u)
    segs = [s for s in p.path.split("/") if s]
    out = []
    for i, s in enumerate(segs):
        last = i == len(segs) - 1
        stem, dot, ext = s.rpartition(".") if last and "." in s else (s, "", "")
        if re.fullmatch(r"[0-9]+", stem):
            v = "{n}"
        elif last or re.fullmatch(r"[0-9a-fA-F]{12,}", stem):
            v = "{x}"
        else:
            v = stem
        out.append(v + (dot + ext if dot else ""))
    k = p.netloc + "/" + "/".join(out) + ("/" if p.path.endswith("/") and segs else "")
    if p.query:
        k += "?" + "&".join(kv.split("=", 1)[0] + ("={v}" if "=" in kv else "") for kv in p.query.split("&"))
    if p.fragment.startswith(("/", "!/")):
        k += "#" + re.sub(r"=[^&]*", "={v}", p.fragment)
    return k


def main(rows_path, out_path):
    entries = {}
    for d in BATCHES:
        for e in json.loads((d / "entries.json").read_text(encoding="utf-8")):
            if e["kind"] == "path_entry":
                e["_dir"] = d
                entries[e["entry_id"]] = e
    fams = {}
    for d in BATCHES:
        for f in json.loads((d / "families.json").read_text(encoding="utf-8")):
            fams[f["entry_id"]] = f
    # pages per entry and main-region links per entry
    pages = defaultdict(set)
    for d in BATCHES:
        for l in (d / "probe/visits.jsonl").read_text(encoding="utf-8").split("\n"):
            if l.strip():
                v = json.loads(l)
                if v.get("status") == 200 and v.get("final_url"):
                    pages[v["entry_id"]].add(v["final_url"])
    links = defaultdict(dict)  # eid -> url -> text
    for d in BATCHES:
        with gzip.open(d / "probe/edges.jsonl.gz", "rt", encoding="utf-8") as f:
            for l in f:
                ed = json.loads(l)
                if ed["region"] in MAIN and ed["parent_url"] in pages.get(ed["entry_id"], ()):
                    u = ed["resolved_url"]
                    if ok(u) and not SKIP_EXT.search(urlsplit(u).path):
                        links[ed["entry_id"]].setdefault(u.split("#", 1)[0] if not re.search(r"#!?/", u) else u,
                                                         ed.get("text", ""))
        for p in (d / "render").glob("*.json"):
            r = json.loads(p.read_text(encoding="utf-8"))
            eid = p.stem
            for a in r.get("anchors", []):
                u = a.get("href") or ""
                if a.get("region") in MAIN and ok(u) and not SKIP_EXT.search(urlsplit(u).path):
                    links[eid].setdefault(u.split("#", 1)[0] if not re.search(r"#!?/", u) else u, a.get("text", ""))
    # sitemap structure counts per host
    sm_cache = {}

    def sitemap_keys(host):
        if host in sm_cache:
            return sm_cache[host]
        cnt = defaultdict(int)
        for d in BATCHES:
            for name in ("sitemaps", "sitemaps-full", "sitemaps-pew"):
                p = d / name / f"{host}.txt.gz"
                if p.exists():
                    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
                        for l in f:
                            u = l.strip().split("\t")[0]
                            if ok(u):
                                cnt[key(u.split("#", 1)[0])] += 1
        sm_cache[host] = cnt
        return cnt

    by_host = defaultdict(list)
    for eid, e in entries.items():
        by_host[e["host"]].append(eid)
    rows = json.loads(Path(rows_path).read_text(encoding="utf-8"))
    report = []
    for r in rows:
        eid = r["entry_ids"][0]
        e = entries[eid]
        f = fams.get(eid, {})
        prefix = f.get("prefix") or (e.get("round3") or {}).get("prefix") or ""
        groups = defaultdict(list)
        for u in links.get(eid, {}):
            if urlsplit(u).netloc.split(".")[-2:] == e["host"].split(".")[-2:]:
                groups[key(u)].append(u)
        others = {o: {key(u) for u in links.get(o, {})} for o in by_host[e["host"]] if o != eid}
        smk = sitemap_keys(e["host"])
        structs = []
        for k, us in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(us) < 2:
                continue
            host = k.split("/", 1)[0]
            path = "/" + k.split("/", 1)[1] if "/" in k else "/"
            structs.append({"key": k, "n": len(us), "in_prefix": host == e["host"] and path.startswith(prefix or "/\0"),
                            "other_entries_with_key": sorted(o for o, ks in others.items() if k in ks),
                            "sitemap_n": smk.get(k, 0), "samples": sorted(us)[:3] + sorted(us)[-2:],
                            "texts": [links[eid][u][:30] for u in sorted(us)[:3]]})
        report.append({"seq": r["seq"], "site": r["site"], "url": r["url"], "entry_id": eid, "host": e["host"],
                       "prefix": prefix, "status": e.get("discovery_status"), "pages": len(pages.get(eid, ())),
                       "n_links": len(links.get(eid, {})), "same_host_entries": len(by_host[e["host"]]),
                       "has_sitemap": bool(smk), "structs": structs[:12]})
    Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(report))


if __name__ == "__main__":
    main(*sys.argv[1:])
