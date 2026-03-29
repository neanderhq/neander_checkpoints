---
description: Show token usage, cost estimate, duration, and file stats for a checkpoint or session. Use when the user asks about costs, token usage, how long something took, or checkpoint metrics. Accepts checkpoint IDs (16-char hex) or session IDs (UUIDs).
---
# Checkpoint info

## Step 1: Run stats command

```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <checkpoint_id_or_session_id_or_path>
```

The `--session` flag accepts a checkpoint ID (16-char hex), a full session ID (UUID), a partial ID, or a full file path.

If the user said "current", use your own session ID from the conversation context.
If the user said "list", run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick.

## Step 2: Output verbatim

Copy the ENTIRE output from step 1 and output it as a markdown code block.

**IMPORTANT — DO NOT IGNORE THESE RULES:**
- **DO NOT SUMMARIZE.** Output every single line exactly as-is.
- **DO NOT ADD COMMENTARY.** No analysis, no suggestions, just the output.
- **USE A CODE BLOCK.** Wrap the entire output in triple backticks so it renders as preformatted text.

This is a DISPLAY command, not an ANALYSIS command. Your only job is to show the raw output.

$ARGUMENTS
