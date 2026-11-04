#!/usr/bin/env python3
"""Relaxed pass for the 87 earlier entries that had no usable regex (78 empty + 9 failed round-3 rules).

Same relaxed standard as fill/relax.py: the regex must be correct and usable (RE2 compiles, anchored,
no .* / .+, matches every real item link seen, does not match the home page or the listing / nav /
author / sibling-column pages recorded as negatives); it may also match items of other columns of
the same site (shared article paths).
Positives: links in the entry page's main content (round-3 crawl, fill2/links.json) that have the item
structure, plus search-engine results for hosts this environment cannot open (SEARCH below).
Live check: up to 2 positives per entry opened now (identity as in fill/run_entry.fetch).
Writes fill2/out/<entry_id>.json. Usage: python3 -I fill2/run2.py [--no-live]
"""
import json
import random
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import re2
import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "fill"))
import run_entry as RE  # noqa: E402

UNREACHABLE = {"www.bls.gov", "lbbonline.com", "www.crunchbase.com", "dealroom.co", "www.digitaling.com",
               "www.linkshop.com", "m.linkshop.com", "blog.linkshop.com"}
SITE = {"www.census.gov": "美国人口普查局（Census）", "www.bls.gov": "美国劳工统计局（BLS）", "www.forrester.com": "Forrester",
        "www.lovethework.com": "The Work（Cannes Lions）", "www.cim.co.uk": "CIM", "www.contagious.com": "Contagious",
        "contentmarketinginstitute.com": "Content Marketing Institute", "lbbonline.com": "LBB", "www.crunchbase.com": "Crunchbase",
        "dealroom.co": "Dealroom", "www.ctrchina.cn": "CTR 央视市场研究", "www.digitaling.com": "数英", "www.jiemian.com": "界面新闻",
        "www.linkshop.com": "联商网", "www.cheaa.org": "中国家用电器协会"}

# search-engine results (WebSearch, 2026-11-04) for hosts this environment cannot open
SEARCH = {
    "linkshop_news": ["http://www.linkshop.com/news/2024521000.shtml", "http://www.linkshop.com/news/2016366506.shtml",
                      "http://www.linkshop.com/news/2023508152.shtml", "http://www.linkshop.com/news/2012216434.shtml",
                      "http://www.linkshop.com/news/2024526844.shtml", "http://www.linkshop.com/news/2018411033.shtml"],
    "linkshop_m": ["http://m.linkshop.com/article/news/496494", "http://m.linkshop.com/article/news/528747",
                   "http://m.linkshop.com/article/news/530076", "http://m.linkshop.com/article/news/502784",
                   "http://m.linkshop.com/article/news/458098", "http://m.linkshop.com/article/news/505196",
                   "http://m.linkshop.com/article/news/526090"],
    "linkshop_blog": ["http://blog.linkshop.com/u/1005293771@qq.com/531777.html", "https://blog.linkshop.com/u/75635/507497.html",
                      "http://blog.linkshop.com/u/yiilong/554860.html", "https://blog.linkshop.com/u/13735588585/503580.html"],
    "lbb_work": ["https://lbbonline.com/work/135420", "https://lbbonline.com/work/132050", "https://lbbonline.com/work/132049"],
    "lbb_news": ["https://lbbonline.com/news/LinkedIn-The-Network-That-Works-For-You", "https://lbbonline.com/news/Work-of-the-Week-270226",
                 "https://lbbonline.com/news/big-w-appoints-72andsunny", "https://lbbonline.com/news/fujifilm-australia-hello-agency-of-record",
                 "https://lbbonline.com/news/joint-creative-agency-geely-auto", "https://lbbonline.com/news/VML-India-Kunal-Roy-and-Shekhar-Khanna",
                 "https://lbbonline.com/news/five-by-five-fbf", "https://lbbonline.com/news/collections-your-free-reel-and-newsletter-builder-on-lbb"],
    "lbb_reels": ["https://lbbonline.com/reels/1000000039", "https://lbbonline.com/reels/1000000066"],
    "crunchbase": ["https://www.crunchbase.com/organization/crunchbase", "https://www.crunchbase.com/organization/profiles",
                   "https://www.crunchbase.com/organization/company", "https://www.crunchbase.com/organization/guide-4412",
                   "https://www.crunchbase.com/organization/lookup-2", "https://www.crunchbase.com/organization/inc"],
    "mafias": ["https://dealroom.co/talent/founder-mafias/n26/", "https://dealroom.co/talent/founder-mafias/revolut/",
               "https://dealroom.co/talent/founder-mafias/wise/", "https://dealroom.co/talent/founder-mafias/angellist/",
               "https://dealroom.co/talent/founder-mafias/adyen/", "https://dealroom.co/talent/founder-mafias/monzo-bank/",
               "https://dealroom.co/talent/founder-mafias/stripe/"],
    "digitaling": ["https://www.digitaling.com/moments/13677.html", "https://www.digitaling.com/moments/31758.html",
                   "https://www.digitaling.com/moments/13901.html"],
    "bls_cex": ["https://www.bls.gov/cex/tables.htm", "https://www.bls.gov/cex/tables-getting-started-guide.htm",
                "https://www.bls.gov/cex/data.htm", "https://www.bls.gov/cex/csxstnd.htm",
                "https://www.bls.gov/cex/labstat/ce-labstat-getting-started-guide.htm"],
    "talks": ["https://www.lovethework.com/en/talks/new-for-2026-the-cannes-lions-wrap-up-live-74211",
              "https://www.lovethework.com/en/talks-series/cannes-lions-2026", "https://www.lovethework.com/en/talks-series/cannes-lions-2025",
              "https://www.lovethework.com/en/talks-series/cannes-lions-2024"],
    "forrester": ["https://www.forrester.com/b2b-marketing/demand-abm/"],
}
SEARCH_NEG = {
    "lbb": ["https://lbbonline.com/companies/dept", "https://lbbonline.com/work/reels", "https://lbbonline.com/"],
    "crunchbase": ["https://www.crunchbase.com/discover/organization.companies"],
    "digitaling": ["https://www.digitaling.com/moments/hot", "https://www.digitaling.com/moments/copy",
                   "https://www.digitaling.com/people/moments/10059991", "https://www.digitaling.com/company/moments/34439"],
    "dealroom": ["https://dealroom.co/talent/founder-dna/", "https://dealroom.co/talent/founder-mafias/"],
    "linkshop": ["http://www.linkshop.com/intro/index.shtml", "http://www.linkshop.com/news/?ClassID=90", "http://m.linkshop.com/page/news/zx"],
}

