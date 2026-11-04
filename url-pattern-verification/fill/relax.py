#!/usr/bin/env python3
"""Relaxed pass (user decision 2026-11-04): a row only needs a correct, usable regex.

- 快照 rows: same-site members are generalised per URL structure (one pattern per structure group,
  variable segments as character classes from the members); off-site members (other registrable
  domains, e.g. WeChat articles) stay as an exact list. Every member must still match; the entry
  page and the row's recorded negatives must not.
- 超范围 / 候选 rows: regex kept as is.
All of them get status 已放宽. The strict record is kept in fill/out_strict/<seq>.json.
Usage: python3 -I fill/relax.py
"""
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import re2

HERE = Path(__file__).resolve().parent
# rows whose generalised rule also matches the entry page itself (a page of the same column): accepted
ALLOW_ENTRY = {126, 127, 132, 133}
# hash-route members the path-based induction cannot express
MANUAL = {103: [r"^https://a\.huiju\.cool/service/extfile/page/[0-9a-f]+\#/file$"]}
sys.path.insert(0, str(HERE))
from run_entry import induce  # noqa: E402
from structs import key  # noqa: E402


def site(host):
    parts = host.split(".")
    return ".".join(parts[-3:]) if parts[-2] in ("com", "org", "net", "gov", "edu") and len(parts) > 2 else ".".join(parts[-2:])


def generalise(members, entry):
    own = site(urlsplit(entry).netloc)
    groups, exact = defaultdict(list), []
    for u in members:
        if site(urlsplit(u).netloc) != own:
            exact.append(u)
        else:
            groups[key(u)].append(u)
    pats = []
    for k, us in groups.items():
        if len(us) >= 2:
            try:
                pats.append(induce(sorted(us)))
                continue
            except ValueError:
                pass
        exact += us
    if exact:
        pats.append("^(?:" + "|".join(re.escape(u) for u in sorted(set(exact))) + ")$")
    return pats


def main():
    strict = HERE / "out_strict"
    strict.mkdir(exist_ok=True)
    report = []
    for p in sorted((HERE / "out").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        st = d.get("status")
        if st not in ("快照", "超范围", "候选"):
            continue
        if not (strict / p.name).exists():
            shutil.copy(p, strict / p.name)
        src = json.loads((strict / p.name).read_text(encoding="utf-8"))
        dec = json.loads((HERE / "dec" / p.name).read_text(encoding="utf-8"))
        base = src.get("pattern_base") or src.get("pattern") or ""
        if st == "快照":
            pat_lines = [l for l in base.split("\n") if l]
            # members actually kept in the snapshot = every alternative of the exact-list line(s)
            ms = []
            for l in pat_lines:
                if l.startswith("^(?:"):
                    ms += [re.sub(r"\\(.)", r"\1", x) for x in l[4:-2].split("|")]
            if not ms:
                continue
            pats = MANUAL.get(d["seq"]) or generalise(ms, d["url"])
            rxs = [re2.compile(x) for x in pats]
            hit = lambda u: any(r.fullmatch(u) for r in rxs)  # noqa: E731
            # relaxed: other columns' items of the same structure may match; the entry page and
            # structurally different pages (lists, nav, other page types) still must not
            mkeys = {key(u) for u in ms}
            neg = ([] if d["seq"] in ALLOW_ENTRY else [d["url"].split("#")[0]]) + [u for u in dec.get("negatives", []) if key(u) not in mkeys and u.split("#")[0] != d["url"].split("#")[0]]
            bad_pos = [u for u in ms if not hit(u)]
            bad_neg = [u for u in neg if hit(u)]
            if bad_pos or bad_neg:
                report.append((d["seq"], "kept exact", len(bad_pos), bad_neg[:2]))
                pats = ["^(?:" + "|".join(re.escape(u) for u in sorted(set(ms))) + ")$"]
            (HERE / "lists").mkdir(exist_ok=True)
            (HERE / "lists" / p.name.replace(".json", ".txt")).write_text("\n".join(sorted(set(ms))) + "\n", encoding="utf-8")
            d["pattern"] = "\n".join(pats)
            d.pop("pattern_base", None)
            d["full_list_count"] = len(set(ms))
            gen = sum(1 for x in pats if not x.startswith("^(?:"))
            d["relax_note"] = (f"由逐条清单改为通用规则（{gen} 条），会同时匹配同站同结构的其他页面" if gen else "保留逐条清单（站外条目或无法归纳）")
            if d["seq"] in ALLOW_ENTRY:
                d["relax_note"] += "，也匹配入口页本身"
        else:
            d["relax_note"] = {"超范围": "通用规则，会同时匹配同站其他栏目的同类页面",
                               "候选": "规则按真实网址结构写成，部分样本未能打开核验"}[st]
        d["status_strict"] = st
        d["status"] = "已放宽"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        report.append((d["seq"], st, d["pattern"].count("\n") + 1))
    for r in report:
        print(r)


if __name__ == "__main__":
    main()
