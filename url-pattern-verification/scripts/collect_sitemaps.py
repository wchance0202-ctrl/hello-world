#!/usr/bin/env python3
"""Collect sitemap URLs per host (read-only GET): robots.txt Sitemap lines, else
/sitemap.xml, /sitemap_index.xml, /sitemap-index.xml. Follows sitemap indexes
(gzip handled). Serial per host, hosts in parallel; caps per host keep it bounded.

Sitemaps are an independent membership source for holdout samples and coverage
checks; they are not proof that a URL belongs to a given column.

Usage: python3 -I collect_sitemaps.py <entries.json> <out_dir> [--max-files N] [--max-urls N]
Writes <out_dir>/<host>.txt (one <loc> per line) and <out_dir>/_summary.json
"""
import argparse
import gzip
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)


def get(s, url):
    try:
        r = s.get(url, timeout=40)
    except requests.RequestException as exc:
        return None, f"{type(exc).__name__}"
    body = r.content
    if body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except OSError:
            pass
    return r.status_code, body.decode("utf-8", "replace")


def host_job(host, out, max_files, max_urls):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    log = {"host": host, "robots": None, "files": [], "urls": 0, "truncated": False}
    st, txt = get(s, f"https://{host}/robots.txt")
    seeds = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", txt or "") if st == 200 else []
    log["robots"] = st
    if not seeds:
        seeds = [f"https://{host}/sitemap.xml", f"https://{host}/sitemap_index.xml",
                 f"https://{host}/sitemap-index.xml"]
    queue, seen, urls = list(dict.fromkeys(seeds)), set(), []
    while queue and len(seen) < max_files and len(urls) < max_urls:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        st, txt = get(s, sm)
        locs = LOC.findall(txt or "") if st == 200 else []
        is_index = bool(re.search(r"<sitemapindex", txt or "", re.I))
        log["files"].append({"url": sm, "status": st, "index": is_index, "locs": len(locs)})
        if is_index:
            queue += [l for l in locs if l not in seen]
        else:
            urls += locs
        time.sleep(0.5)
    if queue or len(urls) >= max_urls:
        log["truncated"] = True
        log["pending_files"] = queue[:50]
    urls = list(dict.fromkeys(u.replace("&amp;", "&") for u in urls))[:max_urls]
    (out / f"{host}.txt").write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    log["urls"] = len(urls)
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries")
    ap.add_argument("out")
    ap.add_argument("--max-files", type=int, default=150)
    ap.add_argument("--max-urls", type=int, default=300000)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hosts = sorted({e["host"] for e in json.loads(Path(a.entries).read_text(encoding="utf-8"))
                    if e["kind"] == "path_entry"})
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        logs = list(ex.map(lambda h: host_job(h, out, a.max_files, a.max_urls), hosts))
    (out / "_summary.json").write_text(json.dumps(logs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"hosts": len(logs), "with_urls": sum(1 for l in logs if l["urls"]),
                      "urls": sum(l["urls"] for l in logs),
                      "truncated": sum(1 for l in logs if l["truncated"])}))


if __name__ == "__main__":
    main()
