#!/usr/bin/env bash
#
# auto_summarize.sh — Generate a scoped AI summary for a checkpoint.
#
# Uses transcript_offset to only summarize the DELTA since the last
# checkpoint — not the entire session. This ensures each checkpoint's
# summary describes what happened between this and the previous checkpoint.
#
# Usage: auto_summarize.sh <checkpoint_id> <transcript_path> [transcript_offset]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

CHECKPOINT_ID="${1:?Usage: auto_summarize.sh <checkpoint_id> <transcript_path> [offset]}"
TRANSCRIPT_PATH="${2:?Usage: auto_summarize.sh <checkpoint_id> <transcript_path> [offset]}"
TRANSCRIPT_OFFSET="${3:-0}"

# Check claude is available
if ! command -v claude >/dev/null 2>&1; then
    echo "Warning: claude not found, skipping auto-summarize" >&2
    exit 0
fi

# Generate condensed transcript from ONLY the delta (offset to end)
CONDENSED="$(python3 "$SCRIPT_DIR/parse_jsonl.py" transcript --checkpoint "$TRANSCRIPT_PATH" --offset "$TRANSCRIPT_OFFSET" 2>/dev/null)"

if [ -z "$CONDENSED" ]; then
    exit 0
fi

# Count lines to keep prompt reasonable
LINE_COUNT="$(echo "$CONDENSED" | wc -l | tr -d ' ')"
if [ "$LINE_COUNT" -gt 200 ]; then
    # Take last 200 lines if delta is too large
    CONDENSED="$(echo "$CONDENSED" | tail -200)"
fi

# Ask Claude to summarize the delta
PROMPT="Analyze this portion of a Claude Code session transcript. This is the work done since the LAST checkpoint — summarize only what happened in THIS segment.

Return ONLY a JSON object (no markdown, no explanation):

<transcript>
$CONDENSED
</transcript>

Return this exact JSON structure:
{\"intent\":\"What was accomplished in this segment (1-2 specific sentences)\",\"outcome\":\"What was achieved (1-2 sentences)\",\"learnings\":{\"repo\":[],\"code\":[],\"workflow\":[]},\"friction\":[],\"open_items\":[]}"

RAW_OUTPUT="$(claude --print --output-format text "$PROMPT" 2>/dev/null || echo "")"

if [ -z "$RAW_OUTPUT" ]; then
    exit 0
fi

# Strip markdown code fences if present (claude --print wraps JSON in ```json ... ```)
SUMMARY_JSON="$(echo "$RAW_OUTPUT" | python3 -c "
import sys, json, re
raw = sys.stdin.read().strip()
# Remove ```json ... ``` wrapper
cleaned = re.sub(r'^[^\S\n]*\`\`\`(?:json)?\s*\n?', '', raw)
cleaned = re.sub(r'\n?[^\S\n]*\`\`\`[^\S\n]*$', '', cleaned)
# Validate it's JSON
json.loads(cleaned)
print(cleaned)
" 2>/dev/null || echo "")"

if [ -z "$SUMMARY_JSON" ]; then
    exit 0
fi

# Save to checkpoint
echo "$SUMMARY_JSON" > /tmp/neander-auto-summary-$$.json
bash "$SCRIPT_DIR/save_summary.sh" "$CHECKPOINT_ID" /tmp/neander-auto-summary-$$.json 2>/dev/null || true
rm -f /tmp/neander-auto-summary-$$.json
