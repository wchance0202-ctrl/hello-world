#!/usr/bin/env bash
# Round 3 pipeline after probe/render/sitemaps are in place (run from url-pattern-verification/).
#   RE2_NODE_MODULE: absolute path of the node-re2 package (validate_patterns.mjs engine_module)
#   SKILL_DIR:       extract-url-patterns skill folder (for validate_patterns.mjs)
# Identity checks and detail-link fetches are resumable: URLs already recorded are not requested again.
set -euo pipefail
OUT="${OUT:-output}"            # batch output folder (output, batch2/output, ...)
INPUT="${INPUT:-input/原始输入_内联粘贴.txt}"
R3="$OUT/round3"
: "${RE2_NODE_MODULE:?set RE2_NODE_MODULE}"
: "${SKILL_DIR:?set SKILL_DIR}"
mkdir -p "$R3/tests"

run_tests() {  # $1 = output tag; uses the v2 overlay when present
  local ov=()
  [ -f "$R3/samples-frozen-v2.json" ] && ov=(--overlay "$R3/samples-frozen-v2.json")
  cat "$R3"/identity-[ABC].jsonl > "$R3/tests/identity-checks.jsonl" 2>/dev/null || true
  python3 -I scripts/build_tests_r2.py generalized "$R3/samples-frozen.json" "$R3/tests/identity-checks.jsonl" "${ov[@]}" > "$R3/tests/r3-tests.json"
  python3 -I - "$R3/tests/r3-tests.json" "$RE2_NODE_MODULE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); d["engine_module"] = sys.argv[2]
json.dump(d, open(sys.argv[1].replace(".json", ".node.json"), "w"))
PY
  node "$SKILL_DIR/scripts/validate_patterns.mjs" "$R3/tests/r3-tests.node.json" > "$R3/tests/r3$1.node-re2.json"
  python3 -I scripts/run_re2_py.py "$R3/tests/r3-tests.json" > "$R3/tests/r3$1.google-re2.json"
}

python3 -I scripts/analyze_r3.py families "$OUT/entries.json" "$R3"
python3 -I scripts/redirect_check.py "$R3/identity-A-targets.json" "$R3/identity-A.jsonl" --delay 1 --workers 16
python3 -I scripts/analyze_r3.py freeze "$R3"
# families still without a holdout source: links on two of their own detail pages, then re-freeze
python3 -I - "$R3" <<'PY'
import json, sys
r3 = sys.argv[1]
R = json.load(open(f"{r3}/samples-frozen.json"))["rules"]
T = [{"family_id": r["id"], "entry_id": r["entry_ids"][0], "url": u} for r in R if not r["holdout_pos"] for u in r["inference"][:2]]
json.dump(T, open(f"{r3}/detail-links-targets.json", "w"), indent=0)
PY
python3 -I scripts/detail_links.py "$R3/detail-links-targets.json" "$R3/detail-links.jsonl" --delay 1
python3 -I scripts/analyze_r3.py freeze "$R3"
python3 -I scripts/redirect_check.py "$R3/identity-B-targets.json" "$R3/identity-B.jsonl" --delay 1 --workers 16

# v1: test, coverage, then revise rules that missed real members
rm -f "$R3/samples-frozen-v2.json"
run_tests -v1
python3 -I scripts/analyze_r3.py coverage "$R3" "$R3/tests/r3-v1.google-re2.json" coverage-v1.json
cp "$R3/coverage-v1.json" "$R3/coverage.json"
python3 -I scripts/analyze_r3.py revise "$R3" "$R3/tests/r3-v1.google-re2.json"
python3 -I scripts/redirect_check.py "$R3/identity-C-targets.json" "$R3/identity-C.jsonl" --delay 1 --workers 16

# final: v1 + v2 overlay
run_tests ""
python3 -I scripts/analyze_r3.py coverage "$R3" "$R3/tests/r3.google-re2.json"
python3 -I scripts/apply_round3.py "$OUT"
python3 -I scripts/readback_check.py "$INPUT" "$R3"
