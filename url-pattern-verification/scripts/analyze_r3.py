#!/usr/bin/env python3
"""Round 3: automatic URL-family induction, sample freezing and coverage checks.

Stages (all offline except where identity checks are run separately with redirect_check.py):

  families  <entries.json> <r3_dir>
      For every path entry: take the links found on the entry's own pages (entry page and
      its pagination pages; header/nav/footer/aside excluded; same host), keep those under the
      entry's path prefix, and group them by structural signature (segment count after the
      prefix, trailing slash, query keys, extension). A group with >=3 distinct URLs is a
      family. Variable character classes are derived ONLY from the induction set (links on
      the entry page itself; later pagination pages are added only if the entry page has <3).
      Writes families.json and identity-A-targets.json (induction samples to open).

  freeze    <r3_dir>
      Uses identity-A results to fix the trailing-slash form (only when an induction sample
      was redirected to the other form) and to drop families whose induction samples do not
      land normally. Then draws holdout positives from an independent source: sitemap URLs
      with the same structure (prefix, segment count, literal positions) that were NOT seen on
      the listing pages; if the host has no usable sitemap, cards from later pagination pages
      that were not used for induction; else same-structure links on other entries' pages or on
      the family's own detail pages (detail-links.jsonl). Negatives are real same-host URLs: the entry page and
      pagination pages, sitemap/edge URLs outside the prefix with the same depth, and URLs
      under the prefix with another signature. Labels are frozen with a sha256 before any
      holdout page is opened. Writes samples-frozen.json and identity-B-targets.json.

  coverage  <r3_dir> <google-re2-results.json>
      Matches every frozen rule against (a) all listing members of its signature and
      (b) all sitemap URLs with the same structure; any miss is a known miss.
      Writes coverage.json.

Scope note: "under the entry prefix" is used as the column boundary. Links outside the
prefix (shared paths such as /articles/{id}) are never generalized; they are retained links.
"""
import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

SEED = 20261028
SKIP_REGIONS = {"header", "nav", "footer", "aside"}
FILE_EXT = re.compile(r"\.(pdf|xlsx?|csv|docx?|pptx?|zip)$", re.I)
ASSET_EXT = re.compile(r"\.(jpe?g|png|gif|svg|webp|css|js|ico|mp4|mp3)$", re.I)
MAX_HOLD, MAX_INF_CHECK = 6, 5


def read_text(p):
    """Plain file, or its committed .gz copy."""
    p = Path(p)
    if p.exists():
        return p.read_text(encoding="utf-8")
    gz = p.with_name(p.name + ".gz")
    if gz.exists():
        import gzip
        return gzip.decompress(gz.read_bytes()).decode("utf-8")
    return None


def parsable(u):
    """False for hrefs urllib cannot parse (e.g. "http://[..."); such links are never used."""
    try:
        urlsplit(u)
        return True
    except ValueError:
        return False


def jl(p):
    txt = read_text(p)
    if txt is None:
        return []
    lines = [l for l in txt.split("\n") if l.strip()]
    out = []
    for i, l in enumerate(lines):
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            if i != len(lines) - 1:  # only a line still being written may be cut off
                raise
    return out


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ URL structure

def prefix_of(path):
    """Column prefix for an entry path."""
    if path.endswith("/"):
        return path
    segs = path.split("/")
    last = segs[-1]
    if "." in last:  # file-like entry: /x/y.html -> /x/ ; SharePoint /x/Pages/default.aspx -> /x/
        parent = segs[:-1]
        if parent and parent[-1].lower() == "pages":
            parent = parent[:-1]
        return "/".join(parent) + "/"
    return path + "/"


def choose_prefix(path, link_paths):
    """For a file-like entry (/x/insights.html) prefer /x/insights/ when the page links to
    at least 3 URLs under it; otherwise the parent directory."""
    base = prefix_of(path)
    last = path.rsplit("/", 1)[-1]
    if "." in last and not path.lower().endswith("/pages/default.aspx"):
        stem = path.rsplit(".", 1)[0] + "/"
        if sum(1 for lp in link_paths if lp.startswith(stem) and lp != stem) >= 3:
            return stem
    return base


def segs_after(path, prefix):
    rest = path[len(prefix):]
    slash = rest.endswith("/")
    parts = [s for s in rest.split("/") if s != ""]
    return parts, slash