LS_NEWS = r"^https?://www\.linkshop\.com/news/[0-9]+\.shtml$"
LS_M = r"^https?://m\.linkshop\.com/article/news/[0-9]+$"
JM_ART = r"^https://www\.jiemian\.com/article/[0-9]+\.html$"
JM_VID = r"^https://www\.jiemian\.com/video/[A-Za-z0-9]+\.html$"
CMI = r"^https://contentmarketinginstitute\.com/(?:ai-in-marketing|analytics-data|career-salary-outlook|content-creation-distribution|content-distribution-promotion|content-marketing-strategy|content-optimization|social-media-content|strategy-planning|measurement-optimization|research|[a-z]+-[a-z-]+)/[a-z0-9-]+$"


def defs(L):
    """entry_id -> dict(lines, pos_rx (selects positives from page links), neg_rx (selects negatives), extra_pos, extra_neg, status, basis)"""
    D = {}
    D["S1-R2-E1"] = dict(lines=[r"^https?://www\.census\.gov/retail/(?:[a-z]+/)?[a-z_]+\.html$"],
                         pos_rx=r"census\.gov/retail/", allow_entry=True, neg_rx=r"census\.gov/(?!retail/)", basis="零售调查栏目 /retail/ 下的说明、数据、发布页（含 index.html 本页）")
    D["S1-R3-E1"] = dict(lines=[r"^https://www\.bls\.gov/cex/(?:[a-z0-9-]+/)?[a-z0-9-]+\.htm$"], extra_pos=SEARCH["bls_cex"],
                         extra_neg=["https://www.bls.gov/news.release/cesan.htm"], basis="消费支出调查栏目 /cex/ 下的 .htm 页面；站点拦截本环境，样本来自搜索结果")
    D["S1-R3-E2"] = dict(lines=[r"^https://www\.bls\.gov/news\.release/(?:cesan\.htm|cesan\.nr0\.htm|cesan\.t[0-9]{2}\.htm|pdf/cesan\.pdf)$"],
                         extra_pos=["https://www.bls.gov/news.release/pdf/cesan.pdf"], extra_neg=["https://www.bls.gov/cex/tables.htm"],
                         status="单页（含跳转页）", basis="消费支出年度新闻稿单页：本页、正文页、表格页和 PDF 版；站点拦截本环境，PDF 地址来自搜索结果")
    D["S1-R50-E1"] = dict(lines=[r"^https://www\.forrester\.com/b2b-marketing/[a-z0-9-]+/$", r"^https://www\.forrester\.com/blogs/[a-z0-9-]+/$",
                                 r"^https://www\.forrester\.com/client-stories/[a-z0-9-]+/$"],
                          pos_rx=r"forrester\.com/(?:b2b-marketing|blogs|client-stories)/[a-z0-9-]+/$", extra_pos=SEARCH["forrester"],
                          neg_rx=r"forrester\.com/(?:blogs/author/|research/|[a-z-]+/$)", extra_neg=["https://www.forrester.com/blogs/category/b2b-marketing/"],
                          basis="B2B 营销页面上的子页面、博客文章、客户案例；博客、案例路径全站共用")
    D["S1-R67-E1"] = dict(lines=[r"^https://www\.lovethework\.com/en/talks/[a-z0-9-]+$", r"^https://www\.lovethework\.com/en/talks-series/[a-z0-9-]+$"],
                          extra_pos=SEARCH["talks"], neg_rx=r"lovethework\.com/(?!en/talks)", extra_neg=["https://www.lovethework.com/en/talks"],
                          basis="演讲详情 /en/talks/{slug} 和演讲系列 /en/talks-series/{年份}；卡片由脚本渲染，样本来自搜索结果")
    D["S1-R67-E2"] = dict(lines=[r"^https://www\.lovethework\.com/reports/[a-z0-9-]+$", r"^https://www\.lovethework\.com/en/[a-z0-9-]+-report-[0-9]{4}$"],
                          pos_rx=r"lovethework\.com/(?:reports/[a-z0-9-]+|en/[a-z0-9-]+-report-[0-9]{4})(?:\?|$)",
                          neg_rx=r"lovethework\.com/(?:awards|contact-us|learn-more|reports$|request-a-demo|talks|the-work|ai/)",
                          basis="报告详情 /reports/{slug}（参数 ?tab= 去掉）和 /en/{名称}-report-{年份}")
    D["S1-R73-E2"] = dict(lines=[r"^https://www\.cim\.co\.uk/learn-develop/training-development/view-all-courses/[a-z0-9-]+/$"],
                          pos_rx=r"view-all-courses/[a-z0-9-]+/$", neg_rx=r"cim\.co\.uk/(?:about|faqs|content-insights)/",
                          extra_neg=["https://www.cim.co.uk/learn-develop/training-development/view-all-courses/"], basis="课程详情 /view-all-courses/{slug}/")
    D["S1-R83-E1"] = dict(lines=[r"^https://www\.contagious\.com/(?:en/)?article/news-and-views/[a-z0-9-]+$"],
                          pos_rx=r"/article/news-and-views/", neg_rx=r"contagious\.com/(?:terms|get-in-touch|about|events|newsletter)",
                          basis="资讯文章 /article/news-and-views/{slug}-{32位编号}")
    D["S1-R83-E2"] = dict(lines=[r"^https://www\.contagious\.com/(?:en/)?(?:the-[a-z0-9-]+-20[0-9]{2}|grand-prix-winning-strategies-20[0-9]{2}|finding-your-centaur)$",
                                 r"^https://www\.contagious\.com/(?:en/)?article/[a-z0-9-]+$"],
                          pos_rx=r"contagious\.com/(?:en/)?(?:the-[a-z0-9-]+-20\d\d|grand-prix-winning-strategies-20\d\d|finding-your-centaur|article/[a-z0-9-]+)$",
                          neg_rx=r"contagious\.com/(?:about-us|event-sponsorship|events|get-in-touch|newsletter|submit-your-work|terms-of-use)",
                          basis="报告落地页（名称带年份）和报告文章 /article/{slug}")
    D["S1-R84-E2"] = dict(lines=[CMI], pos_rx=CMI[1:-1], neg_rx=r"contentmarketinginstitute\.com/(?:author|keyword|tag)/",
                          basis="文章地址 /{分类}/{slug}，分类路径全站共用；作者页、关键词页不匹配")
    D["S1-R84-E3"] = dict(lines=[CMI], pos_rx=CMI[1:-1], neg_rx=r"contentmarketinginstitute\.com/(?:author|keyword|tag|documents|latest-news|strategy-planning$|content-creation-distribution$)",
                          basis="电子书和模板也是 /{分类}/{slug} 文章页，分类路径全站共用")
    for e, kind, src in (("S1-R93-E1", "work", r"^https://lbbonline\.com/work/[0-9]+$"), ("S1-R93-E2", "news", r"^https://lbbonline\.com/news/[A-Za-z0-9-]+$"),
                         ("S1-R93-E3", "reels", r"^https://lbbonline\.com/reels/[0-9]+$")):
        D[e] = dict(lines=[src], extra_pos=SEARCH[f"lbb_{kind}"], extra_neg=SEARCH_NEG["lbb"],
                    basis=f"LBB {kind} 详情；站点拦截本环境（Cloudflare），样本来自搜索结果")
    D["S1-R144-E1"] = dict(lines=[r"^https://www\.crunchbase\.com/organization/[a-z0-9-]+$"], extra_pos=SEARCH["crunchbase"], extra_neg=SEARCH_NEG["crunchbase"],
                           basis="公司详情 /organization/{slug}；站点拦截本环境，样本来自搜索结果；详情需登录才能看全")
    D["S1-R152-E9"] = dict(lines=[r"^https://dealroom\.co/talent/founder-mafias/[a-z0-9-]+/$"], extra_pos=SEARCH["mafias"], extra_neg=SEARCH_NEG["dealroom"],
                           basis="各公司的 Founder Mafia 页 /talent/founder-mafias/{公司}/；站点拦截本环境，样本来自搜索结果")
    D["S1-R152-E11"] = dict(lines=[r"^https://dealroom\.co/vc-investment-dashboard/$"], extra_pos=["https://dealroom.co/vc-investment-dashboard/"],
                            extra_neg=["https://dealroom.co/investors/"], status="单页", allow_entry=True,
                            basis="实时看板单页，图表由接口渲染，没有下级条目地址；正则是本页地址")
    D["S2-R15-E2"] = dict(lines=[r"^https://www\.ctrchina\.cn/rich/report/[0-9]+$"], pos_rx=r"/rich/report/\d+$", basis="报告详情 /rich/report/{编号}")
    D["S2-R71-E1"] = dict(lines=[r"^https://www\.digitaling\.com/moments/[0-9]+\.html$"], extra_pos=SEARCH["digitaling"], extra_neg=SEARCH_NEG["digitaling"],
                          basis="发现动态详情 /moments/{编号}.html；站点拦截本环境，样本来自搜索结果")
    for e in L:
        if e.startswith("S2-R82-"):
            vid = any("/video/" in u for u in L[e])
            D[e] = dict(lines=[JM_ART] + ([JM_VID] if vid else []), pos_rx=r"jiemian\.com/(?:article/\d+|video/[A-Za-z0-9]+)\.html$",
                        neg_rx=r"(?:jiemian\.com/lists/|a\.jiemian\.com/|jiemian\.com/city/)",
                        basis="文章 /article/{编号}.html" + ("、视频 /video/{编号}.html" if vid else "") + "，路径全站共用（文章地址不带栏目号）")
    for e in L:
        if e.startswith("S2-R108-"):
            from collections import Counter
            c = Counter(re.search(r"/contents/(\d+)/", u).group(1) for u in L[e] if "/contents/" in u)
            ids = sorted((k for k, n in c.items() if n >= 3), key=int)
            if not ids:
                continue
            alt = ids[0] if len(ids) == 1 else "(?:" + "|".join(ids) + ")"
            D[e] = dict(lines=[rf"^https://www\.cheaa\.org/contents/{alt}/[0-9]+\.html$"], pos_rx=rf"cheaa\.org/contents/(?:{'|'.join(ids)})/\d+\.html$",
                        neg_rx=r"cheaa\.org/(?:channels/|contents/(?:119|19|441|442|5)/)",
                        basis=f"文章 /contents/{{栏目号}}/{{编号}}.html，栏目号写死为 {'、'.join(ids)}（本栏目页上列出的条目所在栏目）")
    for e in L:
        if e.startswith("S2-R86-"):
            col = e.endswith("-E3")
            D[e] = dict(lines=[LS_NEWS, LS_M] + ([r"^https?://blog\.linkshop\.com/u/[A-Za-z0-9@._-]+/[0-9]+\.html$"] if col else []),
                        extra_pos=SEARCH["linkshop_news"] + SEARCH["linkshop_m"] + (SEARCH["linkshop_blog"] if col else []),
                        extra_neg=SEARCH_NEG["linkshop"],
                        basis="联商网文章 /news/{编号}.shtml（及手机版 /article/news/{编号}）" + ("、专栏文章 blog.linkshop.com/u/{作者}/{编号}.html" if col else "")
                        + "；站点从本环境连接超时，样本来自搜索结果，栏目自己的条目格式未能打开确认")
    return D


