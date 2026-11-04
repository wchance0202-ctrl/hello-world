#!/usr/bin/env python3
"""Refresh the item lists of snapshot / over-scope rows and re-run them.

Sources per row (fill/refresh-config.json):
  {"seq": N, "type": "feed",  "url": "...feed/", "item": "<regex>"}            column RSS feed (newest items)
  {"seq": N, "type": "pages", "tpl": "...{n}...", "item": "<regex>", "base": ""}  static pagination to the end
New items are merged into the row's decision (members / full_list), the row is re-run with
run_entry.py (snapshots re-open every item; regex rows re-test), then redirects.py and the table
builder run. Rows whose list needs a browser (jazzyear) use jy_enum.js and are listed as manual.

Usage: python3 -I fill/refresh.py [seq ...]     (no seq = every row in the config)
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def collect(src, sess):
    found = set()
    if src["type"] == "feed":
        r = sess.get(src["url"], timeout=30)
        # only each entry's own link element, not links quoted inside descriptions
        links = re.findall(r"<link>\s*([^<\s]+)\s*</link>|<link[^>]+href=\"([^\"]+)\"", r.text)
        cand = {(a or b).replace("&amp;", "&") for a, b in links}
        found = {u for u in cand if re.fullmatch(src["item"], u)}
    elif src["type"] == "pages":
        for n in range(src.get("start", 1), src.get("max", 2000) + 1):
            time.sleep(1.2)
            r = sess.get(src["tpl"].format(n=n), timeout=30)
            new = {src.get("base", "") + m if m.startswith("/") else m for m in re.findall(src["item"], r.text)} - found
            if r.status_code != 200 or not new:
                break
            found |= new
    return found


def main(seqs):
    cfg = json.loads((HERE / "refresh-config.json").read_text(encoding="utf-8"))
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    report = []
    for src in cfg:
        if seqs and src["seq"] not in seqs:
            continue
        p = HERE / "dec" / f"{src['seq']:03d}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        try:
            found = collect(src, sess)
        except Exception as e:  # noqa: BLE001
            report.append({"seq": src["seq"], "error": str(e)[:100]})
            continue
        key = "full_list" if d.get("full_list") is not None else "members"
        before = set(d.get(key) or [])
        new = sorted(found - before)
        if new:
            d[key] = sorted(before | set(new))
            if key == "full_list" and "members" in d:
                d["members"] = sorted(set(d["members"]) | set(new))
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            subprocess.run([sys.executable, "-I", str(HERE / "run_entry.py"), str(p)], check=False)
        report.append({"seq": src["seq"], "source": src["type"], "found": len(found), "new": len(new)})
    subprocess.run([sys.executable, "-I", str(HERE / "redirects.py")], check=False)
    subprocess.run([sys.executable, "-I", str(HERE / "build_table.py")], check=False)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]])
