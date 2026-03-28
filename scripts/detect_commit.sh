#!/usr/bin/env bash
#
# detect_commit.sh — Hook script for PostToolUse:Bash
#
# Receives JSON on stdin from Claude Code hook system.
# Checks if the Bash command was a git commit.
# If so, triggers:
#   1. link_commit.sh — add Claude-Session trailer to the commit
#   2. checkpoint.sh  — snapshot the session transcript at this commit
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

# Check if the command looks like a git commit
if echo "$COMMAND" | grep -qE "git commit"; then
    if [ -n "$SESSION_ID" ]; then
        # Link the commit to this session
        "$SCRIPT_DIR/link_commit.sh" "$SESSION_ID"

        # Find the session JSONL and checkpoint it at this commit
        COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"

        # Try transcript_path from hook input first, then search
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
    fi
fi
