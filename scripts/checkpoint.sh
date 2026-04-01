#!/usr/bin/env bash
#
# checkpoint.sh — Save current session transcript to a git orphan branch.
#
# Creates/updates a neander/checkpoints/v1 orphan branch with session
# transcripts and metadata. Supports multiple sessions per checkpoint.
#
# Usage:
#   checkpoint.sh <session_jsonl_path> [commit_sha]
#   checkpoint.sh --commit <sha> <path1> [path2] ...
#

set -euo pipefail

CHECKPOINT_BRANCH="neander/checkpoints/v1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARSER="$SCRIPT_DIR/parse_jsonl.py"

# Parse args
SESSION_FILES=()
COMMIT_SHA=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --commit)
            COMMIT_SHA="$2"
            shift 2
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

# Build metadata
METADATA="$(python3 -c "
import json
metadata = {
    'id': '$CHECKPOINT_ID',
    'session_ids': $SESSION_IDS_JSON,
    'commit_sha': '$COMMIT_SHA',
    'created_at': '$TIMESTAMP',
    'merged_files': $ALL_FILES_JSON,
    'summary': None
}
print(json.dumps(metadata, indent=2))
")"

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
    echo "# Claude Code Session Checkpoints (v1)" > README.md
    git add README.md
    git commit -m "Initialize checkpoint branch" --quiet
else
    git checkout "$CHECKPOINT_BRANCH" --quiet
fi

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

# Push to remote if one exists
if git remote get-url origin >/dev/null 2>&1; then
    git push origin "$CHECKPOINT_BRANCH" --quiet 2>/dev/null || true
fi

echo "Checkpoint created: $CHECKPOINT_ID"
echo "  Sessions: ${SESSION_IDS[*]}"
echo "  Commit:   $COMMIT_SHA"
echo "  Branch:   $CHECKPOINT_BRANCH"
echo "  Ref:      $CHECKPOINT_REF"

# Auto-summarize if enabled
CONFIG=".claude/neander-checkpoints.json"
if [ -f "$CONFIG" ]; then
    AUTO_SUMMARIZE=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('auto_summarize', False))" 2>/dev/null || echo "False")
    if [ "$AUTO_SUMMARIZE" = "True" ]; then
        echo "  Auto-summarizing..."
        "$SCRIPT_DIR/auto_summarize.sh" "$CHECKPOINT_ID" "${VALID_FILES[0]}" &
    fi
fi
