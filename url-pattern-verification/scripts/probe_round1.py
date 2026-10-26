#!/usr/bin/env python3
"""Round-1 discovery probe: entry access, identity, link ledger, pagination hints.

Resumable: entries (and pagination pages) already present in visits.jsonl are
not requested again. Requests are serial per host; hosts run in parallel.
Read-only GETs only; no login, captcha or paywall handling.

Usage:
  python3 -I probe_round1.py <entries.json> <out_dir> [--max-pages N] [--delay S]
      [--only ENTRY_ID ...] [--workers N]
Outputs (appended): visits.jsonl, edges.jsonl, pages.jsonl; rewritten each run:
probe-summary.json (this run only) and pagination-pending.json (carried into the next run).
"""
import argparse
import hashlib
import json
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
FILE_EXT = re.compile(r"\.(pdf|xlsx?|csv|docx?|pptx?|zip)$", re.I)
PAGE_HINT = re.compile(r"(/page/[0-9]+/?$)|([?&](page|p|paged|pg|start|offset)=[0-9]+)", re.I)
CHALLENGE = re.compile(r"(just a moment|attention required|access denied|verify you are human|"
                       r"cf-chl|captcha-delivery|px-captcha)", re.I)
REGIONS = ("header", "nav", "footer", "aside", "main")
_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(path, rec):
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_done(path):
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["request_url"])
    return done


def fetch(session, url, max_hops=10):
    """GET with manual redirects so every hop is recorded."""
    hops, cur = [], url
    for _ in range(max_hops):
        try:
            r = session.get(cur, allow_redirects=False, timeout=30)
        except requests.RequestException as exc:
            return hops, None, f"{type(exc).__name__}: {exc}"[:300]
        hops.append({"url": cur, "status": r.status_code, "location": r.headers.get("Location")})
        if r.is_redirect and r.headers.get("Location"):
            cur = urljoin(cur, r.headers["Location"])
            continue
        return hops, r, None
    return hops, None, "too many redirects"


def region_of(a):
    for p in a.parents:
        if p.name in REGIONS:
            return p.name
        role = (p.get("role") or "") if hasattr(p, "get") else ""
        if role in ("navigation", "banner", "contentinfo"):
            return {"navigation": "nav", "banner": "header", "contentinfo": "footer"}[role]
    return "body"


def identity(resp, soup):
    text = soup.get_text(" ", strip=True) if soup else ""
    title = soup.title.get_text(strip=True) if soup and soup.title else None
    h1 = soup.find("h1").get_text(" ", strip=True) if soup and soup.find("h1") else None
    canon = soup.find("link", rel="canonical") if soup else None
    main = soup.find("main") if soup else None
    main_text = main.get_text(" ", strip=True) if main else text
    return {
        "content_type": resp.headers.get("Content-Type"),
        "bytes": len(resp.content),
        "title": title, "h1": h1,
        "canonical": canon.get("href") if canon else None,
        "text_chars": len(text),
        "text_sha256": hashlib.sha256(main_text.encode()).hexdigest(),
        # keyword hits are a hint only; the main body must be read before calling it a challenge
        "challenge_hint": bool(CHALLENGE.search(text[:5000])) and len(main_text) < 2000,
        "thin_static_html": len(main_text) < 500,
    }


def links(base, soup, entry):
    out = []
    ehost, epath = urlsplit(entry).netloc, urlsplit(entry).path
    eprefix = epath if epath.endswith("/") else epath.rsplit(".", 1)[0] + "/"
    page_url_nofrag = base.split("#", 1)[0]
    for pos, a in enumerate(soup.find_all("a", href=True)):
        raw = a["href"].strip()
        if raw.lower().startswith(("mailto:", "tel:", "javascript:")):
            rel = "non_http_action"
            resolved = raw
        else:
            resolved = urljoin(base, raw)
            sp = urlsplit(resolved)
            if resolved.split("#", 1)[0] == page_url_nofrag and sp.fragment and not sp.fragment.startswith("!"):
                rel = "same_page_anchor"  # never counted as a content page
            elif sp.netloc != ehost:
                rel = "external"
            elif FILE_EXT.search(sp.path):
                rel = "file"
            elif PAGE_HINT.search(resolved) or "next" in (a.get("rel") or []):
                rel = "pagination_hint"
            elif sp.path.startswith(eprefix) and sp.path != epath:
                rel = "child_under_entry_prefix"
            else:
                rel = "same_host_other"
        out.append({"raw_target": raw, "resolved_url": resolved, "relation_hint": rel,
                    "region": region_of(a), "position": pos,
                    "text": a.get_text(" ", strip=True)[:160]})
    return out


