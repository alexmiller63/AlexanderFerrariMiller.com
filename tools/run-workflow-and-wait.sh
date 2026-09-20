#!/usr/bin/env bash
set -euo pipefail

workflow="$1"
shift
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

# Record the dispatch time before sending the request. Matching only on run ID
# can attach to the wrong run when another manual dispatch is in flight.
dispatch_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
before="$(gh run list --repo "$repo" --workflow "$workflow" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
before="${before:-0}"

# Resolve the workflow by its current path/name before dispatching. This avoids
# GitHub CLI silently using an obsolete workflow registration after workflow
# files have been replaced or renamed.
workflow_json="$(gh workflow list --repo "$repo" --all --json id,path,state,name --jq \
  --arg wanted ".github/workflows/$workflow" \
  'map(select(.path == $wanted)) | if length == 1 then .[0] else empty end')"

if [[ -z "$workflow_json" ]]; then
  echo "ERROR: could not uniquely resolve current workflow path .github/workflows/$workflow" >&2
  gh workflow list --repo "$repo" --all >&2
  exit 1
fi

workflow_id="$(jq -r '.id' <<<"$workflow_json")"
workflow_state="$(jq -r '.state' <<<"$workflow_json")"
workflow_path="$(jq -r '.path' <<<"$workflow_json")"
echo "Resolved $workflow_path to workflow id $workflow_id ($workflow_state)"

if [[ "$workflow_state" != "active" ]]; then
  echo "ERROR: workflow $workflow_path is not active (state=$workflow_state)" >&2
  exit 1
fi

gh workflow run "$workflow_id" --repo "$repo" --ref main "$@"

run_id=""
for attempt in $(seq 1 60); do
  run_id="$(gh run list --repo "$repo" --workflow "$workflow" --event workflow_dispatch --limit 20 --json databaseId,createdAt,headBranch,status --jq "map(select(.databaseId > $before and .createdAt >= \"$dispatch_time\" and .headBranch == \"main\")) | sort_by(.createdAt) | last | .databaseId // empty")"
  if [[ -n "$run_id" ]]; then
    echo "Found dispatched $workflow run $run_id (created at/after $dispatch_time)"
    gh run watch "$run_id" --repo "$repo" --exit-status
    exit $?
  fi
  echo "Waiting for exact dispatched $workflow run to appear ($attempt/60)..."
  sleep 2
done

echo "ERROR: exact dispatched $workflow run did not appear within 120 seconds" >&2
exit 1
