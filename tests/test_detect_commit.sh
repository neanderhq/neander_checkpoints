#!/usr/bin/env bash
#
# test_detect_commit.sh — Tests for detect_commit.sh hook filtering
#
# Verifies that detect_commit.sh correctly identifies real user commits
# and ignores internal operations (checkpoint commits, amend from link_commit, etc.)
#
# Usage: bash tests/test_detect_commit.sh
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

# detect_commit.sh reads JSON from stdin and checks the command field.
# We test the filtering logic by feeding it various inputs and checking
# whether it would proceed (exit 0 means skip, non-zero or further execution means trigger).
#
# Since detect_commit.sh calls link_commit.sh and checkpoint.sh, we mock those
# to just record that they were called.

TMPDIR_ROOT="$(mktemp -d)"
REPO_DIR="$TMPDIR_ROOT/repo"

cleanup() {
    cd /
    rm -rf "$TMPDIR_ROOT"
}
trap cleanup EXIT

git init "$REPO_DIR" --quiet
cd "$REPO_DIR"
git commit --allow-empty -m "init" --quiet

# Create mock scripts that record calls
MOCK_DIR="$TMPDIR_ROOT/mock_scripts"
mkdir -p "$MOCK_DIR"

# Copy detect_commit.sh and patch SCRIPT_DIR to use mocks
MOCK_DETECT="$MOCK_DIR/detect_commit.sh"
sed "s|SCRIPT_DIR=.*|SCRIPT_DIR=\"$MOCK_DIR\"|" "$SCRIPT_DIR/detect_commit.sh" > "$MOCK_DETECT"
chmod +x "$MOCK_DETECT"

cat > "$MOCK_DIR/link_commit.sh" << 'SCRIPT'
#!/usr/bin/env bash
echo "LINK_CALLED"
SCRIPT
chmod +x "$MOCK_DIR/link_commit.sh"

cat > "$MOCK_DIR/checkpoint.sh" << 'SCRIPT'
#!/usr/bin/env bash
echo "CHECKPOINT_CALLED"
SCRIPT
chmod +x "$MOCK_DIR/checkpoint.sh"

# Create a fake transcript
TRANSCRIPT="$TMPDIR_ROOT/test-session.jsonl"
echo '{"type":"user","message":{"role":"user","content":"hi"}}' > "$TRANSCRIPT"

TEST_SEQ=0
run_detect() {
    local command="$1"
    local session_id="${2-test-session-id}"
    TEST_SEQ=$((TEST_SEQ + 1))
    local log_file="/tmp/test-detect-calls-${TEST_SEQ}.log"
    rm -f "$log_file"
    # Patch mock scripts to write to this unique log file
    cat > "$MOCK_DIR/link_commit.sh" << SCRIPT
#!/usr/bin/env bash
echo "LINK_CALLED" >> "$log_file"
SCRIPT
    cat > "$MOCK_DIR/checkpoint.sh" << SCRIPT
#!/usr/bin/env bash
echo "CHECKPOINT_CALLED" >> "$log_file"
SCRIPT
    python3 -c "
import json, sys
d = {'tool_input': {'command': sys.argv[1]}, 'session_id': sys.argv[2], 'transcript_path': sys.argv[3]}
print(json.dumps(d))
" "$command" "$session_id" "$TRANSCRIPT" | bash "$MOCK_DETECT" 2>/dev/null || true
    # Wait for any background processes spawned by detect_commit
    wait 2>/dev/null || true
    if [ -f "$log_file" ]; then
        cat "$log_file"
    fi
    rm -f "$log_file"
}

echo "=== detect_commit.sh filtering tests ==="

# --- Test 1: Triggers on normal git commit ---
OUTPUT="$(run_detect 'git commit -m "fix bug"')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && pass "triggers on git commit" || fail "should trigger on git commit"

# --- Test 2: Does NOT trigger on non-commit commands ---
OUTPUT="$(run_detect 'git status')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "should not trigger on git status" || pass "ignores git status"

OUTPUT="$(run_detect 'git push origin main')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "should not trigger on git push" || pass "ignores git push"

OUTPUT="$(run_detect 'git log --oneline')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "should not trigger on git log" || pass "ignores git log"

# --- Test 3: Does NOT trigger on checkpoint internal commands ---
OUTPUT="$(run_detect 'bash checkpoint.sh /tmp/session.jsonl')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "should not trigger on checkpoint.sh" || pass "ignores checkpoint.sh commands"

OUTPUT="$(run_detect 'bash save_summary.sh abc123')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "should not trigger on save_summary.sh" || pass "ignores save_summary.sh commands"

OUTPUT="$(run_detect 'bash persist_summary.sh abc123')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "should not trigger on persist_summary.sh" || pass "ignores persist_summary.sh commands"

# --- Test 4: Does NOT trigger without session ID ---
OUTPUT="$(run_detect 'git commit -m "no session"' '')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "should not trigger without session_id" || pass "ignores empty session_id"

# --- Test 5: Triggers on git commit --amend (from user) ---
rm -f "$REPO_DIR/.git/neander-last-checkpoint-sha"
OUTPUT="$(run_detect 'git commit --amend -m "updated msg"')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && pass "triggers on user git commit --amend" || fail "should trigger on git commit --amend"

# --- Test 6: Triggers on compound commands containing git commit ---
rm -f "$REPO_DIR/.git/neander-last-checkpoint-sha"
OUTPUT="$(run_detect 'git add . && git commit -m "msg"')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && pass "triggers on compound git add && git commit" || fail "should trigger on compound command"

# --- Test 7: Does NOT trigger twice for the same commit (dedup) ---
# First call should trigger (fresh state, no last-sha file)
rm -f "$REPO_DIR/.git/neander-last-checkpoint-sha"
OUTPUT="$(run_detect 'git commit -m "first"')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && pass "first commit triggers" || fail "first commit should trigger"

# Second call with same HEAD should be skipped
OUTPUT="$(run_detect 'git commit -m "duplicate"')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && fail "duplicate commit should not trigger" || pass "skips duplicate commit at same HEAD"

# After a new commit (different HEAD), should trigger again
git commit --allow-empty -m "new commit" --quiet
OUTPUT="$(run_detect 'git commit -m "second"')"
echo "$OUTPUT" | grep -q "LINK_CALLED" && pass "new commit after HEAD change triggers" || fail "should trigger after HEAD change"

# --- Summary ---

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
