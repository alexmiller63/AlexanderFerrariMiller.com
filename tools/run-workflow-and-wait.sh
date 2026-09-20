#!/usr/bin/env bash
set -euo pipefail

workflow="$1"
shift
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

# Resolve the exact workflow filename through GitHub's Actions API before using
# its numeric ID for run-list matching or dispatch.
workflow_json="$(gh api "repos/$repo/actions/workflows/$workflow")"
workflow_id="$(jq -r '.id' <<<"$workflow_json")"
workflow_state="$(jq -r '.state' <<<"$workflow_json")"
workflow_path="$(jq -r '.path' <<<"$workflow_json")"

wanted=".github/workflows/$workflow"
if [[ "$workflow_path" != "$wanted" ]]; then
  echo "ERROR: workflow filename $workflow resolved to unexpected path $workflow_path" >&2
  exit 1
fi

echo "Resolved $workflow_path to workflow id $workflow_id ($workflow_state)"

if [[ "$workflow_state" != "active" ]]; then
  echo "ERROR: workflow $workflow_path is not active (state=$workflow_state)" >&2
  exit 1
fi

# Record the dispatch time and current latest run before sending the request.
# This prevents attaching to an older or simultaneous manual dispatch.
dispatch_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
before="$(gh run list --repo "$repo" --workflow "$workflow_id" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
before="${before:-0}"

# workflow_dispatch accepts a branch or tag ref. In Actions, GITHUB_SHA can be
# a detached commit SHA, which GitHub rejects here with HTTP 422.
dispatch_ref="${GITHUB_REF_NAME:?GITHUB_REF_NAME is required}"
echo "Dispatching $workflow_path on ref: $dispatch_ref"
gh workflow run "$workflow_id" --repo "$repo" --ref "$dispatch_ref" "$@"

# Resolve the branch/tag to its commit SHA so we can identify the exact child
# run without confusing another simultaneous manual dispatch.
dispatch_sha="$(gh api "repos/$repo/commits/$dispatch_ref" --jq '.sha')"

run_id=""
for attempt in $(seq 1 60); do
  run_id="$(gh run list --repo "$repo" --workflow "$workflow_id" --event workflow_dispatch --limit 20 --json databaseId,createdAt,headSha,status --jq "map(select(.databaseId > $before and .createdAt >= \"$dispatch_time\" and .headSha == \"$dispatch_sha\")) | sort_by(.createdAt) | last | .databaseId // empty")"
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
