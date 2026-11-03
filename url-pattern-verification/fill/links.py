"""Helper: all main-content links of an entry (static edges + render anchors), optional key filter."""
import gzip, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from structs import key, ok, BATCHES, MAIN  # noqa
_pages = {}
def pages(eid):
    if not _pages:
        for d in BATCHES:
            for l in (d / "probe/visits.jsonl").read_text(encoding="utf-8").split("\n"):
                if l.strip():
                    v = json.loads(l)
                    if v.get("status") == 200 and v.get("final_url"):
                        _pages.setdefault(v["entry_id"], set()).add(v["final_url"])
    return _pages.get(eid, set())
def links(eids, kfilter=None, regions=MAIN):
    eids = set(eids); out = {e: set() for e in eids}
    for d in BATCHES:
        with gzip.open(d / "probe/edges.jsonl.gz", "rt", encoding="utf-8") as f:
            for l in f:
                if not any(e in l for e in eids): continue
                ed = json.loads(l)
                if ed["entry_id"] in eids and ed["region"] in regions and ed["parent_url"] in pages(ed["entry_id"]):
                    u = ed["resolved_url"]
                    if ok(u) and (kfilter is None or re.search(kfilter, key(u))): out[ed["entry_id"]].add(u)
        for e in eids:
            p = d / "render" / f"{e}.json"
            if p.exists():
                for a in json.loads(p.read_text(encoding="utf-8")).get("anchors", []):
                    u = a.get("href") or ""
                    if a.get("region") in regions and ok(u) and (kfilter is None or re.search(kfilter, key(u))): out[e].add(u)
    return out
