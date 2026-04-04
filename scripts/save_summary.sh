#!/usr/bin/env bash
#
# save_summary.sh — Persist an AI summary into checkpoint metadata.
#
# Uses git worktree to avoid switching branches in the user's working tree.
#
# Usage:
#   save_summary.sh <id> <summary_json_file>
#   echo '{"intent":"..."}' | save_summary.sh <id> -
#
# <id> can be:
#   - a session ID (UUID) → saves to the latest checkpoint for that session
#   - a checkpoint ID (16-char hex) → saves to that specific checkpoint
#

set -euo pipefail

CHECKPOINT_BRANCH="neander/checkpoints/v1"

ID="${1:?Usage: save_summary.sh <session_id_or_checkpoint_id> <summary_json_file_or_->}"
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

# --- Use git worktree to avoid switching branches in the user's working tree ---

WORKTREE_DIR="$(mktemp -d)"

cleanup() {
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null || true
    rm -rf "$WORKTREE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

git worktree add "$WORKTREE_DIR" "$CHECKPOINT_BRANCH" --quiet 2>/dev/null

# Do all work in the worktree
cd "$WORKTREE_DIR"

# Determine if ID is a checkpoint ID or session ID
# Checkpoint IDs are 16-char hex, session IDs are UUIDs with dashes
CHECKPOINT_ID=""
if echo "$ID" | grep -qE '^[0-9a-f]{16}$'; then
    # Direct checkpoint ID
    CHECKPOINT_ID="$ID"
else
    # Session ID — find latest checkpoint for this session
    MATCH="$(grep "$ID" index.log 2>/dev/null | tail -1 || true)"
    if [ -z "$MATCH" ]; then
        echo "Error: $ID not found in checkpoint index" >&2
        exit 1
    fi
    CHECKPOINT_ID="$(echo "$MATCH" | cut -d'|' -f1)"
fi

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

# Get session ID for commit message
SESSION_ID="$(python3 -c "import json; d=json.load(open('$METADATA_PATH')); print(d['session_ids'][0])" 2>/dev/null || echo "unknown")"

git add "$METADATA_PATH"
git commit -m "summary: session=${SESSION_ID:0:12} checkpoint=${CHECKPOINT_ID}" --quiet

cd - > /dev/null

# Push to remote after a delay to avoid racing with user's git push
if git remote get-url origin >/dev/null 2>&1; then
    (sleep 5 && git push origin "$CHECKPOINT_BRANCH" --quiet 2>/dev/null || true) &
fi

echo "Summary saved to checkpoint $CHECKPOINT_ID"
