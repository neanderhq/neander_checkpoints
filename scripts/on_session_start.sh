#!/usr/bin/env bash
#
# on_session_start.sh — SessionStart hook
#
# Injects past checkpoint context into the new session.
# Stdout is added to Claude's context automatically by Claude Code.
#
# Controlled by .claude/neander-checkpoints.json → inject_previous_context
# Silent exit (no output) when disabled or nothing relevant.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check if feature is enabled (default: true)
CONFIG=".claude/neander-checkpoints.json"
if [ -f "$CONFIG" ]; then
    ENABLED=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('inject_previous_context', True))" 2>/dev/null || echo "True")
    [ "$ENABLED" = "False" ] && exit 0
fi

# Get current branch
BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo "")"
[ -z "$BRANCH" ] && exit 0

# Check if checkpoint branch exists
git rev-parse --verify neander/checkpoints/v1 >/dev/null 2>&1 || exit 0

# Run Python script
python3 "$SCRIPT_DIR/get_branch_context.py" "$BRANCH" 2>/dev/null || true
