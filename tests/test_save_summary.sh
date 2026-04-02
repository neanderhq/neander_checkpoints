#!/usr/bin/env bash
#
# test_save_summary.sh — Integration tests for save_summary.sh
#
# Creates a temporary git repo with a checkpoint branch, then tests
# that save_summary.sh correctly persists summaries into metadata.
#
# Usage: bash tests/test_save_summary.sh
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

# --- Setup: create a temp git repo with a checkpoint branch ---

TMPDIR_ROOT="$(mktemp -d)"
REPO_DIR="$TMPDIR_ROOT/repo"

cleanup() {
    cd /
    rm -rf "$TMPDIR_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

# Create main repo
git init "$REPO_DIR" --quiet
cd "$REPO_DIR"
git commit --allow-empty -m "init" --quiet

# Create checkpoint branch with a test checkpoint
CHECKPOINT_BRANCH="neander/checkpoints/v1"
git checkout --orphan "$CHECKPOINT_BRANCH" --quiet
git rm -rf . --quiet 2>/dev/null || true

CHECKPOINT_ID="abcdef0123456789"
SHARD_DIR="${CHECKPOINT_ID:0:2}/${CHECKPOINT_ID:2}"
mkdir -p "$SHARD_DIR"

# Write metadata with null summary
python3 -c "
import json
metadata = {
    'id': '$CHECKPOINT_ID',
    'session_ids': ['test-session-uuid-1234'],
    'commit_sha': 'abc123',
    'created_at': '2026-04-01T10:00:00Z',
    'merged_files': [],
    'transcript_offset': 0,
    'summary': None
}
with open('$SHARD_DIR/metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)
"

# Write index
echo "$CHECKPOINT_ID|test-session-uuid-1234|abc123|2026-04-01T10:00:00Z" > index.log

git add .
git commit -m "test checkpoint" --quiet

# Switch back to main
git checkout master --quiet 2>/dev/null || git checkout main --quiet 2>/dev/null

echo "=== save_summary.sh integration tests ==="

# --- Test 1: Save summary by checkpoint ID ---

SUMMARY='{"intent":"Fixed bug","outcome":"Tests pass"}'
echo "$SUMMARY" > "$TMPDIR_ROOT/summary.json"
bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" "$TMPDIR_ROOT/summary.json" 2>&1

# Verify it was saved
SAVED="$(git show "$CHECKPOINT_BRANCH:$SHARD_DIR/metadata.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['summary']))" 2>/dev/null)"
EXPECTED='{"intent": "Fixed bug", "outcome": "Tests pass"}'
assert_eq "saves summary by checkpoint ID" "$EXPECTED" "$SAVED"

# --- Test 2: Save summary by session ID ---

SUMMARY2='{"intent":"Updated","outcome":"v2"}'
echo "$SUMMARY2" > "$TMPDIR_ROOT/summary2.json"
bash "$SCRIPT_DIR/save_summary.sh" "test-session-uuid-1234" "$TMPDIR_ROOT/summary2.json" 2>&1

SAVED="$(git show "$CHECKPOINT_BRANCH:$SHARD_DIR/metadata.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['summary']['intent'])" 2>/dev/null)"
assert_eq "saves summary by session ID" "Updated" "$SAVED"

# --- Test 3: Rejects invalid JSON ---

echo "not json" > "$TMPDIR_ROOT/bad.json"
OUTPUT="$(bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" "$TMPDIR_ROOT/bad.json" 2>&1 || true)"
echo "$OUTPUT" | grep -q "Invalid JSON" && pass "rejects invalid JSON" || fail "should reject invalid JSON"

# --- Test 4: Fails gracefully for missing checkpoint ---

OUTPUT="$(bash "$SCRIPT_DIR/save_summary.sh" "0000000000000000" "$TMPDIR_ROOT/summary.json" 2>&1 || true)"
echo "$OUTPUT" | grep -q "metadata not found\|not found" && pass "fails for missing checkpoint" || fail "should fail for missing checkpoint"

# --- Test 5: Save via stdin ---

echo '{"intent":"From stdin","outcome":"piped"}' | bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" - 2>&1

SAVED="$(git show "$CHECKPOINT_BRANCH:$SHARD_DIR/metadata.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['summary']['intent'])" 2>/dev/null)"
assert_eq "saves summary from stdin" "From stdin" "$SAVED"

# --- Test 6: Working tree is not disturbed ---

# Create a file in the working tree and verify it's still there after save
echo "important work" > "$REPO_DIR/my-work.txt"
git add my-work.txt
# Don't commit — leave it staged

echo '{"intent":"No disruption","outcome":"clean"}' > "$TMPDIR_ROOT/summary3.json"
bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" "$TMPDIR_ROOT/summary3.json" 2>&1

# Verify we're back on the original branch (not on checkpoint branch)
CURRENT="$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")"
echo "$CURRENT" | grep -qv "neander/checkpoints" && pass "returns to original branch" || fail "stuck on checkpoint branch: $CURRENT"

# Verify the staged file is still there
if git diff --cached --name-only | grep -q "my-work.txt"; then
    pass "staged files preserved after save"
else
    fail "staged files lost after save"
fi

# --- Summary ---

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
