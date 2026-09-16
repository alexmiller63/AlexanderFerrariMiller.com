#!/usr/bin/env bash
set -euo pipefail

workflow="$1"
shift
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

before="$(gh run list --repo "$repo" --workflow "$workflow" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
before="${before:-0}"

gh workflow run "$workflow" --repo "$repo" --ref main "$@"

run_id=""
for attempt in $(seq 1 30); do
  run_id="$(gh run list --repo "$repo" --workflow "$workflow" --event workflow_dispatch --limit 10 --json databaseId --jq "map(select(.databaseId > $before)) | sort_by(.databaseId) | last | .databaseId // empty")"
  if [[ -n "$run_id" ]]; then
    echo "Found $workflow run $run_id"
    gh run watch "$run_id" --repo "$repo" --exit-status
    exit $?
  fi
  echo "Waiting for dispatched $workflow run to appear ($attempt/30)..."
  sleep 2
done

echo "ERROR: dispatched $workflow run did not appear within 60 seconds" >&2
exit 1
