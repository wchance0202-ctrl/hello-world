#!/usr/bin/env python3
"""Fetch a few detail pages and record the links on them (read-only GET).

Used as an extra independent holdout source for families that have no sitemap pool,
no later pagination pages and no links on other entries' pages: links found on the
family's own detail pages (related items etc.) are not part of the listing pages the
rule was induced from. Serial per host, hosts in parallel.

Usage: python3 -I detail_links.py <targets.json> <out.jsonl> [--delay S]
targets.json: [{"family_id": ..., "entry_id": ..., "url": ...}, ...]
Output lines look like probe edges: {"entry_id": "detail:<family_id>", "parent_url", "resolved_url", "region"}
"""
import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
_lock = Lock()


def run_host(items, out, delay):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
    for t in items:
        try:
            r = s.get(t["url"], timeout=30)
        except requests.RequestException:
            continue
        if r.status_code != 200 or "html" not in (r.headers.get("Content-Type") or ""):
            continue
        soup = BeautifulSoup(r.text, "lxml")
        rows = []
        for a in soup.find_all("a", href=True):
            region = next((p.name for p in a.parents if p.name in ("header", "nav", "footer", "aside", "main")), "body")
            rows.append({"entry_id": f"detail:{t['family_id']}", "parent_url": r.url,
                         "resolved_url": urljoin(r.url, a["href"].strip()), "region": region})
        with _lock, open(out, "a", encoding="utf-8") as f:
            for x in rows:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        sleep(delay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets")
    ap.add_argument("out")
    ap.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args()
    by_host = defaultdict(list)
    for t in json.loads(Path(a.targets).read_text(encoding="utf-8")):
        by_host[urlsplit(t["url"]).netloc].append(t)
    with ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(lambda v: run_host(v, a.out, a.delay), by_host.values()))
    print(json.dumps({"targets": sum(len(v) for v in by_host.values())}))


if __name__ == "__main__":
    main()
