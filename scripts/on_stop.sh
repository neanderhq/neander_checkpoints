#!/usr/bin/env bash
#
# on_stop.sh — Hook script for Stop event
#
# Receives JSON on stdin from Claude Code hook system.
# Only creates a checkpoint if the session actually modified files
# (i.e., used Write/Edit tools). Skips read-only sessions like
# running /neander-summarize or asking questions.
#
# Usage: on_stop.sh (reads JSON from stdin)
#

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARSER="$SCRIPT_DIR/parse_jsonl.py"

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

[ -z "$SESSION_FILE" ] && exit 0

# Only checkpoint if the session modified files
FILE_COUNT="$(python3 "$PARSER" files --session "$SESSION_FILE" 2>/dev/null | wc -l | tr -d ' ')"
if [ "$FILE_COUNT" -eq 0 ]; then
    exit 0
fi

COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"
"$SCRIPT_DIR/checkpoint.sh" "$SESSION_FILE" "$COMMIT_SHA" &
