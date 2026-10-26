#!/usr/bin/env python3
"""Round-2 v2 freeze for R2-OPT-ARTICLES-DETAIL after its v1 holdout failed.

v1 missed a real slug with a double hyphen (".../website--app"). v2 widens only that:
hyphen runs are allowed between alphanumeric groups. The v1 holdout pairs were read
while fixing the rule, so they move to regression; a NEW holdout (positives and
negatives) is drawn with a new seed from sitemap members never used before.

Usage: python3 -I freeze_samples_r2_v2.py <samples-frozen.json> <sitemaps_dir> > samples-frozen-v2.json
"""
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SEED = 20261027
RID = "R2-OPT-ARTICLES-DETAIL"


def main(v1_path, sm_dir):
    v1 = json.loads(Path(v1_path).read_text(encoding="utf-8"))
    locs = []
    for f in ("opt-sm1.xml", "opt-sm2.xml"):
        locs += re.findall(r"<loc>([^<]+)</loc>", (Path(sm_dir) / f).read_text(encoding="utf-8"))
    used = set()
    for r in v1["rules"]:
        for k in ("inference", "holdout_pos", "holdout_neg"):
            used |= {u.rstrip("/") for u in r[k]}
    rnd = random.Random(SEED)

    def pool(rx):
        return sorted({l for l in locs if re.match(rx, l) and l.rstrip("/") not in used})
    art = pool(r"^https://www\.optimizely\.com/field-notes/articles/[^/]+$")
    neg = (rnd.sample(pool(r"^https://www\.optimizely\.com/field-notes/guides/[^/]+$"), 2)
           + rnd.sample(pool(r"^https://www\.optimizely\.com/[a-z]{2}(-[a-z]{2})?/field-notes/articles/"), 2)
           + rnd.sample(pool(r"^https://www\.optimizely\.com/field-notes/customer-stories/[^/]+$"), 1)
           + rnd.sample(pool(r"^https://www\.optimizely\.com/field-notes/videos/[^/]+$"), 1)
           + rnd.sample(pool(r"^https://www\.optimizely\.com/field-notes/collections/[^/]+$"), 1))
    r1 = next(r for r in v1["rules"] if r["id"] == RID)
    r2 = {**r1,
          "version": 2,
          "pattern": r"^https://www\.optimizely\.com/field-notes/articles/[a-z0-9]+(?:-+[a-z0-9]+)*/?$",
          "variables": {**r1["variables"], "slug": "小写字母数字，组间允许一个或多个连字符（v1 留出集实测出现 '--'）"},
          "history": [{"version": 1, "pattern": r1["pattern"], "result": "holdout FN 1/6: .../how-to-create-a-user-flow-map-for-your-website--app"}],
          "regression_pos": r1["holdout_pos"], "regression_neg": r1["holdout_neg"],
          "holdout_pos": sorted(rnd.sample(art, 6)), "holdout_neg": neg}
    body = json.dumps(r2, ensure_ascii=False, sort_keys=True)
    json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": SEED,
               "sha256": hashlib.sha256(body.encode()).hexdigest(), "supersedes_v1_sha256": v1["sha256"],
               "rules": [r2]}, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:3])
