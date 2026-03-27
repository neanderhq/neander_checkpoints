#!/usr/bin/env bash
#
# detect_commit.sh — Hook script for PostToolUse:Bash
#
# Checks if the Bash tool output contains evidence of a git commit.
# If so, triggers link_commit.sh to add session trailer.
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
        "$SCRIPT_DIR/link_commit.sh" "$SESSION_ID"
    fi
fi