def signature(url, prefix):
    sp = urlsplit(url)
    parts, slash = segs_after(sp.path, prefix)
    ext = ""
    if parts and "." in parts[-1]:
        ext = parts[-1].rsplit(".", 1)[-1].lower()
    qk = tuple(sorted({k for k, _ in parse_qsl(sp.query, keep_blank_values=True)}))
    return (len(parts), slash, qk, ext)


def char_class(values):
    vals = list(values)
    if all(re.fullmatch(r"[0-9]+", v) for v in vals):
        return "[0-9]+"
    cats = set()
    extra = set()
    for v in vals:
        for ch in v:
            if "a" <= ch <= "z":
                cats.add("a-z")
            elif "A" <= ch <= "Z":
                cats.add("A-Z")
            elif ch.isdigit():
                cats.add("0-9")
            elif ch in "-_.~%":
                extra.add(ch)
            else:
                extra.add(ch)
    order = [c for c in ("a-z", "A-Z", "0-9") if c in cats]
    ex = "".join(re.escape(c) if c not in "-" else "" for c in sorted(extra))
    dash = "-" if "-" in extra else ""
    return "[" + "".join(order) + ex + dash + "]+"


def build_pattern(scheme_host, prefix, template, slash_mode, qk, sample_queries):
    """template: list of ('lit', value) | ('var', class)."""
    parts = []
    for t in template:
        kind, v = t[0], t[1]
        parts.append(re.escape(v) if kind == "lit" else v + (re.escape("." + t[2]) if kind == "varext" else ""))
    path = re.escape(prefix) + "/".join(parts)
    if slash_mode == "slash":
        path += "/"
    elif slash_mode == "optional":
        path += "/?"
    q = ""
    if qk:
        # keep the observed key order of the first induction sample; values by class
        first = sample_queries[0]
        pieces = []
        for k, _ in raw_qsl(first):
            vals = [dict(raw_qsl(sq)).get(k, "") for sq in sample_queries]
            vc = char_class([x for x in vals if x]) if any(vals) else ""
            vcls = (vc[:-1] + "*") if vc else ""
            pieces.append(re.escape(k) + "=" + (re.escape(vals[0]) if len(set(vals)) == 1 else vcls))
        q = r"\?" + "&".join(pieces)
    return "^" + re.escape(scheme_host) + path + q + "$"


def raw_qsl(query):
    """key/value pairs exactly as written in the URL (no percent-decoding), order kept."""
    out = []
    for piece in query.split("&"):
        if piece:
            k, _, v = piece.partition("=")
            out.append((k, v))
    return out


def template_of(urls, prefix):
    cols = defaultdict(set)
    for u in urls:
        parts, _ = segs_after(urlsplit(u).path, prefix)
        for i, p in enumerate(parts):
            cols[i].add(p)
    tpl = []
    for i in range(len(cols)):
        vals = cols[i]
        last = i == len(cols) - 1
        exts = {v.rsplit(".", 1)[1] for v in vals if "." in v} if last else set()
        if len(vals) == 1:
            tpl.append(("lit", next(iter(vals))))
        elif last and len(exts) == 1 and all("." in v for v in vals):
            ext = exts.pop()  # keep the file extension literal: stem class + ".ext"
            tpl.append(("varext", char_class(v.rsplit(".", 1)[0] for v in vals), ext))
        else:
            tpl.append(("var", char_class(vals)))
    return tpl


def same_structure(url, prefix, sig, template, scheme_host, any_slash=True):
    """Structure-only test used to pick holdout/coverage URLs (literal positions + depth),
    independent of the variable character classes. The other trailing-slash form counts as the
    same family only when any_slash is set: i.e. the rule's own induction samples showed the two
    forms redirect to each other (slash_mode "optional"); otherwise it is a different page type."""
    if not url.startswith(scheme_host + prefix):
        return False
    us = signature(url, prefix)
    if (us[0], us[2], us[3]) != (sig[0], sig[2], sig[3]) or (not any_slash and us[1] != sig[1]):
        return False
    parts, _ = segs_after(urlsplit(url).path, prefix)
    return all(t[0] != "lit" or parts[i] == t[1] for i, t in enumerate(template))


# ------------------------------------------------------------------ stage: families

def entry_pages(visits, eid):
    return [v for v in visits if v["entry_id"] == eid and v.get("status") == 200 and v.get("identity")]


