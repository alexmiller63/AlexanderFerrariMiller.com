#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 WORKFLOW [gh workflow run arguments...]" >&2
  exit 2
fi

workflow="$1"
shift
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

MAX_DISCOVERY_ATTEMPTS=20
DISCOVERY_INTERVAL_SECONDS=15
STATUS_INTERVAL_SECONDS=60
RUN_LIST_LIMIT=20

api_with_retry() {
  local output rc attempt
  for attempt in 1 2 3 4 5; do
    set +e
    output="$(gh api "$@" 2>&1)"
    rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
      printf '%s\n' "$output"
      return 0
    fi
    if grep -qiE 'rate limit|HTTP 403|HTTP 429' <<<"$output"; then
      echo "GitHub API temporarily rate-limited; waiting 60 seconds before retry ($attempt/5)..." >&2
      sleep 60
      continue
    fi
    printf '%s\n' "$output" >&2
    return "$rc"
  done
  printf '%s\n' "$output" >&2
  return "$rc"
}

workflow_json="$(api_with_retry "repos/$repo/actions/workflows/$workflow")"
workflow_state="$(jq -r '.state' <<<"$workflow_json")"
workflow_path="$(jq -r '.path' <<<"$workflow_json")"

wanted=".github/workflows/$workflow"
if [[ "$workflow_path" != "$wanted" ]]; then
  echo "ERROR: workflow filename $workflow resolved to unexpected path $workflow_path" >&2
  exit 1
fi

echo "Resolved $workflow_path ($workflow_state)"

if [[ "$workflow_state" != "active" ]]; then
  echo "ERROR: workflow $workflow_path is not active (state=$workflow_state)" >&2
  exit 1
fi

dispatch_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
before="$(gh run list --repo "$repo" --workflow "$workflow" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
before="${before:-0}"

dispatch_ref="${GITHUB_REF_NAME:?GITHUB_REF_NAME is required}"
echo "Dispatching $workflow_path on ref: $dispatch_ref"
gh workflow run "$workflow" --repo "$repo" --ref "$dispatch_ref" "$@"

dispatch_sha="$(api_with_retry "repos/$repo/commits/$dispatch_ref" --jq '.sha')"

run_id=""
for attempt in $(seq 1 "$MAX_DISCOVERY_ATTEMPTS"); do
  set +e
  run_id="$(gh run list --repo "$repo" --workflow "$workflow" --event workflow_dispatch --limit "$RUN_LIST_LIMIT" --json databaseId,createdAt,headSha,status --jq "map(select(.databaseId > $before and .createdAt >= \"$dispatch_time\" and .headSha == \"$dispatch_sha\")) | sort_by(.createdAt) | last | .databaseId // empty" 2>/tmp/gh-run-list.err)"
  rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    if grep -qiE 'rate limit|HTTP 403|HTTP 429' /tmp/gh-run-list.err; then
      echo "Rate-limited while locating child run; waiting 60 seconds..."
      sleep 60
      continue
    fi
    cat /tmp/gh-run-list.err >&2
    exit "$rc"
  fi
  if [[ -n "$run_id" ]]; then
    echo "Found dispatched $workflow run $run_id (created at/after $dispatch_time)"
    break
  fi
  echo "Waiting for exact dispatched $workflow run to appear ($attempt/$MAX_DISCOVERY_ATTEMPTS)..."
  sleep "$DISCOVERY_INTERVAL_SECONDS"
done

if [[ -z "$run_id" ]]; then
  wait_seconds=$((MAX_DISCOVERY_ATTEMPTS * DISCOVERY_INTERVAL_SECONDS))
  echo "ERROR: exact dispatched $workflow run did not appear within $wait_seconds seconds" >&2
  exit 1
fi

while true; do
  set +e
  run_json="$(api_with_retry "repos/$repo/actions/runs/$run_id")"
  rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    exit "$rc"
  fi

  status="$(jq -r '.status' <<<"$run_json")"
  conclusion="$(jq -r '.conclusion // empty' <<<"$run_json")"
  echo "Child $workflow run $run_id: status=$status${conclusion:+ conclusion=$conclusion}"

  if [[ "$status" == "completed" ]]; then
    if [[ "$conclusion" == "success" ]]; then
      exit 0
    fi
    echo "ERROR: child $workflow run $run_id completed with conclusion=$conclusion" >&2
    exit 1
  fi

  sleep "$STATUS_INTERVAL_SECONDS"
done
