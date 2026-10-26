#!/usr/bin/env python3
"""Freeze round-2 rule targets, labels and independent samples BEFORE identity checks.

Rules are written from the inference samples only (list-page cards seen during
discovery). Holdout positives come from a separate source (sitemap members that
are not on the list pages) and are drawn with a fixed seed; negatives are real
near-neighbour URLs from the same host. Labels are frozen here and never edited
to make metrics pass: a failing pair means fix the rule or downgrade it.

Usage: python3 -I freeze_samples_r2.py <round2_dir> <raw_dir> > samples-frozen.json
  round2_dir: output/round2 (probe/edges.jsonl, render/opt-*.json)
  raw_dir:    folder with opt-sm1.xml, opt-sm2.xml, cs-sm-list.txt (sitemaps fetched this round)
"""
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SEED = 20261026


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main(r2, raw):
    r2, raw = Path(r2), Path(raw)
    rnd = random.Random(SEED)
    edges = read_jsonl(r2 / "probe/edges.jsonl")
    locs = []
    for f in ("opt-sm1.xml", "opt-sm2.xml"):
        locs += re.findall(r"<loc>([^<]+)</loc>", (raw / f).read_text(encoding="utf-8"))
    cs_sm = [l.strip() for l in (raw / "cs-sm-list.txt").read_text(encoding="utf-8").splitlines() if l.strip()]

    # ---- Contentsquare blog details (entry S1-R121-E1)
    cs_list = sorted({e["resolved_url"].split("#")[0] for e in edges
                      if e["entry_id"] == "S1-R121-E1" and e["region"] in ("main", "body")
                      and re.match(r"^https://contentsquare\.com/blog/[^/]+/$", e["resolved_url"])})
    cs_hold = sorted(u for u in cs_sm if re.match(r"^https://contentsquare\.com/blog/[^/]+/$", u)
                     and u not in cs_list)
    cs_neg = ["https://contentsquare.com/blog/", "https://contentsquare.com/blog/page/2/",
              "https://contentsquare.com/blog/page/32/"]
    cs_neg += sorted(u for u in cs_sm if not u.startswith("https://contentsquare.com/blog/")
                     and u != "https://contentsquare.com/")[:5]

    # ---- Optimizely guides / articles (entries S1-R129-E1 / E2)
    def opt(section):
        rend = json.loads((r2 / f"render/opt-{section}.json").read_text(encoding="utf-8"))
        listed = sorted({a["href"] for a in rend["anchors"]
                         if re.match(rf"^https://www\.optimizely\.com/field-notes/{section}/[^/#]+/?$", a["href"])})
        listed_norm = {u.rstrip("/") for u in listed}
        sm = sorted({l for l in locs if re.match(rf"^https://www\.optimizely\.com/field-notes/{section}/[^/]+$", l)})
        pool = [u for u in sm if u not in listed_norm]
        return listed, sorted(rnd.sample(pool, 6)), sm
    g_list, g_hold, g_sm = opt("guides")
    a_list, a_hold, a_sm = opt("articles")
    others = {k: sorted(l for l in locs if re.match(rf"^https://www\.optimizely\.com/field-notes/{k}/[^/]+$", l))
              for k in ("customer-stories", "videos", "events", "collections")}
    loc_g = sorted(l for l in locs if re.match(r"^https://www\.optimizely\.com/[a-z]{2}(-[a-z]{2})?/field-notes/guides/", l))
    loc_a = sorted(l for l in locs if re.match(r"^https://www\.optimizely\.com/[a-z]{2}(-[a-z]{2})?/field-notes/articles/", l))
    common_neg = [rnd.choice(others["customer-stories"]), rnd.choice(others["videos"]),
                  rnd.choice(others["events"])]
    g_neg = ["https://www.optimizely.com/field-notes/guides", rnd.choice(loc_g)] + rnd.sample(
        [u for u in a_sm if u.rstrip("/") not in {x.rstrip("/") for x in a_list}], 2) + common_neg
    a_neg = ["https://www.optimizely.com/field-notes/articles", rnd.choice(loc_a)] + rnd.sample(
        [u for u in g_sm if u.rstrip("/") not in {x.rstrip("/") for x in g_list}], 2) + common_neg

    rules = [
        {"id": "R2-CS-BLOG-DETAIL", "entry_ids": ["S1-R121-E1"],
         "target": "Contentsquare 英文博客文章详情（/blog/ 栏目专属单段 slug，带尾斜杠，与列表链接及最终地址一致）",
         "family": "栏目专属路径",
         "pattern": r"^https://contentsquare\.com/blog/[a-z0-9]+(?:-[a-z0-9]+)*/$",
         "variables": {"slug": "小写字母数字与单个连字符；277 个列表卡片全部符合"},
         "assumptions": "完整 URL、区分大小写、无 query/fragment；/blog/page/N/ 是两段路径，不匹配",
         "inference": cs_list, "holdout_pos": cs_hold, "holdout_neg": cs_neg},
        {"id": "R2-OPT-GUIDES-DETAIL", "entry_ids": ["S1-R129-E1"],
         "target": "Optimizely Field Notes 英文 guides 详情：列表链接带尾斜杠（308 跳转），最终地址不带尾斜杠，两种形式都保留",
         "family": "栏目专属路径",
         "pattern": r"^https://www\.optimizely\.com/field-notes/guides/[a-z0-9]+(?:-[a-z0-9]+)*/?$",
         "variables": {"slug": "小写字母数字与连字符", "trailing_slash": "列表 href 有、308 最终地址无，两者均实测"},
         "assumptions": "仅英文默认语言路径；/de/ 等语言版本不在入口范围内，作反例",
         "inference": g_list, "holdout_pos": g_hold, "holdout_neg": g_neg},
        {"id": "R2-OPT-ARTICLES-DETAIL", "entry_ids": ["S1-R129-E2"],
         "target": "Optimizely Field Notes 英文 articles 详情：同上，两种尾斜杠形式",
         "family": "栏目专属路径",
         "pattern": r"^https://www\.optimizely\.com/field-notes/articles/[a-z0-9]+(?:-[a-z0-9]+)*/?$",
         "variables": {"slug": "小写字母数字与连字符", "trailing_slash": "同上"},
         "assumptions": "同上",
         "inference": a_list, "holdout_pos": a_hold, "holdout_neg": a_neg},
    ]
    body = json.dumps(rules, ensure_ascii=False, sort_keys=True)
    json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": SEED,
               "sha256": hashlib.sha256(body.encode()).hexdigest(),
               "sources": {"contentsquare_sitemap": "https://contentsquare.com/sitemap_index.xml (138 loc，截断至 f 开头)",
                           "optimizely_sitemap": "https://www.optimizely.com/sitemap.xml → 2 个 CMP 子 sitemap"},
               "counts": {"cs_sitemap_blog_total": len([u for u in cs_sm if '/blog/' in u]),
                          "opt_sitemap_guides_en": len(g_sm), "opt_sitemap_articles_en": len(a_sm)},
               "rules": rules}, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:3])
