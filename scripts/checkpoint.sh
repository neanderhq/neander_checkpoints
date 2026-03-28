#!/usr/bin/env bash
#
# checkpoint.sh — Save current session transcript to a git orphan branch.
#
# Called by the Stop hook or manually. Creates/updates an orphan branch
# (neander/checkpoints/v1) with session transcripts and metadata.
#
# Supports multiple sessions per checkpoint — each transcript is stored as
# transcript-<session_id>.jsonl so concurrent sessions on the same commit
# don't overwrite each other.
#
# Usage: checkpoint.sh <session_jsonl_path> [commit_sha]
#        checkpoint.sh <path1> <path2> ... [--commit <sha>]
#

set -euo pipefail

CHECKPOINT_BRANCH="neander/checkpoints/v1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARSER="$SCRIPT_DIR/parse_jsonl.py"

# Parse args: support multiple session files + optional --commit flag
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

# Backward compat: first positional arg is session file, second is commit sha
if [ ${#SESSION_FILES[@]} -eq 0 ]; then
    echo "Usage: checkpoint.sh <session_jsonl_path> [commit_sha]" >&2
    exit 1
fi

if [ ${#SESSION_FILES[@]} -ge 2 ] && [ -z "$COMMIT_SHA" ]; then
    # Legacy: second arg might be commit sha (not a file)
    LAST="${SESSION_FILES[-1]}"
    if [ ! -f "$LAST" ]; then
        COMMIT_SHA="$LAST"
        unset 'SESSION_FILES[-1]'
    fi
fi

[ -z "$COMMIT_SHA" ] && COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Collect session IDs
SESSION_IDS=()
for f in "${SESSION_FILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "Warning: Session file not found, skipping: $f" >&2
        continue
    fi
    SESSION_IDS+=("$(basename "$f" .jsonl)")
done

if [ ${#SESSION_IDS[@]} -eq 0 ]; then
    echo "Error: No valid session files provided" >&2
    exit 1
fi

# Generate checkpoint ID from all session IDs + timestamp
CHECKPOINT_INPUT="$(printf "%s" "${SESSION_IDS[@]}")${TIMESTAMP}"
CHECKPOINT_ID="$(echo "$CHECKPOINT_INPUT" | shasum -a 256 | cut -c1-16)"

# Shard directory: first 2 chars / rest
SHARD_DIR="${CHECKPOINT_ID:0:2}/${CHECKPOINT_ID:2}"

# Collect stats and build file list
ALL_FILES=()
SESSION_STATS=()
for i in "${!SESSION_FILES[@]}"; do
    f="${SESSION_FILES[$i]}"
    sid="${SESSION_IDS[$i]}"
    stats="$(python3 "$PARSER" stats --session "$f" --json 2>/dev/null || echo '{}')"
    SESSION_STATS+=("$stats")
    # Extract modified files from stats
    files="$(echo "$stats" | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f) for f in d.get('modified_files',[])]" 2>/dev/null || true)"
    while IFS= read -r file; do
        [ -n "$file" ] && ALL_FILES+=("$file")
    done <<< "$files"
done

# Deduplicate files
MERGED_FILES="$(printf '%s\n' "${ALL_FILES[@]}" | sort -u | python3 -c "import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")"

# Build session_ids JSON array
SESSION_IDS_JSON="$(printf '%s\n' "${SESSION_IDS[@]}" | python3 -c "import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")"

# Build metadata
METADATA="$(python3 -c "
import json, sys

metadata = {
    'id': '$CHECKPOINT_ID',
    'session_ids': $SESSION_IDS_JSON,
    'commit_sha': '$COMMIT_SHA',
    'created_at': '$TIMESTAMP',
    'merged_files': $MERGED_FILES,
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

# Copy transcripts — one per session, namespaced
for i in "${!SESSION_FILES[@]}"; do
    f="${SESSION_FILES[$i]}"
    sid="${SESSION_IDS[$i]}"
    cp "$f" "$SHARD_DIR/transcript-${sid}.jsonl"
done

# Write metadata
echo "$METADATA" > "$SHARD_DIR/metadata.json"

# Update index
for sid in "${SESSION_IDS[@]}"; do
    INDEX_ENTRY="$CHECKPOINT_ID|$sid|$COMMIT_SHA|$TIMESTAMP"
    echo "$INDEX_ENTRY" >> index.log
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
