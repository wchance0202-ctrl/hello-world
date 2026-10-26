#!/usr/bin/env python3
"""Run a validate_patterns.mjs-format test file on google-re2 (Python).

Cross-check for the node-re2 harness: same input contract, per-pair results and
per-rule/per-split confusion counts. Mechanical only: it proves nothing about
page identity, scope, label truth or holdout isolation.

Usage: python3 -I run_re2_py.py <tests.json> > re2-py-execution.json
"""
import importlib.metadata
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

import re2


def ratio(num, den):
    return None if den == 0 else num / den


def main(path):
    spec = json.load(open(path, encoding="utf-8"))
    compiled, rules_out = {}, []
    for r in spec["rules"]:
        p = r["pattern"]
        ok = p.startswith("^") and p.endswith("$")
        try:
            compiled[r["id"]] = re2.compile(p)
            rules_out.append({"id": r["id"], "compiled": True, "anchored": ok})
        except Exception as exc:  # re2.error has no stable public class name
            rules_out.append({"id": r["id"], "compiled": False, "error": str(exc)})
    counts = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "unlabelled": 0})
    results = []
    for t in spec["tests"]:
        rx = compiled.get(t["rule_id"])
        actual = None if rx is None else rx.fullmatch(t["url"]) is not None
        exp = t.get("expected")
        key = (t["rule_id"], t.get("split"))
        if exp is None or actual is None:
            counts[key]["unlabelled"] += 1
        else:
            counts[key][("T" if exp == actual else "F") + ("P" if actual else "N")] += 1
        results.append({**t, "actual": actual, "pass": None if exp is None else exp == actual})
    metrics = []
    for (rid, split), c in sorted(counts.items()):
        n = c["TP"] + c["FP"] + c["FN"] + c["TN"]
        metrics.append({"rule_id": rid, "split": split, **c,
                        "accuracy": ratio(c["TP"] + c["TN"], n),
                        "precision": ratio(c["TP"], c["TP"] + c["FP"]),
                        "recall": ratio(c["TP"], c["TP"] + c["FN"])})
    json.dump({"observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "engine": {"name": "google-re2",
                          "version": importlib.metadata.version("google-re2"),
                          "runtime": sys.version.split()[0]},
               "target_engine": spec.get("target_engine"),
               "rules": rules_out, "metrics": metrics, "results": results,
               "note": "Mechanical checks only."},
              sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
