#!/usr/bin/env bash
#
# detect_commit.sh — Hook script for PostToolUse:Bash
#
# Checks if the Bash tool output contains evidence of a git commit.
# If so, triggers:
#   1. link_commit.sh — add Claude-Session trailer to the commit
#   2. checkpoint.sh  — snapshot the session transcript at this commit
#
# Called with: the tool output is piped to stdin or passed as env vars
# by the Claude Code hook system.
#
# Usage: detect_commit.sh <session_id>
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION_ID="${1:-}"

# The hook receives tool info via environment variables
# TOOL_INPUT contains the bash command that was run
COMMAND="${TOOL_INPUT:-}"

# Check if the command looks like a git commit
if echo "$COMMAND" | grep -qE "git commit"; then
    if [ -n "$SESSION_ID" ]; then
        # Link the commit to this session
        "$SCRIPT_DIR/link_commit.sh" "$SESSION_ID"

        # Find the session JSONL and checkpoint it at this commit
        COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo 'none')"
        PROJECTS_DIR="$HOME/.claude/projects"
        if [ -d "$PROJECTS_DIR" ]; then
            SESSION_FILE="$(find "$PROJECTS_DIR" -name "${SESSION_ID}.jsonl" -type f 2>/dev/null | head -1)"
            if [ -n "$SESSION_FILE" ]; then
                "$SCRIPT_DIR/checkpoint.sh" "$SESSION_FILE" "$COMMIT_SHA" &
            fi
        fi
    fi
fi
