#!/usr/bin/env bash
#
# test_checkpoint.sh — Integration tests for checkpoint.sh
#
# Tests checkpoint creation in a temporary git repo, verifying:
# - Worktree-based operation (no branch switching in user's working tree)
# - Metadata correctness (transcript_offset, summary field)
# - Offset state file advancement
#
# Usage: bash tests/test_checkpoint.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"
PASS=0
FAIL=0

fail() {
    echo "  FAIL: $1"
    FAIL=$((FAIL + 1))
}

pass() {
    echo "  PASS: $1"
    PASS=$((PASS + 1))
}

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        pass "$desc"
    else
        fail "$desc"
        echo "    expected: $expected"
        echo "    actual:   $actual"
    fi
}

# --- Setup ---

TMPDIR_ROOT="$(mktemp -d)"
REPO_DIR="$TMPDIR_ROOT/repo"

cleanup() {
    cd /
    rm -rf "$TMPDIR_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

git init "$REPO_DIR" --quiet
cd "$REPO_DIR"
git commit --allow-empty -m "init" --quiet

# Create a transcript file
TRANSCRIPT="$TMPDIR_ROOT/test-session-id.jsonl"
for i in $(seq 1 10); do
    echo '{"type":"user","message":{"role":"user","content":"msg '$i'"},"timestamp":"2026-04-01T10:00:0'$i'.000Z"}' >> "$TRANSCRIPT"
done

echo "=== checkpoint.sh integration tests ==="

# --- Test 1: Creates checkpoint without switching branches ---

ORIGINAL_BRANCH="$(git symbolic-ref --short HEAD)"
bash "$SCRIPT_DIR/checkpoint.sh" "$TRANSCRIPT" --commit abc123 2>&1

CURRENT_BRANCH="$(git symbolic-ref --short HEAD)"
assert_eq "stays on original branch after checkpoint" "$ORIGINAL_BRANCH" "$CURRENT_BRANCH"

# Verify checkpoint was created on the checkpoint branch
CHECKPOINT_BRANCH="neander/checkpoints/v1"
INDEX_LINE="$(git show "$CHECKPOINT_BRANCH:index.log" 2>/dev/null | tail -1)"
CHECKPOINT_ID="$(echo "$INDEX_LINE" | cut -d'|' -f1)"
assert_eq "checkpoint ID is 16 hex chars" "16" "$(echo -n "$CHECKPOINT_ID" | wc -c | tr -d ' ')"

# --- Test 2: Metadata has correct fields ---

SHARD_DIR="${CHECKPOINT_ID:0:2}/${CHECKPOINT_ID:2}"
METADATA="$(git show "$CHECKPOINT_BRANCH:$SHARD_DIR/metadata.json" 2>/dev/null)"

COMMIT="$(echo "$METADATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['commit_sha'])")"
assert_eq "metadata has correct commit_sha" "abc123" "$COMMIT"

SUMMARY="$(echo "$METADATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['summary'])")"
assert_eq "metadata summary starts as null" "None" "$SUMMARY"

OFFSET="$(echo "$METADATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['transcript_offset'])")"
assert_eq "first checkpoint has offset 0" "0" "$OFFSET"

# --- Test 3: Offset advances on second checkpoint ---

# Add more lines to transcript
for i in $(seq 11 15); do
    echo '{"type":"user","message":{"role":"user","content":"msg '$i'"},"timestamp":"2026-04-01T10:01:0'$i'.000Z"}' >> "$TRANSCRIPT"
done

sleep 1  # ensure different timestamp for unique checkpoint ID
bash "$SCRIPT_DIR/checkpoint.sh" "$TRANSCRIPT" --commit def456 2>&1

# Get the second checkpoint
INDEX_LINE2="$(git show "$CHECKPOINT_BRANCH:index.log" 2>/dev/null | tail -1)"
CHECKPOINT_ID2="$(echo "$INDEX_LINE2" | cut -d'|' -f1)"
SHARD_DIR2="${CHECKPOINT_ID2:0:2}/${CHECKPOINT_ID2:2}"
METADATA2="$(git show "$CHECKPOINT_BRANCH:$SHARD_DIR2/metadata.json" 2>/dev/null)"

OFFSET2="$(echo "$METADATA2" | python3 -c "import json,sys; print(json.load(sys.stdin)['transcript_offset'])")"
assert_eq "second checkpoint offset is 10 (first transcript length)" "10" "$OFFSET2"

# --- Test 4: No worktrees left behind ---

WORKTREE_COUNT="$(git worktree list | wc -l | tr -d ' ')"
assert_eq "no extra worktrees left" "1" "$WORKTREE_COUNT"

# --- Test 5: User's working tree files are untouched ---

echo "user work in progress" > "$REPO_DIR/wip.txt"
git add wip.txt

sleep 1
bash "$SCRIPT_DIR/checkpoint.sh" "$TRANSCRIPT" --commit ghi789 2>&1

if [ -f "$REPO_DIR/wip.txt" ] && git diff --cached --name-only | grep -q "wip.txt"; then
    pass "user's staged files preserved"
else
    fail "user's staged files were lost"
fi

# --- Test 6: Auto-summarize runs by default even without config file ---

# Capture checkpoint output — should say "Auto-summarizing..." even with no config
OUTPUT="$(sleep 1 && bash "$SCRIPT_DIR/checkpoint.sh" "$TRANSCRIPT" --commit jkl012 2>&1)"
echo "$OUTPUT" | grep -q "Auto-summarizing" && pass "auto-summarize triggers without config file" || fail "auto-summarize should trigger by default without config file"

# --- Test 7: Auto-summarize respects config when present ---

mkdir -p .claude
echo '{"auto_summarize": false}' > .claude/neander-checkpoints.json
OUTPUT="$(sleep 1 && bash "$SCRIPT_DIR/checkpoint.sh" "$TRANSCRIPT" --commit mno345 2>&1)"
echo "$OUTPUT" | grep -q "Auto-summarizing" && fail "auto-summarize should be disabled by config" || pass "auto-summarize respects config auto_summarize=false"
rm -rf .claude

# --- Summary ---

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
