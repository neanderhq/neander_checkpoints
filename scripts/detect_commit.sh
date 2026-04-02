#!/usr/bin/env bash
#
# detect_commit.sh — Hook script for PostToolUse:Bash
#
# Receives JSON on stdin from Claude Code hook system.
# Checks if the Bash command was a git commit on a user branch
# (not our checkpoint branch or internal scripts).
# If so, triggers checkpoint.sh and link_commit.sh.
#
# Usage: detect_commit.sh (reads JSON from stdin)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Read hook input from stdin
INPUT="$(cat)"

# Extract fields from JSON
COMMAND="$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")"
SESSION_ID="$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || echo "")"
TRANSCRIPT_PATH="$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('transcript_path',''))" 2>/dev/null || echo "")"

# Only trigger on user git commits, not our internal scripts
# Skip if:
#   - command doesn't contain "git commit"
#   - command is from checkpoint.sh, save_summary.sh, or link_commit.sh
#   - current branch is the checkpoint branch
echo "$COMMAND" | grep -qE "git commit" || exit 0
echo "$COMMAND" | grep -qE "checkpoint|save_summary|persist_summary" && exit 0
[ -z "$SESSION_ID" ] && exit 0

CURRENT_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo "")"
echo "$CURRENT_BRANCH" | grep -q "neander/checkpoints" && exit 0

# Only trigger on NEW commits — skip if HEAD hasn't changed since last checkpoint
COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"
LAST_SHA_FILE=".git/neander-last-checkpoint-sha"
if [ -f "$LAST_SHA_FILE" ] && [ "$(cat "$LAST_SHA_FILE")" = "$COMMIT_SHA" ]; then
    exit 0
fi

# Link the commit to this session (amends commit, changes SHA)
"$SCRIPT_DIR/link_commit.sh" "$SESSION_ID"

# Re-read HEAD after amend and record it to prevent duplicate checkpoints
COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"
echo "$COMMIT_SHA" > "$LAST_SHA_FILE"

SESSION_FILE=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    SESSION_FILE="$TRANSCRIPT_PATH"
else
    PROJECTS_DIR="$HOME/.claude/projects"
    if [ -d "$PROJECTS_DIR" ]; then
        SESSION_FILE="$(find "$PROJECTS_DIR" -name "${SESSION_ID}.jsonl" -type f 2>/dev/null | head -1)"
    fi
fi

if [ -n "$SESSION_FILE" ]; then
    "$SCRIPT_DIR/checkpoint.sh" "$SESSION_FILE" "$COMMIT_SHA" &
fi
