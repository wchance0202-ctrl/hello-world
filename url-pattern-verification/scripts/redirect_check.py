#!/usr/bin/env python3
"""Redirect-chain check for discovered child links (read-only GET, manual redirects).

Records every hop (HTTP Location), the final URL, status, title and whether the
final URL differs from the requested one. Serial per host, hosts in parallel;
resumable (URLs already in the output are skipped).

Usage: python3 -I redirect_check.py <targets.json> <out.jsonl> [--delay S] [--workers N]
targets.json: [{"entry_id": ..., "url": ..., "parent_url": ...}, ...]
"""
import argparse
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
REFRESH = re.compile(r"<meta[^>]+http-equiv=[\"']?refresh[^>]+url=([^\"'>]+)", re.I)
_lock = Lock()


def check(session, url):
    hops, cur = [], url
    for _ in range(10):
        try:
            r = session.get(cur, allow_redirects=False, timeout=30)
        except requests.RequestException as exc:
            return hops, None, None, f"{type(exc).__name__}: {exc}"[:300]
        hops.append({"url": cur, "status": r.status_code, "location": r.headers.get("Location")})
        if r.is_redirect and r.headers.get("Location"):
            cur = urljoin(cur, r.headers["Location"])
            continue
        body = r.text if "html" in (r.headers.get("Content-Type") or "") else ""  # <title> can sit late in a big <head>
        m, mr = TITLE.search(body), REFRESH.search(body)
        info = {"content_type": r.headers.get("Content-Type"),
                "title": re.sub(r"\s+", " ", m.group(1)).strip()[:200] if m else None,
                "meta_refresh": urljoin(cur, mr.group(1).strip()) if mr else None}
        return hops, r.status_code, info, None
    return hops, None, None, "too many redirects"


def run_host(items, out, delay):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
    for t in items:
        hops, status, info, err = check(s, t["url"])
        final = hops[-1]["url"] if hops else None
        rec = {**t, "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "method": "GET", "hops": hops, "final_url": final, "status": status,
               "redirected": bool(final and final != t["url"]), "error": err, **(info or {})}
        with _lock, open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        sleep(delay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets")
    ap.add_argument("out")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    out = Path(a.out)
    done = set()
    if out.exists():
        done = {json.loads(l)["url"] for l in out.read_text(encoding="utf-8").split("\n") if l.strip()}
    by_host = defaultdict(list)
    seen = set(done)
    for t in json.loads(Path(a.targets).read_text(encoding="utf-8")):
        if t["url"] not in seen:
            seen.add(t["url"])
            by_host[urlsplit(t["url"]).netloc].append(t)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(lambda items: run_host(items, out, a.delay), by_host.values()))
    print(json.dumps({"requested": sum(len(v) for v in by_host.values()), "skipped_done": len(done)}))


if __name__ == "__main__":
    main()
