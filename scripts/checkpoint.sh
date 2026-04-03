#!/usr/bin/env bash
#
# checkpoint.sh — Save current session transcript to a git orphan branch.
#
# Uses git worktree to avoid switching branches in the user's working tree.
# Tracks transcript_offset per session so summaries can be scoped to the
# delta since the last checkpoint.
#
# Usage:
#   checkpoint.sh <session_jsonl_path> [commit_sha]
#   checkpoint.sh --commit <sha> <path1> [path2] ...
#

set -euo pipefail

CHECKPOINT_BRANCH="neander/checkpoints/v1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARSER="$SCRIPT_DIR/parse_jsonl.py"
STATE_FILE=".git/neander-checkpoint-offsets.json"

# Parse args
SESSION_FILES=()
COMMIT_SHA=""
ON_COMMIT=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --commit)
            COMMIT_SHA="$2"
            shift 2
            ;;
        --on-commit)
            ON_COMMIT=true
            shift
            ;;
        *)
            SESSION_FILES+=("$1")
            shift
            ;;
    esac
done

if [ ${#SESSION_FILES[@]} -eq 0 ]; then
    echo "Usage: checkpoint.sh <session_jsonl_path> [commit_sha]" >&2
    exit 1
fi

# Backward compat: if two positional args and second isn't a file, it's commit sha
if [ ${#SESSION_FILES[@]} -ge 2 ] && [ -z "$COMMIT_SHA" ]; then
    LAST_IDX=$(( ${#SESSION_FILES[@]} - 1 ))
    LAST="${SESSION_FILES[$LAST_IDX]}"
    if [ ! -f "$LAST" ]; then
        COMMIT_SHA="$LAST"
        unset "SESSION_FILES[$LAST_IDX]"
    fi
fi

[ -z "$COMMIT_SHA" ] && COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Collect valid session IDs and files
VALID_FILES=()
SESSION_IDS=()
for f in "${SESSION_FILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "Warning: Session file not found, skipping: $f" >&2
        continue
    fi
    VALID_FILES+=("$f")
    SESSION_IDS+=("$(basename "$f" .jsonl)")
done

if [ ${#VALID_FILES[@]} -eq 0 ]; then
    echo "Error: No valid session files provided" >&2
    exit 1
fi

# Read transcript offset for the first session (used for scoping summaries)
# For commit-triggered checkpoints, use commit_offsets so the summary covers
# all work since the previous commit (not just since the last checkpoint).
TRANSCRIPT_OFFSET=0
if [ -f "$STATE_FILE" ]; then
    if [ "$ON_COMMIT" = true ]; then
        OFFSET_KEY="commit_offsets"
    else
        OFFSET_KEY="transcript_offsets"
    fi
    TRANSCRIPT_OFFSET=$(python3 -c "
import json
state = json.load(open('$STATE_FILE'))
print(state.get('$OFFSET_KEY', {}).get('${SESSION_IDS[0]}', 0))
" 2>/dev/null || echo "0")
fi

# Count current transcript lines (this becomes the new offset after checkpoint)
TRANSCRIPT_LINES=$(wc -l < "${VALID_FILES[0]}" 2>/dev/null | tr -d ' ' || echo "0")

# Generate checkpoint ID
CHECKPOINT_INPUT=""
for sid in "${SESSION_IDS[@]}"; do
    CHECKPOINT_INPUT="${CHECKPOINT_INPUT}${sid}"
done
CHECKPOINT_INPUT="${CHECKPOINT_INPUT}${TIMESTAMP}"
CHECKPOINT_ID="$(echo "$CHECKPOINT_INPUT" | shasum -a 256 | cut -c1-16)"

# Shard directory
SHARD_DIR="${CHECKPOINT_ID:0:2}/${CHECKPOINT_ID:2}"

# Collect modified files from all sessions
ALL_FILES_JSON="[]"
for f in "${VALID_FILES[@]}"; do
    stats="$(python3 "$PARSER" stats --session "$f" --json 2>/dev/null || echo '{}')"
    files="$(echo "$stats" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('modified_files',[])))" 2>/dev/null || echo '[]')"
    ALL_FILES_JSON="$(python3 -c "
import json
a = json.loads('$ALL_FILES_JSON')
b = json.loads('$files')
print(json.dumps(sorted(set(a + b))))
")"
done

# Build session IDs JSON
SESSION_IDS_JSON="$(python3 -c "import json; print(json.dumps($(printf '"%s",' "${SESSION_IDS[@]}" | sed 's/,$//' | sed 's/^/[/;s/$/]/')))")"

# Build metadata (includes transcript_offset for scoped summaries)
METADATA="$(python3 -c "
import json
metadata = {
    'id': '$CHECKPOINT_ID',
    'session_ids': $SESSION_IDS_JSON,
    'commit_sha': '$COMMIT_SHA',
    'created_at': '$TIMESTAMP',
    'merged_files': $ALL_FILES_JSON,
    'transcript_offset': $TRANSCRIPT_OFFSET,
    'summary': None
}
print(json.dumps(metadata, indent=2))
")"

# --- Use git worktree to avoid switching branches in the user's working tree ---

WORKTREE_DIR="$(mktemp -d)"

cleanup() {
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null || true
    rm -rf "$WORKTREE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

# Initialize the checkpoint branch if it doesn't exist
if ! git rev-parse --verify "$CHECKPOINT_BRANCH" >/dev/null 2>&1; then
    git worktree add --detach "$WORKTREE_DIR" 2>/dev/null
    cd "$WORKTREE_DIR"
    git checkout --orphan "$CHECKPOINT_BRANCH" --quiet
    git rm -rf . --quiet 2>/dev/null || true
    echo "# Claude Code Session Checkpoints (v1)" > README.md
    git add README.md
    git commit -m "Initialize checkpoint branch" --quiet
    cd - > /dev/null
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null || true
fi

# Add worktree for the checkpoint branch
git worktree add "$WORKTREE_DIR" "$CHECKPOINT_BRANCH" --quiet 2>/dev/null

# Do all work in the worktree
cd "$WORKTREE_DIR"

# Create checkpoint directory
mkdir -p "$SHARD_DIR"

# Copy transcripts — one per session
for i in "${!VALID_FILES[@]}"; do
    f="${VALID_FILES[$i]}"
    sid="${SESSION_IDS[$i]}"
    cp "$f" "$SHARD_DIR/transcript-${sid}.jsonl"
done

# Write metadata
echo "$METADATA" > "$SHARD_DIR/metadata.json"

# Update index
for sid in "${SESSION_IDS[@]}"; do
    echo "$CHECKPOINT_ID|$sid|$COMMIT_SHA|$TIMESTAMP" >> index.log
done

# Commit
git add "$SHARD_DIR" index.log
git commit -m "checkpoint: ${CHECKPOINT_ID} sessions=${#SESSION_IDS[@]} commit=${COMMIT_SHA:0:8}" --quiet

CHECKPOINT_REF="$(git rev-parse HEAD)"

# Go back to original directory
cd - > /dev/null

# Push to remote if one exists
if git remote get-url origin >/dev/null 2>&1; then
    git push origin "$CHECKPOINT_BRANCH" --quiet 2>/dev/null || true
fi

# Advance offsets for next checkpoint
python3 -c "
import json, os
state_file = '$STATE_FILE'
state = {}
if os.path.exists(state_file):
    with open(state_file) as f:
        state = json.load(f)
# Always advance transcript_offsets
offsets = state.get('transcript_offsets', {})
offsets['${SESSION_IDS[0]}'] = $TRANSCRIPT_LINES
state['transcript_offsets'] = offsets
# Advance commit_offsets only on commit-triggered checkpoints
if '$ON_COMMIT' == 'true':
    commit_offsets = state.get('commit_offsets', {})
    commit_offsets['${SESSION_IDS[0]}'] = $TRANSCRIPT_LINES
    state['commit_offsets'] = commit_offsets
with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)
    f.write('\n')
" 2>/dev/null || true

echo "Checkpoint created: $CHECKPOINT_ID"
echo "  Sessions: ${SESSION_IDS[*]}"
echo "  Commit:   $COMMIT_SHA"
echo "  Branch:   $CHECKPOINT_BRANCH"
echo "  Ref:      $CHECKPOINT_REF"
echo "  Transcript offset: $TRANSCRIPT_OFFSET → $TRANSCRIPT_LINES"

# Auto-summarize on commit-triggered checkpoints only.
# Stop checkpoints skip summarization because the topic would describe
# uncommitted WIP, creating a misleading association with the commit SHA.
if [ "$ON_COMMIT" = true ]; then
    CONFIG=".claude/neander-checkpoints.json"
    AUTO_SUMMARIZE="True"
    if [ -f "$CONFIG" ]; then
        AUTO_SUMMARIZE=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('auto_summarize', True))" 2>/dev/null || echo "True")
    fi
    if [ "$AUTO_SUMMARIZE" = "True" ]; then
        echo "  Auto-summarizing..."
        "$SCRIPT_DIR/auto_summarize.sh" "$CHECKPOINT_ID" "${VALID_FILES[0]}" "$TRANSCRIPT_OFFSET" &
    fi
fi
