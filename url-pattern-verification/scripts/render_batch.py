#!/usr/bin/env python3
"""Run render_probe.js for many entries: serial per host, a few hosts in parallel.

Each entry gets <out_dir>/<entry_id>.json. Common consent overlays are hidden with CSS
(nothing is clicked on them); the probe clicks only generic "load more"-type buttons.
Challenge/CAPTCHA pages are recorded as they are; nothing tries to get past them.

Usage: python3 -I render_batch.py <targets.json> <out_dir> [--parallel N] [--rounds N] [--timeout S]
targets.json: [{"entry_id": ..., "url": ...}, ...]
"""
import argparse
import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

HIDE = ("#onetrust-consent-sdk, #CybotCookiebotDialog, #usercentrics-root, .cky-consent-container, "
        "#truste-consent-track, #didomi-host, .cc-window, #cookie-law-info-bar, #hs-eu-cookie-confirmation, "
        "#onetrust-banner-sdk, .osano-cm-window, #qc-cmp2-container")
PROBE = Path(__file__).resolve().parent / "render_probe.js"


def run_host(items, out, rounds, timeout):
    res = []
    for t in items:
        dest = out / f"{t['entry_id']}.json"
        if dest.exists():
            continue
        try:
            p = subprocess.run(["node", str(PROBE), t["url"], str(dest), "--rounds", str(rounds), "--hide", HIDE],
                               capture_output=True, text=True, timeout=timeout)
            res.append({"entry_id": t["entry_id"], "rc": p.returncode, "out": p.stdout.strip()[-300:],
                        "err": p.stderr.strip()[-300:]})
        except subprocess.TimeoutExpired:
            res.append({"entry_id": t["entry_id"], "rc": None, "err": f"timeout {timeout}s"})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets")
    ap.add_argument("out")
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--rounds", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=420)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    by_host = defaultdict(list)
    for t in json.loads(Path(a.targets).read_text(encoding="utf-8")):
        by_host[urlsplit(t["url"]).netloc].append(t)
    with ThreadPoolExecutor(max_workers=a.parallel) as ex:
        logs = [r for rs in ex.map(lambda v: run_host(v, out, a.rounds, a.timeout), by_host.values()) for r in rs]
    with open(out / "_batch-log.jsonl", "a", encoding="utf-8") as f:
        for r in logs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({"targets": sum(len(v) for v in by_host.values()), "ran": len(logs),
                      "failed": sum(1 for r in logs if r["rc"] != 0)}))


if __name__ == "__main__":
    main()
