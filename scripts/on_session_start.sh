#!/usr/bin/env bash
#
# on_session_start.sh — SessionStart hook
#
# Injects past checkpoint context into the new session.
# Stdout is added to Claude's context automatically by Claude Code.
#
# Silent exit (no output) when there's nothing relevant to show.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Get current branch
BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo "")"
[ -z "$BRANCH" ] && exit 0

# Check if checkpoint branch exists
git rev-parse --verify neander/checkpoints/v1 >/dev/null 2>&1 || exit 0

# Run Python script (stdin is not needed, branch passed as arg)
python3 "$SCRIPT_DIR/get_branch_context.py" "$BRANCH" 2>/dev/null || true
