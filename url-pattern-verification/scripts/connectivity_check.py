#!/usr/bin/env python3
"""Connectivity check: one read-only GET per host (first path entry of each host).

Separates three outcomes that must not be confused:
  - proxy_refused: the session egress proxy rejected CONNECT (request never reached the site)
  - network_error: DNS/TLS/timeout/reset, no HTTP status from the site
  - site_response: the site answered; status, redirect hops, server and challenge markers recorded
A site 403 with a challenge marker is "access restricted", not "page broken".

Usage: python3 -I connectivity_check.py <entries.json> <out.jsonl> [--extra URL ...] [--workers N]
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
CHALLENGE = re.compile(r"(just a moment|attention required|verify you are human|cf-chl|"
                       r"captcha-delivery|px-captcha|access denied)", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probe(entry_id, url):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
    hops, cur, rec = [], url, {"entry_id": entry_id, "request_url": url, "method": "GET",
                               "observed_at": now()}
    for _ in range(10):
        try:
            r = s.get(cur, allow_redirects=False, timeout=30)
        except requests.exceptions.ProxyError as exc:
            rec.update(outcome="proxy_refused", site_http_status=None, error=str(exc)[:300])
            break
        except requests.RequestException as exc:
            rec.update(outcome="network_error", site_http_status=None,
                       error=f"{type(exc).__name__}: {exc}"[:300])
            break
        hops.append({"url": cur, "status": r.status_code, "location": r.headers.get("Location")})
        if r.is_redirect and r.headers.get("Location"):
            cur = urljoin(cur, r.headers["Location"])
            continue
        body = r.text[:20000] if "html" in (r.headers.get("Content-Type") or "") else ""
        m = TITLE.search(body)
        rec.update(outcome="site_response", site_http_status=r.status_code, final_url=cur,
                   server=r.headers.get("Server"), cf_mitigated=r.headers.get("cf-mitigated"),
                   content_type=r.headers.get("Content-Type"), bytes=len(r.content),
                   title=re.sub(r"\s+", " ", m.group(1)).strip()[:200] if m else None,
                   challenge_hint=bool(CHALLENGE.search(body[:8000])) or bool(r.headers.get("cf-mitigated")))
        break
    else:
        rec.update(outcome="network_error", site_http_status=None, error="too many redirects")
    rec["hops"] = hops
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries")
    ap.add_argument("out")
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    ents = json.load(open(a.entries, encoding="utf-8"))
    first = {}
    for e in ents:
        if e["kind"] == "path_entry":
            first.setdefault(e["host"], (e["entry_id"], e["raw"]))
    jobs = list(first.values()) + [("dependency", u) for u in a.extra]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        recs = list(ex.map(lambda j: probe(*j), jobs))
    with open(a.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tally = {}
    for r in recs:
        k = r["outcome"] if r["outcome"] != "site_response" else f"site_{r['site_http_status']}"
        tally[k] = tally.get(k, 0) + 1
    json.dump({"hosts": len(recs), "tally": tally}, sys.stdout, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
