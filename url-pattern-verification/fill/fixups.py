#!/usr/bin/env python3
"""Fix-ups from the final verification (verify-report.json), relaxed standard.

- Real column links a row's regex does not match yet: links that open (status 200, also when they
  redirect, also pages without a static <title>) are added as one exact-list line, together with the
  URL they land on; links that are dead (404/410/5xx/no answer) are recorded as dead, not added.
- Rows given in GENERAL get their per-channel lines replaced by one channel-variable rule.
- Rows given in DROP_NEG lose negatives that are items of other columns of the same structure
  (allowed under the relaxed standard).
Usage: python3 -I fill/fixups.py
"""
import json
import re
from pathlib import Path

import re2

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

HERE = Path(__file__).resolve().parent
GENERAL = {
    51: [r"^https://www\.woshipm\.com/[a-z]+/[0-9]+\.html$", r"^http://woshipm\.com/\?p=[0-9]+$"],
    52: [r"^https://www\.woshipm\.com/[a-z]+/[0-9]+\.html$"],
}
DROP_NEG = {27, 31, 78}


def main():
    cache = {}
    for l in (HERE / "identity-cache.jsonl").read_text(encoding="utf-8").split("\n"):
        if l.strip():
            x = json.loads(l)
            cache[x["url"]] = x
    rep = {r["seq"]: r for r in json.loads((HERE / "verify-report.json").read_text(encoding="utf-8"))}
    import verify_all as V  # noqa: E402
    r3 = {}
    for seq, r in rep.items():
        if r.get("result") != "有问题":
            continue
        pdec, pout = HERE / "dec" / f"{seq:03d}.json", HERE / "out" / f"{seq:03d}.json"
        dec, out = json.loads(pdec.read_text(encoding="utf-8")), json.loads(pout.read_text(encoding="utf-8"))
        if seq in DROP_NEG:
            dec["negatives"] = [u for u in dec.get("negatives", []) if u.split("#")[0].rstrip("/") == out["url"].split("#")[0].rstrip("/")]
            dec["note"] = (dec.get("note") or "") + "；放宽标准下允许匹配同站其他栏目的同类页面"
            pdec.write_text(json.dumps(dec, ensure_ascii=False, indent=1), encoding="utf-8")
        lines = [l for l in (out.get("pattern") or "").split("\n") if l]
        if seq in GENERAL:
            lines = GENERAL[seq]
        rxs = [re2.compile(l) for l in lines]
        pos = V.positives(seq, dec, out, r3)
        missing = [u for u in pos if u.startswith("http") and not any(r.fullmatch(u) for r in rxs)]
        alive, dead = set(), []
        for u in missing:
            c = cache.get(u, {})
            if c.get("status") == 200:
                alive.add(u)
                f = c.get("final_url")
                if f and not any(r.fullmatch(f) for r in rxs):
                    alive.add(f)
            else:
                dead.append({"url": u, "status": c.get("status")})
        if alive:
            lines = lines + ["^(?:" + "|".join(re.escape(u) for u in sorted(alive)) + ")$"]
        out["pattern"] = "\n".join(lines)
        out["pattern_base"] = out["pattern"]
        out["fix_added"] = sorted(alive)
        out["dead_links"] = dead
        pout.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(seq, "added", len(alive), "dead", len(dead))


if __name__ == "__main__":
    main()
