#!/usr/bin/env python3
"""Rebuild probe-summary.json / pagination-pending.json from visits.jsonl and edges.jsonl.

Used when probe_round1.py stopped before writing its summary (the summary is only written at
the end of a run). Follows the probe's own rule: a pagination link found on one of the entry's
pages, inside the entry's own path, and never visited, is pending; an entry with pending links
stopped at the page cap.

Usage: python3 -I rebuild_probe_summary.py <entries.json> <probe_dir> [--max-pages N] [--skip ENTRY_ID ...]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit


def jl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").split("\n") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries")
    ap.add_argument("probe")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()
    probe = Path(a.probe)
    visits = jl(probe / "visits.jsonl")
    done = {v["request_url"] for v in visits}
    pages = defaultdict(list)
    for v in visits:
        pages[v["entry_id"]].append(v)
    finals = {eid: {v["final_url"] for v in vs if v.get("final_url")} for eid, vs in pages.items()}
    pend = defaultdict(list)
    for ed in jl(probe / "edges.jsonl"):
        eid = ed["entry_id"]
        if ed.get("relation_hint") != "pagination_hint" or ed["parent_url"] not in finals.get(eid, ()):
            continue
        pend[eid].append((ed["resolved_url"].split("#", 1)[0], ed["parent_url"]))
    summary, pending = [], {}
    for e in json.loads(Path(a.entries).read_text(encoding="utf-8")):
        if e["kind"] != "path_entry" or e["entry_id"] in a.skip:
            continue
        eid = e["entry_id"]
        start = e.get("request_url") or e["raw"]
        ep = urlsplit(start)
        ebase = ep.path if ep.path.endswith("/") else ep.path.rsplit(".", 1)[0]
        left = []
        for u, parent in pend.get(eid, []):
            if urlsplit(u).path.startswith(ebase) and u not in done and all(u != x[0] for x in left):
                left.append([u, parent, "pagination"])
        n = len(pages.get(eid, []))
        summary.append({"entry_id": eid, "pages_requested": n, "pagination_pending": left,
                        "stop_reason": "queue_empty" if not left else f"max_pages={a.max_pages}",
                        "rebuilt_from_logs": True})
        pending[eid] = left
    (probe / "probe-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (probe / "pagination-pending.json").write_text(json.dumps(pending, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"entries": len(summary), "with_pending": sum(1 for s in summary if s["pagination_pending"])}))


if __name__ == "__main__":
    main()
