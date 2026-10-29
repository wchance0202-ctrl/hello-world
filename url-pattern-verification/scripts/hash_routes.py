#!/usr/bin/env python3
"""Hash-route entries (#/... or #!/...): rules from click-probe landings, validated in a browser.

The part after "#" is never sent to the server, so plain HTTP cannot tell these pages apart;
samples come from click_probe.js landings and identity is checked by opening each URL in a
browser (hash_verify.js) and finding the clicked card's title in the rendered text.

Stages:
  freeze <entries.json> <click_dir> <out_dir>
      Per entry: landings that stay on the entry's host and route family (same route depth and
      query keys as the majority) are members. A seeded split decided BEFORE induction gives the
      holdout (1/4, at least 1, at most 6); the template (literal / variable per route segment,
      query values literal when constant) is induced from the rest only. Negatives are real
      landings of the other hash entries, the entry's own list route, and landings outside the
      family. Writes hash-frozen.json and hash-verify-targets.json.
  tests <out_dir>
      Builds validate_patterns.mjs-format tests from hash-frozen.json + hash-verify.jsonl
      (identity normal = the card title was found when the URL was opened on its own).
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_r3 import char_class, raw_qsl  # noqa: E402

SEED = 20261029


def split_hash(url):
    """https://h/p#!/a/b?x=1 -> (base, marker, [a, b], [(x, 1)])"""
    base, _, frag = url.partition("#")
    marker = "#!" if frag.startswith("!") else "#"
    route = frag[1:] if frag.startswith("!") else frag
    path, _, q = route.partition("?")
    return base, marker, [s for s in path.split("/") if s], raw_qsl(q)


def sig(url):
    base, marker, segs, q = split_hash(url)
    return (base, marker, len(segs), tuple(k for k, _ in q))


def build(urls):
    base, marker, _, q0 = split_hash(urls[0])
    cols = list(zip(*[split_hash(u)[2] for u in urls]))
    parts = []
    for vals in cols:
        v = set(vals)
        parts.append(re.escape(next(iter(v))) if len(v) == 1 else char_class(v))
    pat = "^" + re.escape(base) + re.escape(marker) + "/" + "/".join(parts)
    if q0:
        pieces = []
        for i, (k, _) in enumerate(q0):
            vals = {split_hash(u)[3][i][1] for u in urls}
            pieces.append(re.escape(k) + "=" + (re.escape(next(iter(vals))) if len(vals) == 1 else char_class(vals)))
        pat += r"\?" + "&".join(pieces)
    return pat + "$"


def freeze(entries_path, click_dir, out):
    out = Path(out)
    ents = {e["entry_id"]: e for e in json.loads(Path(entries_path).read_text(encoding="utf-8"))
            if e["kind"] == "path_entry" and (e.get("fragment") or "").startswith(("/", "!/"))}
    landings = {}
    for eid in ents:
        p = Path(click_dir) / f"{eid}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            landings[eid] = [c for c in d["clicks"] if c.get("landed") and c.get("via") != "none"]
    rules, verify = [], []
    for eid, e in ents.items():
        L = landings.get(eid, [])
        host = urlsplit(e["raw"]).netloc
        same = [c for c in L if urlsplit(c["landed"]).netloc == host and "#" in c["landed"]]
        if not same:
            rules.append({"entry_id": eid, "status": "no_landings", "landings": L})
            continue
        fam_sig = Counter(sig(c["landed"]) for c in same).most_common(1)[0][0]
        members = [c for c in same if sig(c["landed"]) == fam_sig]
        outside = [c for c in L if c not in members]
        urls = sorted({c["landed"] for c in members})
        if len(urls) < 4:
            rules.append({"entry_id": eid, "status": "too_few", "members": urls, "outside_family": outside})
            continue
        k = min(6, max(1, len(urls) // 4))
        hold = sorted(random.Random(f"{SEED}-{eid}").sample(urls, k))
        inf = [u for u in urls if u not in hold]
        pattern = build(inf)
        negs = [e["raw"]] + sorted({c["landed"] for x, LL in landings.items() if x != eid for c in LL
                                    if c.get("landed") and c["landed"] not in urls})[:6]
        negs += [c["landed"] for c in outside if c["landed"] not in negs]
        title = {c["landed"]: c.get("title_text") or c.get("title") for c in members}
        texts = {c["landed"]: c["text"] for c in members}
        rules.append({"id": f"R3H-{eid}-F1", "entry_id": eid, "entry_ids": [eid], "status": "frozen",
                      "pattern": pattern, "inference": inf, "holdout_pos": hold, "holdout_neg": negs,
                      "outside_family": outside, "card_texts": texts,
                      "target": f"{e['raw']} 的 Hash 路由详情（点击卡片落地）",
                      "family": "Hash 路由（浏览器点击取样）"})
        for u in urls:
            verify.append({"entry_id": eid, "url": u, "expect_text": texts[u]})
    body = json.dumps(rules, ensure_ascii=False, sort_keys=True)
    (out / "hash-frozen.json").write_text(json.dumps(
        {"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": SEED,
         "sha256": hashlib.sha256(body.encode()).hexdigest(), "rules": rules}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (out / "hash-verify-targets.json").write_text(json.dumps(verify, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps({"entries": len(ents), "rules": sum(1 for r in rules if r["status"] == "frozen"),
                      "verify": len(verify), "other": [(r["entry_id"], r["status"]) for r in rules if r["status"] != "frozen"]},
                     ensure_ascii=False))


def tests(out):
    out = Path(out)
    fr = json.loads((out / "hash-frozen.json").read_text(encoding="utf-8"))
    ver = {}
    p = out / "hash-verify.jsonl"
    if p.exists():
        for l in p.read_text(encoding="utf-8").split("\n"):
            if l.strip():
                r = json.loads(l)
                ver[r["url"]] = r
    rules, T, excluded = [], [], []
    for r in fr["rules"]:
        if r["status"] != "frozen":
            continue
        rules.append({"id": r["id"], "pattern": r["pattern"]})
        for split, key, exp in (("inference", "inference", True), ("holdout", "holdout_pos", True),
                                ("holdout", "holdout_neg", False)):
            for u in r[key]:
                t = {"rule_id": r["id"], "url": u, "expected": exp, "split": split, "source_id": u}
                if exp:
                    v = ver.get(u, {})
                    if v.get("found_text"):
                        t["identity"] = "normal"
                    else:
                        t["expected"] = None
                        t["note"] = "直接打开未找到卡片标题，不作为正例"
                        excluded.append(t)
                        continue
                T.append(t)
    json.dump({"target_engine": "re2", "engine": "re2", "engine_module": "re2", "rules": rules, "tests": T,
               "excluded_records": excluded}, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    stage, *args = sys.argv[1:]
    {"freeze": freeze, "tests": tests}[stage](*args)
