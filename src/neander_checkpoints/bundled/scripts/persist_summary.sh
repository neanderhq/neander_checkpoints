#!/usr/bin/env bash
#
# persist_summary.sh — Save summary JSON file to checkpoint branch.
#
# Reads a summary JSON file, saves to checkpoint branch, then
# prints the JSON back so Claude can format it for the user.
#
# Usage: persist_summary.sh <session_or_checkpoint_id> <json_file>
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ID="${1:?Usage: persist_summary.sh <session_or_checkpoint_id> <json_file>}"
JSON_FILE="${2:?Usage: persist_summary.sh <session_or_checkpoint_id> <json_file>}"

if [ ! -f "$JSON_FILE" ]; then
    echo "Error: JSON file not found: $JSON_FILE" >&2
    exit 1
fi

# Save to checkpoint branch
"$SCRIPT_DIR/save_summary.sh" "$ID" "$JSON_FILE" 2>&1

# Output the summary JSON so caller can display it
echo "---SUMMARY---"
cat "$JSON_FILE"