def families(entries_path, r3):
    r3 = Path(r3)
    ents = [e for e in json.loads(Path(entries_path).read_text(encoding="utf-8")) if e["kind"] == "path_entry"]
    visits = jl(r3 / "probe/visits.jsonl")
    edges_by_parent = defaultdict(list)
    for e in jl(r3 / "probe/edges.jsonl"):
        edges_by_parent[(e["entry_id"], e["parent_url"])].append(e)
    render = {}
    for f in (r3 / "render").glob("*.json") if (r3 / "render").exists() else []:
        d = json.loads(f.read_text(encoding="utf-8"))
        render[f.stem] = d
    out, idA, sm_cache = [], [], {}
    for e in ents:
        eid = e["entry_id"]
        pages = entry_pages(visits, eid)
        rec = {"entry_id": eid, "raw": e["raw"], "host": e["host"], "pages": len(pages),
               "families": [], "outside_prefix": [], "files": [], "under_prefix_singletons": []}
        if not pages and eid not in render:
            rec["status"] = "no_page"
            out.append(rec)
            continue
        entry_final = pages[0]["final_url"] if pages else render[eid]["final_url"]
        sp = urlsplit(entry_final)
        scheme_host = f"{sp.scheme}://{sp.netloc}"
        listing = {p["final_url"].split("#")[0] for p in pages} | {p["request_url"] for p in pages}
        first_links, all_links, nav_links = [], [], []  # (url, page_rank)
        for rank, p in enumerate(pages):
            for ed in edges_by_parent.get((eid, p["final_url"]), []):
                if ed["region"] in SKIP_REGIONS:
                    if ed["region"] != "footer":
                        u = ed["resolved_url"].split("#")[0]
                        if u.startswith(("http://", "https://")) and parsable(u):
                            nav_links.append((u, rank, "nav"))
                    continue
                u = ed["resolved_url"].split("#")[0]
                if not u.startswith(("http://", "https://")) or not parsable(u):
                    continue
                all_links.append((u, rank, ed["relation_hint"]))
        if eid in render:  # rendered DOM after load-more: counts as the entry page itself
            for a in render[eid]["anchors"]:
                if a["region"].lower() in SKIP_REGIONS:
                    if a["region"].lower() != "footer" and a["href"].startswith(("http://", "https://")) \
                            and parsable(a["href"]):
                        nav_links.append((a["href"].split("#")[0], 0, "nav"))
                    continue
                u = a["href"].split("#")[0]
                if u.startswith(("http://", "https://")) and parsable(u):
                    all_links.append((u, 0, "rendered"))
        def under(links, pfx):
            return [x for x in links if urlsplit(x[0]).netloc == sp.netloc and urlsplit(x[0]).path.startswith(pfx)
                    and urlsplit(x[0]).path != sp.path]
        # some sites put the column's own item list inside <nav>/<header>: when the content
        # regions hold nothing under the entry prefix, use those links (under the prefix only)
        if len(under(all_links, prefix_of(sp.path))) < 3 and len(under(nav_links, prefix_of(sp.path))) >= 3:
            all_links += under(nav_links, prefix_of(sp.path))
            rec["nav_fallback"] = True
        seen_rank = {}
        for u, rank, rel in all_links:
            seen_rank[u] = min(rank, seen_rank.get(u, 99))
        prefix = choose_prefix(sp.path, [urlsplit(u).path for u in seen_rank
                                         if urlsplit(u).netloc == sp.netloc])
        rec.update({"final_url": entry_final, "scheme_host": scheme_host, "prefix": prefix,
                    "challenge": bool(pages and pages[0]["identity"].get("challenge_hint")),
                    "thin": bool(pages and pages[0]["identity"].get("thin_static_html"))})
        sm = sitemap_urls(r3, sm_cache, scheme_host)
        groups = defaultdict(set)
        for u, rank in seen_rank.items():
            usp = urlsplit(u)
            if ASSET_EXT.search(usp.path):
                continue
            if FILE_EXT.search(usp.path):
                rec["files"].append(u)
                continue
            if f"{usp.scheme}://{usp.netloc}" != scheme_host or not usp.path.startswith(prefix):
                if usp.netloc.split(":")[0].endswith(e["host"].split(".", 1)[-1]) or usp.netloc == sp.netloc:
                    rec["outside_prefix"].append(u)
                continue
            if u in listing or usp.path == sp.path:
                continue
            groups[signature(u, prefix)].add(u)
        fam_no = 0
        for sig, urls in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if sig[0] == 0 or len(urls) < 3:
                rec["under_prefix_singletons"] += sorted(urls)
                continue
            # With an independent holdout source (sitemap URLs of the same structure that the
            # listing does not show) the whole listing is the induction set; otherwise induce
            # from the entry page only and hold out the later pagination pages.
            tpl_all = template_of(urls, prefix)
            norm = {x.rstrip("/") for x in urls}
            has_pool = any(same_structure(u, prefix, sig, tpl_all, scheme_host) and u.rstrip("/") not in norm
                           for u in sm)
            if has_pool:
                inf, tpl, mode = sorted(urls), tpl_all, "sitemap"
            else:
                inf = sorted(u for u in urls if seen_rank[u] == 0)
                r = 1
                while len(inf) < 3:
                    inf = sorted(u for u in urls if seen_rank[u] <= r)
                    r += 1
                tpl, mode = template_of(inf, prefix), "later_pagination_pages"
            fam_no += 1
            fid = f"R3-{eid}-F{fam_no}"
            q = sorted(urlsplit(u).query for u in inf)
            fam = {"id": fid, "signature": list(sig), "template": tpl, "members": sorted(urls),
                   "inference": inf, "later_members": sorted(set(urls) - set(inf)),
                   "slash_mode": "slash" if sig[1] else "none", "queries": q, "holdout_mode": mode}
            rec["families"].append(fam)
            rnd = random.Random(f"{SEED}-{fid}")
            for u in rnd.sample(inf, min(MAX_INF_CHECK, len(inf))):
                idA.append({"entry_id": eid, "url": u, "parent_url": entry_final, "relation": f"{fid}:inference"})
        rec["outside_prefix"] = sorted(set(rec["outside_prefix"]))
        rec["files"] = sorted(set(rec["files"]))
        rec["status"] = "ok"
        out.append(rec)
    (r3 / "families.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (r3 / "identity-A-targets.json").write_text(json.dumps(idA, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps({"entries": len(out), "families": sum(len(r["families"]) for r in out),
                      "identity_A": len(idA)}))


