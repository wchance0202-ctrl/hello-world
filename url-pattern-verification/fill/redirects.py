#!/usr/bin/env python3
"""Redirect coverage: for every row with a pattern, look at the landing records of its column links
(fill/identity-cache.jsonl) and add the redirect targets the row's pattern does not match yet, as one
extra exact-list line. Targets that are not content pages are left out: verification pages
(captcha), the entry page itself, the site root, and one-segment list pages such as /blog/.
Idempotent: the extra line is rebuilt from scratch on every run (field redirect_extra).
Usage: python3 -I redirects.py
"""
import glob
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import re2

HERE = Path(__file__).resolve().parent


def main():
    cache = {}
    for l in (HERE / "identity-cache.jsonl").read_text(encoding="utf-8").split("\n"):
        if l.strip():
            r = json.loads(l)
            cache[r["url"]] = r
    changed = 0
    for p in sorted(glob.glob(str(HERE / "out" / "*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        base = d.get("pattern_base") or d.get("pattern")
        if not base:
            continue
        dec = json.loads(Path(p.replace("/out/", "/dec/")).read_text(encoding="utf-8"))
        ms = set(dec.get("members", [])) | set(dec.get("holdout", []))
        for f in dec.get("families", []):
            ms |= set(f.get("members", [])) | set(f.get("holdout", []))
        rxs = [re2.compile(x) for x in base.split("\n")]
        extra, skipped = set(), []
        for u in ms:
            c = cache.get(u)
            if not c or c.get("status") != 200:
                continue
            t = c.get("final_url") or u
            if t.rstrip("/") == u.rstrip("/") or any(r.fullmatch(t) for r in rxs):
                continue
            segs = [s for s in urlsplit(t).path.split("/") if s]
            if ("captcha" in t or t.rstrip("/") == d["url"].split("#")[0].rstrip("/") or len(segs) <= 1
                    and not urlsplit(t).query):
                skipped.append([u, t])
                continue
            extra.add(t)
        d["pattern_base"] = base
        d["redirect_extra"] = sorted(extra)
        d["redirect_skipped"] = skipped
        d["pattern"] = base + ("\n^(?:" + "|".join(re.escape(t) for t in sorted(extra)) + ")$" if extra else "")
        Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        changed += bool(extra)
    print("rows with redirect targets added:", changed)


if __name__ == "__main__":
    main()
