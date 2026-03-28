#!/usr/bin/env bash
#
# save_summary.sh — Persist an AI summary into checkpoint metadata.
#
# Finds the checkpoint for a given session and updates its metadata.json
# with the provided summary JSON.
#
# Usage:
#   save_summary.sh <session_id> <summary_json_file>
#   echo '{"intent":"..."}' | save_summary.sh <session_id> -
#

set -euo pipefail

CHECKPOINT_BRANCH="neander/checkpoints/v1"

SESSION_ID="${1:?Usage: save_summary.sh <session_id> <summary_json_file_or_->}"
SUMMARY_SOURCE="${2:--}"

# Read summary from file or stdin
if [ "$SUMMARY_SOURCE" = "-" ]; then
    SUMMARY_JSON="$(cat)"
else
    if [ ! -f "$SUMMARY_SOURCE" ]; then
        echo "Error: Summary file not found: $SUMMARY_SOURCE" >&2
        exit 1
    fi
    SUMMARY_JSON="$(cat "$SUMMARY_SOURCE")"
fi

# Validate it's valid JSON
echo "$SUMMARY_JSON" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null || {
    echo "Error: Invalid JSON summary" >&2
    exit 1
}

# Check we're in a git repo with the checkpoint branch
if ! git rev-parse --verify "$CHECKPOINT_BRANCH" >/dev/null 2>&1; then
    echo "Error: checkpoint branch $CHECKPOINT_BRANCH not found" >&2
    exit 1
fi

# Save current branch
ORIGINAL_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse HEAD)"
STASH_NEEDED=false
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    STASH_NEEDED=true
    git stash push -m "save-summary-auto-stash" --quiet
fi

cleanup() {
    git checkout "$ORIGINAL_BRANCH" --quiet 2>/dev/null || true
    if [ "$STASH_NEEDED" = true ]; then
        git stash pop --quiet 2>/dev/null || true
    fi
}
trap cleanup EXIT

git checkout "$CHECKPOINT_BRANCH" --quiet

# Find checkpoint ID from index (use the latest entry for this session)
MATCH="$(grep "$SESSION_ID" index.log 2>/dev/null | tail -1 || true)"
if [ -z "$MATCH" ]; then
    echo "Error: session $SESSION_ID not found in checkpoint index" >&2
    exit 1
fi

CHECKPOINT_ID="$(echo "$MATCH" | cut -d'|' -f1)"
SHARD_DIR="${CHECKPOINT_ID:0:2}/${CHECKPOINT_ID:2}"
METADATA_PATH="$SHARD_DIR/metadata.json"

if [ ! -f "$METADATA_PATH" ]; then
    echo "Error: metadata not found at $METADATA_PATH" >&2
    exit 1
fi

# Merge summary into metadata
python3 -c "
import json, sys

with open('$METADATA_PATH') as f:
    metadata = json.load(f)

summary = json.loads('''$SUMMARY_JSON''')
metadata['summary'] = summary

with open('$METADATA_PATH', 'w') as f:
    json.dump(metadata, f, indent=2)
    f.write('\n')
"

git add "$METADATA_PATH"
git commit -m "summary: session=${SESSION_ID:0:12} checkpoint=${CHECKPOINT_ID}" --quiet

# Push to remote if one exists
if git remote get-url origin >/dev/null 2>&1; then
    git push origin "$CHECKPOINT_BRANCH" --quiet 2>/dev/null || true
fi

echo "Summary saved to checkpoint $CHECKPOINT_ID"
