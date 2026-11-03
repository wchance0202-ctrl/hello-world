#!/usr/bin/env python3
"""Static pagination enumerator: fetch tpl.format(n) for n=start.. until a page adds no new item links.
Usage: python3 -I page_enum.py <out.txt> <tpl with {n}> <item_regex> [start] [max] [prefix_for_relative]"""
import re, sys, time, requests
out, tpl, rx = sys.argv[1:4]
start = int(sys.argv[4]) if len(sys.argv) > 4 else 1
mx = int(sys.argv[5]) if len(sys.argv) > 5 else 2000
base = sys.argv[6] if len(sys.argv) > 6 else ""
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
seen, log = set(), []
for n in range(start, mx + 1):
    time.sleep(1.2)
    try:
        r = s.get(tpl.format(n=n), timeout=30)
    except Exception as e:
        log.append(f"p{n}:ERR"); break
    found = {(base + m if m.startswith("/") else m) for m in re.findall(rx, r.text)}
    new = found - seen
    log.append(f"p{n}:{r.status_code}+{len(new)}")
    if r.status_code != 200 or not new:
        break
    seen |= new
open(out, "w").write("\n".join(sorted(seen)) + "\n")
print(out.rsplit("/", 1)[-1], len(seen), " ".join(log[-3:]))
