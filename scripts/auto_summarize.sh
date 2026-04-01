#!/usr/bin/env bash
#
# auto_summarize.sh — Generate an AI summary for a checkpoint using claude --print.
#
# Called by checkpoint.sh when auto_summarize is enabled.
# Uses claude --print to generate a structured summary, then saves it
# to the checkpoint metadata.
#
# Usage: auto_summarize.sh <checkpoint_id> <transcript_path>
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

CHECKPOINT_ID="${1:?Usage: auto_summarize.sh <checkpoint_id> <transcript_path>}"
TRANSCRIPT_PATH="${2:?Usage: auto_summarize.sh <checkpoint_id> <transcript_path>}"

# Check claude is available
if ! command -v claude >/dev/null 2>&1; then
    echo "Warning: claude not found, skipping auto-summarize" >&2
    exit 0
fi

# Generate condensed transcript
CONDENSED="$(python3 "$SCRIPT_DIR/parse_jsonl.py" transcript --checkpoint "$TRANSCRIPT_PATH" 2>/dev/null | head -200)"

if [ -z "$CONDENSED" ]; then
    exit 0
fi

# Ask Claude to summarize
PROMPT="Analyze this Claude Code session transcript and return ONLY a JSON object (no markdown, no explanation):

<transcript>
$CONDENSED
</transcript>

Return this exact JSON structure:
{\"intent\":\"What the user was trying to accomplish (1-2 sentences)\",\"outcome\":\"What was achieved (1-2 sentences)\",\"learnings\":{\"repo\":[],\"code\":[],\"workflow\":[]},\"friction\":[],\"open_items\":[]}"

SUMMARY_JSON="$(claude --print --output-format text "$PROMPT" 2>/dev/null || echo "")"

# Validate it's JSON
if [ -z "$SUMMARY_JSON" ]; then
    exit 0
fi

echo "$SUMMARY_JSON" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null || exit 0

# Save to checkpoint
echo "$SUMMARY_JSON" > /tmp/neander-auto-summary-$$.json
bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" /tmp/neander-auto-summary-$$.json 2>/dev/null || true
rm -f /tmp/neander-auto-summary-$$.json
