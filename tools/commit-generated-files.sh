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
git push