def main_detail_set(edges):
    return sorted({e["resolved_url"].split("#", 1)[0] for e in edges
                   if e["region"] in ("main", "body")
                   and e["relation_hint"] in ("child_under_entry_prefix", "same_host_other")})


def probe_host(host, ents, out, args, done, pending):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
    summary = []
    for e in ents:
        queue = [(e["raw"], None, "entry")] + [tuple(q) for q in pending.get(e["entry_id"], [])]
        seen_sets, n = {}, 0
        while queue and n < args.max_pages:
            url, parent, rel = queue.pop(0)
            if url in done:
                continue
            n += 1
            hops, resp, err = fetch(s, url)
            done.add(url)
            rec = {"entry_id": e["entry_id"], "request_url": url, "parent_url": parent,
                   "relation": rel, "method": "GET", "observed_at": now(), "hops": hops,
                   "final_url": hops[-1]["url"] if hops else None,
                   "status": resp.status_code if resp is not None else None,
                   "error": err}
            soup = None
            if resp is not None and "html" in (resp.headers.get("Content-Type") or ""):
                soup = BeautifulSoup(resp.text, "lxml")
                rec["identity"] = identity(resp, soup)
            append(out / "visits.jsonl", rec)
            if soup is None:
                time.sleep(args.delay)
                continue
            es = links(rec["final_url"], soup, e["raw"])
            for x in es:
                append(out / "edges.jsonl", {"entry_id": e["entry_id"], "parent_url": rec["final_url"],
                                             "method": "static_html", "observed_at": rec["observed_at"],
                                             "scope_decision": "pending", **x})
            dset = main_detail_set(es)
            dup_of = next((u for u, st in seen_sets.items() if st == dset and dset), None)
            seen_sets[url] = dset
            append(out / "pages.jsonl", {"entry_id": e["entry_id"], "url": url, "relation": rel,
                                         "main_link_count": len(dset), "duplicate_of": dup_of,
                                         "observed_at": rec["observed_at"]})
            if dup_of:
                # same main-link set as an earlier page: page parameter likely ignored or cached
                time.sleep(args.delay)
                continue
            for x in es:
                if x["relation_hint"] == "pagination_hint":
                    u = x["resolved_url"].split("#", 1)[0]
                    if u not in done and all(u != q[0] for q in queue):
                        queue.append((u, url, "pagination"))
            time.sleep(args.delay)
        summary.append({"entry_id": e["entry_id"], "pages_requested": n,
                        "pagination_pending": [list(q) for q in queue if q[0] not in done],
                        "stop_reason": "queue_empty" if not queue else f"max_pages={args.max_pages}"})
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries")
    ap.add_argument("out")
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    from pathlib import Path
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ents = [e for e in json.loads(Path(args.entries).read_text(encoding="utf-8"))
            if e["kind"] == "path_entry" and (not args.only or e["entry_id"] in args.only)]
    done = load_done(out / "visits.jsonl")
    pend_path = out / "pagination-pending.json"
    pending = json.loads(pend_path.read_text(encoding="utf-8")) if pend_path.exists() else {}
    by_host = defaultdict(list)
    for e in ents:
        by_host[e["host"]].append(e)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(probe_host, h, es, out, args, done, pending) for h, es in by_host.items()]
        summary = [s for f in futs for s in f.result()]
    for srec in summary:
        pending[srec["entry_id"]] = srec["pagination_pending"]
    pend_path.write_text(json.dumps(pending, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "probe-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    print(json.dumps({"entries": len(summary),
                      "pages": sum(s["pages_requested"] for s in summary)}))


if __name__ == "__main__":
    main()
