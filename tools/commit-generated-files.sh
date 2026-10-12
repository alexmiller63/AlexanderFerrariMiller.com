#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <commit-message> <file-or-pattern> [file-or-pattern ...]"
  exit 1
fi
COMMIT_MESSAGE="$1"
shift
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -- "$@"
if git diff --cached --quiet; then
  echo "No generated files to commit."
  exit 0
fi
git commit -m "$COMMIT_MESSAGE"
branch="$(git symbolic-ref --quiet --short HEAD)"
for attempt in 1 2 3 4 5; do
  git fetch origin "$branch"
  if ! git rebase "origin/$branch"; then
    git rebase --abort || true
    echo "Conflict: generated commit preserved locally." >&2
    exit 1
  fi
  if git push origin "HEAD:$branch"; then
    echo "Published on attempt $attempt"
    exit 0
  fi
  sleep "$((attempt * 2))"
done
echo "Push failed after five attempts; generated commit preserved locally." >&2
exit 1
