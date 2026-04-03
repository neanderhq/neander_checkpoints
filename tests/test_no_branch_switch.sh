#!/usr/bin/env bash
#
# test_no_branch_switch.sh — Guard against scripts switching branches in the user's working tree.
#
# This is a regression test for a recurring bug: scripts that `git checkout`
# to the checkpoint branch cause Claude Code to lose its .claude/ config
# (skills, agents, hooks all vanish).
#
# The test scans ALL shell scripts for dangerous `git checkout` patterns.
# Any script that needs to write to the checkpoint branch MUST use
# `git worktree` instead.
#
# Usage: bash tests/test_no_branch_switch.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"
PASS=0
FAIL=0

pass() {
    echo "  PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "  FAIL: $1"
    FAIL=$((FAIL + 1))
}

echo "=== No branch switching in user's working tree ==="

# --- Static analysis: scan for dangerous git checkout patterns ---

# Pattern: `git checkout "$CHECKPOINT_BRANCH"` or `git checkout neander/checkpoints`
# outside of a worktree context (i.e., not inside a `cd "$WORKTREE_DIR"` block).
#
# Allowed:
#   - `git checkout --orphan` inside a worktree (one-time branch init)
#   - `git worktree add ... "$CHECKPOINT_BRANCH"` (correct pattern)
#
# Forbidden:
#   - `git checkout "$CHECKPOINT_BRANCH"` (switches user's working tree)
#   - `git checkout "$ORIGINAL_BRANCH"` (implies a prior forbidden checkout)
#   - `git stash push` paired with checkout (implies branch-switch-and-restore)

VIOLATIONS=0

for script in "$SCRIPT_DIR"/*.sh; do
    name="$(basename "$script")"

    # Check for `git checkout` to the checkpoint branch (not --orphan, not in worktree init)
    if grep -n 'git checkout' "$script" | grep -v '\-\-orphan' | grep -qiE 'CHECKPOINT_BRANCH|neander.checkpoints'; then
        echo "    $name: git checkout to checkpoint branch (use git worktree instead)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi

    # Check for stash-checkout-restore pattern (sign of branch switching)
    if grep -q 'git stash push' "$script" && grep -q 'git checkout.*ORIGINAL_BRANCH\|git checkout.*--quiet' "$script"; then
        echo "    $name: stash+checkout pattern detected (use git worktree instead)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi

    # Check for saving/restoring ORIGINAL_BRANCH (implies checkout-based approach)
    if grep -q 'ORIGINAL_BRANCH' "$script"; then
        echo "    $name: ORIGINAL_BRANCH variable detected (use git worktree instead)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

if [ "$VIOLATIONS" -eq 0 ]; then
    pass "no scripts checkout to checkpoint branch in user's working tree"
else
    fail "$VIOLATIONS violation(s) found — scripts must use git worktree, not git checkout"
fi

# --- Verify worktree cleanup: scripts that create worktrees must have cleanup traps ---

for script in "$SCRIPT_DIR"/*.sh; do
    name="$(basename "$script")"
    if grep -q 'git worktree add' "$script"; then
        if grep -q 'git worktree remove' "$script"; then
            pass "$name: worktree add has matching cleanup"
        else
            fail "$name: creates worktree but never removes it"
        fi
    fi
done

# --- Integration: verify branch doesn't change during checkpoint+save flow ---

echo ""
echo "--- Integration: branch stability during checkpoint+save ---"

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

CHECKPOINT_BRANCH="neander/checkpoints/v1"

ORIGINAL_BRANCH="$(git symbolic-ref --short HEAD)"

# Create a .claude dir with a marker file (simulates skills/agents)
mkdir -p .claude/skills .claude/agents
echo "marker" > .claude/skills/test-skill.md
echo "marker" > .claude/agents/test-agent.md

# Create a transcript
TRANSCRIPT="$TMPDIR_ROOT/test-session.jsonl"
echo '{"type":"user","message":{"role":"user","content":"hello"},"timestamp":"2026-04-01T10:00:00.000Z"}' > "$TRANSCRIPT"

# Run checkpoint (creates the checkpoint branch + checkpoint)
bash "$SCRIPT_DIR/checkpoint.sh" --on-commit "$TRANSCRIPT" --commit abc123 2>&1 >/dev/null

# Verify branch didn't change
CURRENT="$(git symbolic-ref --short HEAD)"
assert_branch() {
    if [ "$1" = "$2" ]; then
        pass "$3"
    else
        fail "$3 (expected $1, got $2)"
    fi
}
assert_branch "$ORIGINAL_BRANCH" "$CURRENT" "branch unchanged after checkpoint"

# Verify .claude files still exist
if [ -f .claude/skills/test-skill.md ] && [ -f .claude/agents/test-agent.md ]; then
    pass ".claude/ directory intact after checkpoint"
else
    fail ".claude/ directory was disturbed by checkpoint"
fi

# Now test save_summary.sh
echo '{"intent":"test","outcome":"ok"}' > "$TMPDIR_ROOT/summary.json"
CHECKPOINT_ID="$(git log "$CHECKPOINT_BRANCH" --oneline -1 | grep -oE '[a-f0-9]{16}' | head -1 || true)"

if [ -n "$CHECKPOINT_ID" ]; then
    # Get checkpoint ID from index
    CHECKPOINT_ID="$(git show "$CHECKPOINT_BRANCH:index.log" | tail -1 | cut -d'|' -f1)"
    bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" "$TMPDIR_ROOT/summary.json" 2>&1 >/dev/null

    CURRENT="$(git symbolic-ref --short HEAD)"
    assert_branch "$ORIGINAL_BRANCH" "$CURRENT" "branch unchanged after save_summary"

    if [ -f .claude/skills/test-skill.md ] && [ -f .claude/agents/test-agent.md ]; then
        pass ".claude/ directory intact after save_summary"
    else
        fail ".claude/ directory was disturbed by save_summary"
    fi
fi

# Monitor branch during a background save (race condition test)
# Run save_summary in background and poll branch every 0.1s
if [ -n "$CHECKPOINT_ID" ]; then
    echo '{"intent":"bg test","outcome":"ok"}' > "$TMPDIR_ROOT/summary2.json"
    bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" "$TMPDIR_ROOT/summary2.json" 2>/dev/null &
    BG_PID=$!

    BRANCH_CHANGED=false
    for i in $(seq 1 20); do
        CURRENT="$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")"
        if [ "$CURRENT" != "$ORIGINAL_BRANCH" ]; then
            BRANCH_CHANGED=true
            break
        fi
        sleep 0.1
    done
    wait $BG_PID 2>/dev/null || true

    if [ "$BRANCH_CHANGED" = true ]; then
        fail "branch changed during background save_summary"
    else
        pass "branch stable during background save_summary"
    fi
fi

# --- Summary ---

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
