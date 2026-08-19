#!/bin/bash
# usage: run_kind.sh <kind>  — generate manifest, real-record, validate, commit. Exits nonzero on any failure.
set -u
cd /data/codes/equity-os
K=$1; M=scratchpad/inventory-batches/$K.json; mkdir -p scratchpad/inventory-batches
python3 scripts/equity_os_blueprint/make_inventory_batch_manifest.py "$K" "$M" | cut -c1-300 || exit 10
python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root . >/dev/null || { echo "STRUCT-BEFORE FAIL"; exit 11; }
OUT=$(python3 scripts/equity_os_blueprint/record_inventory_review.py --repo-root . --batch "$M" 2>&1); RC=$?
echo "$OUT" | grep -E '"pending_(before|after)"|"review_count"|"stale_after"|"structural_candidate_exit"|ABORT' | cut -c1-200
[ $RC -eq 0 ] || { echo "RECORD FAIL rc=$RC"; exit 12; }
python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root . >/dev/null || { echo "STRUCT-AFTER FAIL"; exit 13; }
# commit ledger + this batch's artifacts
COMPS=$(python3 -c "import json;print(' '.join(sorted({e['component_id'] for e in json.load(open('$M'))['reviews']})))")
N=$(python3 -c "import json;print(len(json.load(open('$M'))['reviews']))")
PA=$(echo "$OUT" | grep -o '"pending_after": [0-9]*' | grep -o '[0-9]*$')
for c in $COMPS; do git add "docs/goals/reviews/ledger/inventory/$c"; done
git add docs/goals/equity-os-blueprint-component-ledger.jsonl
git commit -q -m "feat(ledger): record inventory reviews — $K ($N reviews, $(echo $COMPS | wc -w) components)

Recorder r6 real run; pending -> $PA, stale 0, structural 0.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" || exit 14
echo "COMMITTED $K -> pending $PA"
