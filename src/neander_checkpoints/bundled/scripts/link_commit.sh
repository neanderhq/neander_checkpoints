#!/usr/bin/env bash
#
# link_commit.sh — Add session metadata trailer to the most recent commit.
#
# Called by PostToolUse:Bash hook when a git commit is detected.
# Adds a "Claude-Session" trailer linking the commit to the active session.
#
# Usage: link_commit.sh <session_id>
#

set -euo pipefail

SESSION_ID="${1:?Usage: link_commit.sh <session_id>}"

# Only proceed if we're in a git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    exit 0
fi

# Get the latest commit message
CURRENT_MSG="$(git log -1 --format=%B)"

# Don't add trailer if already present
if echo "$CURRENT_MSG" | grep -q "Claude-Session:"; then
    exit 0
fi

# Amend the commit with the trailer
git commit --amend --no-edit --trailer "Claude-Session: $SESSION_ID" --quiet 2>/dev/null || true