def main(live=True):
    L = {k: set(v) for k, v in json.loads((HERE / "links.json").read_text(encoding="utf-8")).items()}
    ents = {}
    for d in ("output/round3", "batch2/output/round3"):
        for e in json.loads((ROOT / d / "entries.json").read_text(encoding="utf-8")):
            ents[e["entry_id"]] = e
    D = defs(L)
    sess = requests.Session()
    sess.headers["User-Agent"] = RE.UA
    (HERE / "out").mkdir(exist_ok=True)
    for eid in sorted(L, key=lambda x: (x.split("-")[0], int(x.split("-R")[1].split("-")[0]), int(x.split("-E")[1]))):
        e = ents[eid]
        raw = e["raw"] if "://" in e["raw"] else "https://" + e["raw"]
        host = urlsplit(raw).netloc
        d = D.get(eid)
        rec = {"entry_id": eid, "url": e["raw"], "site": SITE.get(host, host)}
        if not d:
            rec.update(status="无正则", pattern="", positives=[], negatives=[], basis="未找到可用的条目结构")
            (HERE / "out" / f"{eid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            print(eid, "none")
            continue
        rxs = [re2.compile(x) for x in d["lines"]]
        hit = lambda u: any(r.fullmatch(u) for r in rxs)  # noqa: E731
        links = {u if re.search(r"#!?/", u) else u.split("#")[0] for u in L.get(eid, set())}
        links = {u.split("?tab=")[0] for u in links}
        pos = set(d.get("extra_pos", []))
        if d.get("pos_rx"):
            pos |= {u for u in links if re.search(d["pos_rx"], u)}
        entry = raw.split("#")[0].rstrip("/")
        negs = set(d.get("extra_neg", [])) | {f"https://{host}/"}
        if d.get("neg_rx"):
            negs |= {u for u in links if re.search(d["neg_rx"], u) and u not in pos}
        negs = {u for u in negs if u.rstrip("/") != entry and u not in pos}
        syn = all(x.startswith("^") and x.endswith("$") and ".*" not in x and ".+" not in x for x in d["lines"])
        pos_fail = sorted(u for u in pos if not hit(u))
        neg_fail = sorted(u for u in negs if hit(u))
        lv = []
        if live:
            cand = sorted(u for u in pos if hit(u))
            random.Random(eid).shuffle(cand)
            for u in cand[:2]:
                if urlsplit(u).netloc in UNREACHABLE:
                    lv.append({"url": u, "result": "本环境无法访问（样本来自搜索结果）"})
                    continue
                r = RE.fetch(sess, u)
                lv.append({"url": u, "status": r.get("status"), "final": r.get("final_url"),
                           "result": "可打开" if r.get("status") == 200 else f"返回 {r.get('status') or r.get('error', '')[:30]}"})
        ok = syn and not pos_fail and not neg_fail and len(pos) > 0
        rec.update(status=d.get("status", "已放宽"), pattern="\n".join(d["lines"]), positives=sorted(pos), negatives=sorted(negs),
                   pos_fail=pos_fail, neg_fail=neg_fail, syntax_ok=syn, live=lv, basis=d["basis"],
                   result="正确且能用" if ok else "有问题")
        (HERE / "out" / f"{eid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        print(eid, rec["result"], len(pos), len(negs), len(pos_fail), len(neg_fail), [x["result"] for x in lv], flush=True)


if __name__ == "__main__":
    main(live="--no-live" not in sys.argv)
