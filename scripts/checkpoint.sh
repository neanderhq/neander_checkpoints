#!/usr/bin/env bash
#
# checkpoint.sh — Save current session transcript to a git orphan branch.
#
# Called by the Stop hook or manually. Creates/updates an orphan branch
# (claude-sessions/checkpoints) with session transcripts and metadata.
#
# Usage: checkpoint.sh <session_jsonl_path> [commit_sha]
#

set -euo pipefail

CHECKPOINT_BRANCH="claude-sessions/checkpoints"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARSER="$SCRIPT_DIR/parse_jsonl.py"

SESSION_FILE="${1:?Usage: checkpoint.sh <session_jsonl_path> [commit_sha]}"
COMMIT_SHA="${2:-$(git rev-parse HEAD 2>/dev/null || echo 'none')}"
SESSION_ID="$(basename "$SESSION_FILE" .jsonl)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CHECKPOINT_ID="$(echo "${SESSION_ID}-${TIMESTAMP}" | shasum -a 256 | cut -c1-16)"

# Shard directory: first 2 chars / rest
SHARD_DIR="${CHECKPOINT_ID:0:2}/${CHECKPOINT_ID:2}"

if [ ! -f "$SESSION_FILE" ]; then
    echo "Error: Session file not found: $SESSION_FILE" >&2
    exit 1
fi

# Get session stats as JSON
STATS_JSON="$(python3 "$PARSER" stats --session "$SESSION_FILE" --json 2>/dev/null || echo '{}')"

# Build metadata
METADATA="$(cat <<EOF
{
  "checkpoint_id": "$CHECKPOINT_ID",
  "session_id": "$SESSION_ID",
  "commit_sha": "$COMMIT_SHA",
  "timestamp": "$TIMESTAMP",
  "stats": $STATS_JSON
}
EOF
)"

# Save current branch
ORIGINAL_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse HEAD)"
STASH_NEEDED=false
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    STASH_NEEDED=true
    git stash push -m "checkpoint-auto-stash" --quiet
fi

cleanup() {
    git checkout "$ORIGINAL_BRANCH" --quiet 2>/dev/null || true
    if [ "$STASH_NEEDED" = true ]; then
        git stash pop --quiet 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Create orphan branch if it doesn't exist
if ! git rev-parse --verify "$CHECKPOINT_BRANCH" >/dev/null 2>&1; then
    git checkout --orphan "$CHECKPOINT_BRANCH" --quiet
    git rm -rf . --quiet 2>/dev/null || true
    echo "# Claude Code Session Checkpoints" > README.md
    git add README.md
    git commit -m "Initialize checkpoint branch" --quiet
else
    git checkout "$CHECKPOINT_BRANCH" --quiet
fi

# Create checkpoint directory
mkdir -p "$SHARD_DIR"

# Copy transcript (will be redacted separately if needed)
cp "$SESSION_FILE" "$SHARD_DIR/transcript.jsonl"

# Write metadata
echo "$METADATA" | python3 -m json.tool > "$SHARD_DIR/metadata.json"

# Write condensed transcript
python3 "$PARSER" transcript --session "$SESSION_FILE" > "$SHARD_DIR/condensed.txt" 2>/dev/null || true

# Update index
INDEX_ENTRY="$CHECKPOINT_ID|$SESSION_ID|$COMMIT_SHA|$TIMESTAMP"
echo "$INDEX_ENTRY" >> index.log

# Commit
git add "$SHARD_DIR" index.log
git commit -m "checkpoint: ${CHECKPOINT_ID} session=${SESSION_ID:0:12} commit=${COMMIT_SHA:0:8}" --quiet

CHECKPOINT_REF="$(git rev-parse HEAD)"
echo "Checkpoint created: $CHECKPOINT_ID"
echo "  Session:  $SESSION_ID"
echo "  Commit:   $COMMIT_SHA"
echo "  Branch:   $CHECKPOINT_BRANCH"
echo "  Ref:      $CHECKPOINT_REF"
