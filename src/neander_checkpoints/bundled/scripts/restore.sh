#!/usr/bin/env bash
#
# restore.sh — Restore a session JSONL from the checkpoint branch.
#
# Fetches the checkpoint branch from remote, finds the session transcript,
# and copies it to the correct ~/.claude/projects/ directory so
# `claude --resume <session-id>` works.
#
# Usage: restore.sh <session_id> [project_path]
#
#   session_id   — the UUID session ID to restore
#   project_path — the project working directory (defaults to pwd)
#                  used to determine the encoded project dir name
#

set -euo pipefail

CHECKPOINT_BRANCH="neander/checkpoints/v1"

SESSION_ID="${1:?Usage: restore.sh <session_id> [project_path]}"
PROJECT_PATH="${2:-$(pwd)}"

# Encode project path the same way Claude Code does: / → -, _ → -
ENCODED_DIR="$(echo "$PROJECT_PATH" | sed 's|/|-|g; s|_|-|g')"
TARGET_DIR="$HOME/.claude/projects/$ENCODED_DIR"
TARGET_FILE="$TARGET_DIR/$SESSION_ID.jsonl"

# Check if already exists locally
if [ -f "$TARGET_FILE" ]; then
    echo "Session already exists locally: $TARGET_FILE"
    echo "To resume: claude --resume $SESSION_ID"
    exit 0
fi

# Check we're in a git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: not in a git repository" >&2
    exit 1
fi

# Fetch checkpoint branch from remote
echo "Fetching checkpoint branch from remote..."
if ! git fetch origin "$CHECKPOINT_BRANCH" --quiet 2>/dev/null; then
    echo "Error: could not fetch $CHECKPOINT_BRANCH from remote" >&2
    echo "The checkpoint branch may not exist on the remote yet." >&2
    exit 1
fi

# Fast path: check index.log first
echo "Searching for session $SESSION_ID..."
FOUND=""
TRANSCRIPT_FILE=""

INDEX="$(git show "origin/$CHECKPOINT_BRANCH:index.log" 2>/dev/null || true)"
MATCH="$(echo "$INDEX" | grep "$SESSION_ID" | tail -1 || true)"
if [ -n "$MATCH" ]; then
    CHECKPOINT_ID="$(echo "$MATCH" | cut -d'|' -f1)"
    SHARD_DIR="${CHECKPOINT_ID:0:2}/${CHECKPOINT_ID:2}"
    # New format: transcript-<session_id>.jsonl
    if git show "origin/$CHECKPOINT_BRANCH:$SHARD_DIR/transcript-${SESSION_ID}.jsonl" >/dev/null 2>&1; then
        FOUND="$SHARD_DIR"
        TRANSCRIPT_FILE="transcript-${SESSION_ID}.jsonl"
    # Legacy format: transcript.jsonl
    elif git show "origin/$CHECKPOINT_BRANCH:$SHARD_DIR/transcript.jsonl" >/dev/null 2>&1; then
        FOUND="$SHARD_DIR"
        TRANSCRIPT_FILE="transcript.jsonl"
    fi
fi

# Slow path: walk metadata files
if [ -z "$FOUND" ]; then
    for metadata in $(git ls-tree -r --name-only "origin/$CHECKPOINT_BRANCH" 2>/dev/null | grep "metadata.json"); do
        CONTENT="$(git show "origin/$CHECKPOINT_BRANCH:$metadata" 2>/dev/null || true)"
        if echo "$CONTENT" | grep -q "$SESSION_ID"; then
            CHECKPOINT_DIR="$(dirname "$metadata")"
            # Check for namespaced transcript first, then legacy
            if git show "origin/$CHECKPOINT_BRANCH:$CHECKPOINT_DIR/transcript-${SESSION_ID}.jsonl" >/dev/null 2>&1; then
                FOUND="$CHECKPOINT_DIR"
                TRANSCRIPT_FILE="transcript-${SESSION_ID}.jsonl"
            elif git show "origin/$CHECKPOINT_BRANCH:$CHECKPOINT_DIR/transcript.jsonl" >/dev/null 2>&1; then
                FOUND="$CHECKPOINT_DIR"
                TRANSCRIPT_FILE="transcript.jsonl"
            fi
            break
        fi
    done
fi

if [ -z "$FOUND" ]; then
    echo "Error: session $SESSION_ID not found on checkpoint branch" >&2
    exit 1
fi

echo "Found checkpoint at: $FOUND"

# Extract the transcript
mkdir -p "$TARGET_DIR"
git show "origin/$CHECKPOINT_BRANCH:$FOUND/$TRANSCRIPT_FILE" > "$TARGET_FILE" 2>/dev/null

if [ ! -s "$TARGET_FILE" ]; then
    rm -f "$TARGET_FILE"
    echo "Error: extracted transcript is empty" >&2
    exit 1
fi

SIZE="$(wc -c < "$TARGET_FILE" | tr -d ' ')"
echo "Restored session transcript ($SIZE bytes)"
echo "  From:   $FOUND/$TRANSCRIPT_FILE"
echo "  To:     $TARGET_FILE"
echo ""
echo "To resume: claude --resume $SESSION_ID"
