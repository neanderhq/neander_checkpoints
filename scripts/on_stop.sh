#!/usr/bin/env bash
#
# on_stop.sh — Hook script for Stop event
#
# Receives JSON on stdin from Claude Code hook system.
# Extracts session info and triggers checkpoint.sh.
#
# Usage: on_stop.sh (reads JSON from stdin)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Read hook input from stdin
INPUT="$(cat)"

# Extract fields from JSON
SESSION_ID="$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || echo "")"
TRANSCRIPT_PATH="$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('transcript_path',''))" 2>/dev/null || echo "")"

# Find session file
SESSION_FILE=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    SESSION_FILE="$TRANSCRIPT_PATH"
elif [ -n "$SESSION_ID" ]; then
    PROJECTS_DIR="$HOME/.claude/projects"
    if [ -d "$PROJECTS_DIR" ]; then
        SESSION_FILE="$(find "$PROJECTS_DIR" -name "${SESSION_ID}.jsonl" -type f 2>/dev/null | head -1)"
    fi
fi

if [ -n "$SESSION_FILE" ]; then
    COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"
    "$SCRIPT_DIR/checkpoint.sh" "$SESSION_FILE" "$COMMIT_SHA"
fi
