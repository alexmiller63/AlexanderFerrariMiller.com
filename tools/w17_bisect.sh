#!/usr/bin/env bash
set -uo pipefail

GOOD_REF="95a9dd78fce7dd4044bee20a012b4ae88db8bfaa"
BAD_REF="$(git rev-parse HEAD)"
HARNESS_DIR="${RUNNER_TEMP:-/tmp}/w17-bisect-harness"
mkdir -p "$HARNESS_DIR"

cat > "$HARNESS_DIR/test-one.sh" <<'SH'
#!/usr/bin/env bash
set -uo pipefail
ref="$(git rev-parse HEAD)"
echo "::group::Testing actual W17 at $ref"
PLANET_FINDER_DIAGNOSTIC_LEVEL=0 timeout 400s python tools/generate_planet_finders.py --year 2026 --week 17
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
"$HARNESS_DIR/test-one.sh" || { echo "Safety stop: GOOD_REF failed"; exit 1; }

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