# ------------------------------------------------------------------ stage: freeze

def load_ident(r3, names):
    m = {}
    for n in names:
        for r in jl(Path(r3) / n):
            m[r["url"]] = r
    return m


def sitemap_urls(r3, host_cache, scheme_host):
    host = urlsplit(scheme_host).netloc
    if host not in host_cache:
        txt = read_text(Path(r3) / "sitemaps" / f"{host}.txt")
        urls = []
        for l in (txt or "").splitlines():
            l = l.strip()
            if "#" in l and not re.search(r"#[!/]", l):
                l = l.split("#", 1)[0]  # an ordinary anchor is not a separate page
            if l and parsable(l):
                urls.append(l)
        host_cache[host] = list(dict.fromkeys(urls))
    return host_cache[host]


def freeze(r3):
    r3 = Path(r3)
    fams = json.loads((r3 / "families.json").read_text(encoding="utf-8"))
    idA = load_ident(r3, ["identity-A.jsonl"])
    cache, rules, idB, dropped = {}, [], [], []
    # links seen anywhere in this round's crawl, per host: fallback holdout source
    # (pages other than the family's own listing pages)
    elsewhere = defaultdict(set)
    for ed in jl(r3 / "probe/edges.jsonl") + jl(r3 / "detail-links.jsonl"):
        u = ed["resolved_url"].split("#")[0]
        if u.startswith(("http://", "https://")) and parsable(u):
            elsewhere[urlsplit(u).netloc].add((u, ed["entry_id"]))
    for rec in fams:
        if rec.get("status") != "ok":
            continue
        sh, prefix = rec["scheme_host"], rec["prefix"]
        sm = sitemap_urls(r3, cache, sh)
        listing_all = set()
        for f in rec["families"]:
            listing_all |= set(f["members"])
        for f in rec["families"]:
            checked = [idA[u] for u in f["inference"] if u in idA]
            normal = [c for c in checked if c.get("status") == 200 and c.get("title")
                      and (c.get("final_url") or "").rstrip("/") == c["url"].rstrip("/")]
            away = [c for c in checked if c.get("redirected") and (c.get("final_url") or "").rstrip("/") != c["url"].rstrip("/")]
            if len(normal) < min(3, len(checked)) or not checked:
                dropped.append({"id": f["id"], "entry_id": rec["entry_id"], "why": "归纳样本落地不足 3 个正常页面",
                                "checked": [(c["url"], c.get("status"), c.get("final_url")) for c in checked]})
                continue
            slash_mode = f["slash_mode"]
            if any(c["redirected"] and c["final_url"].rstrip("/") == c["url"].rstrip("/") for c in normal):
                slash_mode = "optional"  # both forms observed on the induction sample's own redirect
            sig = tuple(x if not isinstance(x, list) else tuple(x) for x in f["signature"])
            tpl = [tuple(t) for t in f["template"]]
            pattern = build_pattern(sh, prefix, tpl, slash_mode, sig[2], f["queries"])
            rnd = random.Random(f"{SEED}-{f['id']}-hold")
            if f["holdout_mode"] == "sitemap":
                norm = {x.rstrip("/") for x in listing_all}
                pool = [u for u in sm if same_structure(u, prefix, sig, tpl, sh, slash_mode == "optional")
                        and u.rstrip("/") not in norm]
                source = "sitemap"
            else:
                pool, source = list(f["later_members"]), "later_pagination_pages"
            if not pool:
                norm = {x.rstrip("/") for x in listing_all}
                pool = sorted({u for u, eid2 in elsewhere[urlsplit(sh).netloc]
                               if eid2 != rec["entry_id"] and same_structure(u, prefix, sig, tpl, sh, slash_mode == "optional")
                               and u.rstrip("/") not in norm})
                source = "other_entries_pages"
            # the entry page and its directory-index aliases are the listing itself, never a member
            alias = re.compile(r"^" + re.escape(sh + prefix) + r"(index|default)\.[a-z]+$", re.I)
            pool = [u for u in pool if u.rstrip("/") != rec["final_url"].rstrip("/") and not alias.match(u)]
            hold = sorted(rnd.sample(pool, min(MAX_HOLD, len(pool))))
            if not hold and len(f["inference"]) >= 4:
                # no outside source at all: split the listing members BEFORE inducing; the
                # held-out members are never shown to the induction
                k = min(MAX_HOLD, max(1, len(f["inference"]) // 4))
                hold = sorted(random.Random(f"{SEED}-{f['id']}-split").sample(f["inference"], k))
                rest = [u for u in f["inference"] if u not in hold]
                tpl = template_of(rest, prefix)
                pattern = build_pattern(sh, prefix, tpl, slash_mode, sig[2], sorted(urlsplit(u).query for u in rest))
                normal = [c for c in normal if c["url"] not in hold]
                source = "listing_split"
            negs = [rec["final_url"]]
            depth_total = len([s for s in urlsplit(f["inference"][0]).path.split("/") if s])
            outside = [u for u in sm + rec["outside_prefix"]
                       if u.startswith(sh) and not urlsplit(u).path.startswith(prefix)
                       and len([s for s in urlsplit(u).path.split("/") if s]) == depth_total]
            outside = sorted(set(outside))
            negs += rnd.sample(outside, min(4, len(outside)))
            if len(negs) < 4:  # too few same-depth neighbours: any other real same-site page outside the prefix
                seen_any = [u for u, _ in elsewhere[urlsplit(sh).netloc]]
                anyd = sorted({u for u in sm + rec["outside_prefix"] + seen_any if u.startswith(sh)
                               and not urlsplit(u).path.startswith(prefix) and u not in negs
                               and not ASSET_EXT.search(urlsplit(u).path)})
                negs += rnd.sample(anyd, min(4 - len(negs), len(anyd)))
            others = sorted({u for g in rec["families"] if g["id"] != f["id"] for u in g["members"]}
                            | set(rec["under_prefix_singletons"]))
            negs += rnd.sample(others, min(2, len(others)))
            negs = [u for u in dict.fromkeys(negs) if u.rstrip("/") not in {h.rstrip("/") for h in hold}]
            ok_inf = [c["url"] for c in normal]
            rule = {"id": f["id"], "entry_ids": [rec["entry_id"]],
                    "target": f"{rec['raw']} 入口前缀 {prefix} 下签名 {list(sig)} 的页面家族（自动归纳）",
                    "family": "栏目前缀内路径（自动归纳）", "pattern": pattern,
                    "variables": {f"seg{i}": t[1] + (f" + .{t[2]}" if t[0] == "varext" else "")
                                  for i, t in enumerate(tpl) if t[0] != "lit"},
                    "literals": {f"seg{i}": t[1] for i, t in enumerate(tpl) if t[0] == "lit"},
                    "assumptions": ("完整 URL、区分大小写；变量字符集只取自归纳集合（"
                                    + ("列表全部页面，留出取自 sitemap" if source == "sitemap" else "入口首页，留出取自后续分页")
                                    + "）；尾斜杠按归纳样本实测"),
                    "slash_mode": slash_mode, "holdout_source": source,
                    "inference": ok_inf, "holdout_pos": hold, "holdout_neg": negs,
                    "inference_redirected_away": [(c["url"], c["final_url"]) for c in away],
                    "template": [list(t) for t in tpl]}
            rules.append(rule)
            for u in hold:
                idB.append({"entry_id": rec["entry_id"], "url": u, "parent_url": None, "relation": f"{f['id']}:holdout_pos"})
    body = json.dumps(rules, ensure_ascii=False, sort_keys=True)
    (r3 / "samples-frozen.json").write_text(json.dumps(
        {"frozen_at": now(), "seed": SEED, "sha256": hashlib.sha256(body.encode()).hexdigest(),
         "rules": rules, "dropped": dropped}, ensure_ascii=False, indent=1), encoding="utf-8")
    (r3 / "identity-B-targets.json").write_text(json.dumps(idB, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps({"rules": len(rules), "dropped": len(dropped), "identity_B": len(idB),
                      "holdout_sources": dict(__import__("collections").Counter(r["holdout_source"] for r in rules))}))


# ------------------------------------------------------------------ stage: coverage

def frozen_rules(r3):
    """v1 freeze with the v2 revision (if any) overlaid by rule id."""
    rules = {r["id"]: r for r in json.loads((r3 / "samples-frozen.json").read_text(encoding="utf-8"))["rules"]}
    v2 = r3 / "samples-frozen-v2.json"
    if v2.exists():
        rules.update({r["id"]: r for r in json.loads(v2.read_text(encoding="utf-8"))["rules"]})
    return {"rules": list(rules.values())}


def coverage(r3, results_path, out_name="coverage.json"):
    import re2
    r3 = Path(r3)
    fams = {f["id"]: (rec, f) for rec in json.loads((r3 / "families.json").read_text(encoding="utf-8"))
            for f in rec.get("families", [])}
    frozen = frozen_rules(r3)
    cache, out = {}, {}
    for r in frozen["rules"]:
        rec, f = fams[r["id"]]
        rx = re2.compile(r["pattern"])
        sig = tuple(x if not isinstance(x, list) else tuple(x) for x in f["signature"])
        tpl = [tuple(t) for t in f["template"]]
        anys = r.get("slash_mode") == "optional"
        sm = [u for u in sitemap_urls(r3, cache, rec["scheme_host"])
              if same_structure(u, rec["prefix"], sig, tpl, rec["scheme_host"], anys)]
        miss_list = [u for u in f["members"] if not rx.fullmatch(u)]
        miss_sm = [u for u in sm if not rx.fullmatch(u)]
        # also: anything the rule matches on the sitemap that is outside the structural family
        extra = [u for u in sitemap_urls(r3, cache, rec["scheme_host"])
                 if rx.fullmatch(u) and not same_structure(u, rec["prefix"], sig, tpl, rec["scheme_host"], True)]
        out[r["id"]] = {"listing_members": len(f["members"]), "listing_missed": miss_list,
                        "sitemap_same_structure": len(sm), "sitemap_missed": miss_sm,
                        "sitemap_missed_count": len(miss_sm), "matched_outside_structure": extra[:50],
                        "sitemap_not_in_listing": len([u for u in sm if u not in set(f["members"])])}
    (r3 / out_name).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = sum(1 for v in out.values() if v["listing_missed"] or v["sitemap_missed_count"])
    print(json.dumps({"rules": len(out), "with_known_misses": bad}))


# ------------------------------------------------------------------ stage: revise (v2)

def revise(r3, results_path):
    """v2 for rules that MISSED real members (holdout FN, listing or sitemap misses) and made
    no false match: widen only the variable classes (and the trailing slash) by the missed
    URLs' own characters, move the v1 holdout to regression and draw a NEW holdout and new
    negatives from samples never used before. Rules with any false positive are not revised."""
    r3 = Path(r3)
    fams = {f["id"]: (rec, f) for rec in json.loads((r3 / "families.json").read_text(encoding="utf-8"))
            for f in rec.get("families", [])}
    v1 = {r["id"]: r for r in json.loads((r3 / "samples-frozen.json").read_text(encoding="utf-8"))["rules"]}
    cov = json.loads((r3 / "coverage.json").read_text(encoding="utf-8"))
    res = json.loads(Path(results_path).read_text(encoding="utf-8"))["results"]
    fn, fp = defaultdict(list), defaultdict(list)
    for t in res:
        if t["expected"] is True and t["actual"] is False:
            fn[t["rule_id"]].append(t["url"])
        if t["expected"] is False and t["actual"] is True:
            fp[t["rule_id"]].append(t["url"])
    cache, out, idC, skipped = {}, [], [], []
    elsewhere = defaultdict(set)
    for ed in jl(r3 / "probe/edges.jsonl") + jl(r3 / "detail-links.jsonl"):
        u = ed["resolved_url"].split("#")[0]
        if u.startswith(("http://", "https://")) and parsable(u):
            elsewhere[urlsplit(u).netloc].add((u, ed["entry_id"]))
    for rid, r in v1.items():
        c = cov[rid]
        misses = fn[rid] + c["listing_missed"] + c["sitemap_missed"]
        if not misses:
            continue
        if fp[rid] or c["matched_outside_structure"]:
            skipped.append({"id": rid, "why": "存在误配，不放宽"})
            continue
        rec, f = fams[rid]
        sh, prefix = rec["scheme_host"], rec["prefix"]
        sig = tuple(x if not isinstance(x, list) else tuple(x) for x in f["signature"])
        tpl1 = [tuple(t) for t in f["template"]]
        induced_from = [u for u in f["inference"] if u not in set(r["holdout_pos"])] \
            if r["holdout_source"] == "listing_split" else f["inference"]
        # decide the v2 holdout BEFORE widening: if no unused sample exists anywhere, hold out part
        # of the missed URLs themselves and widen with the rest only
        sm = sitemap_urls(r3, cache, sh)
        miss_hold = []
        pre_used = {u.rstrip("/") for u in set(r["inference"]) | set(r["holdout_pos"]) | set(r["holdout_neg"])
                    | set(induced_from) | set(misses)}
        if r["holdout_source"] == "sitemap":
            pre_pool = [u for u in sm if same_structure(u, prefix, sig, tpl1, sh, r["slash_mode"] == "optional")
                        and u.rstrip("/") not in pre_used]
        else:
            pre_pool = [u for u in list(f["later_members"]) + list(f["members"]) if u.rstrip("/") not in pre_used]
        if not pre_pool:  # links seen on other pages of this host (other entries, detail pages)
            pre_pool = [u for u, e2 in elsewhere[urlsplit(sh).netloc] if e2 != rec["entry_id"]
                        and same_structure(u, prefix, sig, tpl1, sh, r["slash_mode"] == "optional")
                        and u.rstrip("/") not in pre_used]
        uniq_miss = sorted(set(misses))
        list_hold = []
        if not pre_pool and len(uniq_miss) < 2 and len(induced_from) >= 8:
            # last resort: re-induce v2 without a random part of the listing, which becomes the holdout
            list_hold = sorted(random.Random(f"{SEED}-{rid}-v2split").sample(
                induced_from, min(MAX_HOLD, len(induced_from) // 4)))
            induced_from = [u for u in induced_from if u not in list_hold]
        if not pre_pool and len(uniq_miss) >= 2:
            miss_hold = sorted(random.Random(f"{SEED}-{rid}-misssplit").sample(uniq_miss, min(MAX_HOLD, len(uniq_miss) // 2)))
        widen_with = [u for u in uniq_miss if u not in miss_hold]
        basis = sorted(set(induced_from) | set(widen_with))
        tpl = template_of(basis, prefix)
        # keep v1 literal positions literal only if every basis URL agrees (same_structure guarantees it)
        slash_mode = r["slash_mode"]
        if any(signature(u, prefix)[1] != sig[1] for u in widen_with):
            slash_mode = "optional"
        queries = sorted(urlsplit(u).query for u in basis)
        pattern = build_pattern(sh, prefix, tpl, slash_mode, sig[2], queries)
        used = {u.rstrip("/") for u in set(r["inference"]) | set(r["holdout_pos"]) | set(r["holdout_neg"])
                | set(induced_from) | set(misses) | set(list_hold)}
        if r["holdout_source"] == "sitemap":
            pool = [u for u in sm if same_structure(u, prefix, sig, tpl1, sh, r["slash_mode"] == "optional")]
        elif r["holdout_source"] in ("later_pagination_pages", "listing_split"):
            pool = list(f["later_members"]) + list(f["members"])
        else:
            pool = [u for u, e2 in elsewhere[urlsplit(sh).netloc] if e2 != rec["entry_id"]
                    and same_structure(u, prefix, sig, tpl1, sh, r["slash_mode"] == "optional")]
        alias = re.compile(r"^" + re.escape(sh + prefix) + r"(index|default)\.[a-z]+$", re.I)
        pool = sorted({u for u in pool if u.rstrip("/") not in used and not alias.match(u)
                       and u.rstrip("/") != rec["final_url"].rstrip("/")})
        rnd = random.Random(f"{SEED}-{rid}-v2")
        if not pool and pre_pool:
            pool = sorted({u for u in pre_pool if u.rstrip("/") not in used})
        hold = sorted(rnd.sample(pool, min(MAX_HOLD, len(pool)))) or miss_hold or list_hold
        depth_total = len([x for x in urlsplit(r["inference"][0]).path.split("/") if x])
        outside = sorted({u for u in sm + rec["outside_prefix"] if u.startswith(sh)
                          and not urlsplit(u).path.startswith(prefix)
                          and len([x for x in urlsplit(u).path.split("/") if x]) == depth_total
                          and u.rstrip("/") not in used})
        negs = [rec["final_url"]] if rec["final_url"].rstrip("/") not in used else []  # fresh negatives only
        negs += rnd.sample(outside, min(4, len(outside)))
        if len(negs) < 4:
            seen_any = [u for u, _ in elsewhere[urlsplit(sh).netloc]]
            anyd = sorted({u for u in sm + rec["outside_prefix"] + seen_any if u.startswith(sh)
                           and not urlsplit(u).path.startswith(prefix) and u not in negs
                           and u.rstrip("/") not in used and not ASSET_EXT.search(urlsplit(u).path)})
            negs += rnd.sample(anyd, min(4 - len(negs), len(anyd)))
        others = sorted({u for g in rec["families"] if g["id"] != rid for u in g["members"]
                         if u.rstrip("/") not in used})
        negs += rnd.sample(others, min(2, len(others)))
        r2 = {**r, "version": 2, "pattern": pattern, "slash_mode": slash_mode,
              "variables": {f"seg{i}": t[1] + (f" + .{t[2]}" if t[0] == "varext" else "")
                            for i, t in enumerate(tpl) if t[0] != "lit"},
              "literals": {f"seg{i}": t[1] for i, t in enumerate(tpl) if t[0] == "lit"},
              "history": [{"version": 1, "pattern": r["pattern"], "holdout_fn": fn[rid][:10],
                           "listing_missed": c["listing_missed"][:10],
                           "sitemap_missed": c["sitemap_missed_count"]}],
              "assumptions": r["assumptions"] + ("；v2：变量字符集按 v1 漏配样本扩展，v1 留出转回归，重新抽取留出"
                                                 + ("（无新样本：扩展前留出一半漏配样本）" if miss_hold and hold == miss_hold else "")),
              "regression_pos": r["holdout_pos"], "regression_neg": r["holdout_neg"],
              "holdout_pos": hold, "holdout_neg": list(dict.fromkeys(negs))}
        out.append(r2)
        idC += [{"entry_id": rec["entry_id"], "url": u, "parent_url": None, "relation": f"{rid}:v2-holdout_pos"}
                for u in hold]
    body = json.dumps(out, ensure_ascii=False, sort_keys=True)
    (r3 / "samples-frozen-v2.json").write_text(json.dumps(
        {"frozen_at": now(), "seed": SEED, "sha256": hashlib.sha256(body.encode()).hexdigest(),
         "rules": out, "skipped": skipped}, ensure_ascii=False, indent=1), encoding="utf-8")
    (r3 / "identity-C-targets.json").write_text(json.dumps(idC, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps({"revised": len(out), "skipped_fp": len(skipped), "identity_C": len(idC),
                      "no_new_holdout": sum(1 for r in out if not r["holdout_pos"])}))


if __name__ == "__main__":
    stage, *args = sys.argv[1:]
    {"families": families, "freeze": freeze, "coverage": coverage, "revise": revise}[stage](*args)
