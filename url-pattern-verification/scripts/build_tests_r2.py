#!/usr/bin/env python3
"""Assemble validate_patterns.mjs-format test files for round 2.

  generalized: rules + frozen samples (samples-frozen.json, optional v2 overlay) + identity checks
               (identity-checks.jsonl). A positive is identity=normal only when its
               own GET ended 200 with an HTML title (after redirects).
  snapshot:    Forrester B2B Research exact-set chunks; every member is expected to
               match exactly its own chunk, every negative no chunk (finite-set equality,
               not a generalization test).

Usage:
  python3 -I build_tests_r2.py generalized <samples-frozen.json> <identity-checks.jsonl> [--overlay samples-frozen-v2.json] [--rules-override rules.json] > tests.json
  python3 -I build_tests_r2.py snapshot <exact-candidates.json> <members.json> <negatives.json> > tests.json
"""
import json
import re
import sys
from pathlib import Path

RE2_MODULE = "re2"


def identity_map(path):
    """url -> 'normal' | 'redirected_away' | 'unverified'.

    normal: final status 200 with an HTML title and the final URL is the requested one
    (a trailing-slash-only redirect is allowed). Landing on another path is not normal.
    """
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            same = (r.get("final_url") or "").rstrip("/") == r["url"].rstrip("/")
            if r.get("status") == 200 and r.get("title") and same:
                out[r["url"]] = "normal"
            else:
                out[r["url"]] = "redirected_away" if r.get("redirected") else "unverified"
    return out


def generalized(samples, checks, override=None, overlay=None):
    spec = json.loads(Path(samples).read_text(encoding="utf-8"))
    if overlay:  # a later freeze replaces whole rules by id (pattern, splits, history)
        newer = {r["id"]: r for r in json.loads(Path(overlay).read_text(encoding="utf-8"))["rules"]}
        spec["rules"] = [newer.get(r["id"], r) for r in spec["rules"]]
    idm = identity_map(checks)
    patterns = {r["id"]: r["pattern"] for r in spec["rules"]}
    if override:
        patterns.update(json.loads(Path(override).read_text(encoding="utf-8")))
    rules, tests, excluded = [], [], []
    for r in spec["rules"]:
        rules.append({"id": r["id"], "pattern": patterns[r["id"]]})
        for split, key, exp in (("inference", "inference", True), ("holdout", "holdout_pos", True),
                                ("holdout", "holdout_neg", False), ("regression", "regression_pos", True),
                                ("regression", "regression_neg", False)):
            for u in r.get(key, []):
                t = {"rule_id": r["id"], "url": u, "expected": exp, "split": split,
                     "source_id": u.rstrip("/")}
                state = idm.get(u, "unverified")
                if exp and state == "normal":
                    t["identity"] = "normal"
                elif exp and state == "redirected_away":
                    # a listed link that lands on a non-detail page: kept on record, not a positive
                    t["expected"] = None
                    t["note"] = "列表链接跳转到非详情页，身份不正常，不作为正例"
                    excluded.append(t)
                    continue
                tests.append(t)
    return {"target_engine": "re2", "engine": "re2", "engine_module": RE2_MODULE,
            "rules": rules, "tests": tests, "excluded_records": excluded}


def unescape(p):
    return re.sub(r"\\(.)", r"\1", p)


def snapshot(cands, members, negatives):
    pats = json.loads(Path(cands).read_text(encoding="utf-8"))["patterns"]
    mem = [m["link"] for m in json.loads(Path(members).read_text(encoding="utf-8"))["members"]]
    neg = json.loads(Path(negatives).read_text(encoding="utf-8"))["members"]
    rules = [{"id": f"R2-FORR-B2B-SNAP-{i + 1:02d}", "pattern": p} for i, p in enumerate(pats)]
    # chunk membership from the generator's literal alternatives (^(?:a|b|...)$), not from an engine run
    lits = [{unescape(x) for x in p[len("^(?:"):-len(")$")].split("|")} for p in pats]
    memset = set(mem)
    assert set().union(*lits) == memset, "chunks do not reproduce the member set"
    tests = []
    for u in mem + neg:
        for i, r in enumerate(rules):
            exp = u in memset and u in lits[i]
            # membership comes from the WP REST listing; only a 6-URL sample was opened,
            # so no pair is marked identity=normal here
            tests.append({"rule_id": r["id"], "url": u, "expected": exp, "split": "regression",
                          "source_id": u})
    return {"target_engine": "re2", "engine": "re2", "engine_module": RE2_MODULE,
            "rules": rules, "tests": tests}


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "generalized":
        ov = args[args.index("--rules-override") + 1] if "--rules-override" in args else None
        ovl = args[args.index("--overlay") + 1] if "--overlay" in args else None
        out = generalized(args[0], args[1], ov, ovl)
    else:
        out = snapshot(*args[:3])
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
