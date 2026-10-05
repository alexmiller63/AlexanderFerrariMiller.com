#!/usr/bin/env bash
set -uo pipefail

GOOD_REF="95a9dd78fce7dd4044bee20a012b4ae88db8bfaa"
BAD_REF="$(git rev-parse HEAD)"
HARNESS_DIR="${RUNNER_TEMP:-/tmp}/w17-bisect-harness"
mkdir -p "$HARNESS_DIR"
cp tests/test_planet_finder_w17_ladder.py "$HARNESS_DIR/test_planet_finder_w17_ladder.py"

cat > "$HARNESS_DIR/oracle.py" <<'PY'
import sys
sys.path.insert(0, "tools")
sys.path.insert(0, sys.argv[1])
from test_planet_finder_w17_ladder import (
    ALIGNMENT_CHAIN, bodies_for, names, expected_alignment,
    expected_conjunction, assert_valid,
)
from planet_finder_geometry import FinderMode, alignment_groups, conjunction_groups
from planet_finder_search import layout

selected = ALIGNMENT_CHAIN[:6] + ["Venus"]
source = bodies_for(selected)
assert names(alignment_groups(source)) == expected_alignment(7)
assert names(conjunction_groups(source)) == expected_conjunction(7)
result = layout(
    FinderMode.GREEK, source, target_solutions=5,
    budget={"max_node_candidates": 200, "max_seconds": 120.0},
    context_label="W17-bisect-venus-exact-54.923",
)
assert_valid(result, source)
PY

cat > "$HARNESS_DIR/test-one.sh" <<'SH'
#!/usr/bin/env bash
set -uo pipefail
ref="$(git rev-parse HEAD)"
echo "::group::Testing $ref"
PLANET_FINDER_DIAGNOSTIC_LEVEL=0 timeout 130s python "$HARNESS_DIR/oracle.py" "$HARNESS_DIR"
rc=$?
echo "::endgroup::"
if [ "$rc" -eq 0 ]; then
  echo "RESULT $ref PASS"
  exit 0
fi
echo "RESULT $ref FAIL (rc=$rc)"
exit 1
SH
chmod +x "$HARNESS_DIR/test-one.sh"

export HARNESS_DIR
echo "Verifying GOOD endpoint $GOOD_REF"
git checkout --detach "$GOOD_REF"
"$HARNESS_DIR/test-one.sh"

echo "Verifying BAD endpoint $BAD_REF"
git checkout --detach "$BAD_REF"
if "$HARNESS_DIR/test-one.sh"; then
  echo "Safety stop: BAD_REF unexpectedly passed"
  exit 1
fi

git bisect reset || true
git bisect start "$BAD_REF" "$GOOD_REF"
set +e
git bisect run "$HARNESS_DIR/test-one.sh"
rc=$?
set -e
git bisect log
git bisect reset
exit "$rc"
