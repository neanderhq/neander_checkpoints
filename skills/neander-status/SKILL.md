---
description: Show active and recent Claude Code sessions for this project. Use when the user asks about recent sessions, what's been going on, or session overview.
---
# Session status

## Step 1: Run status command

```
python3 __SCRIPTS_DIR__/parse_jsonl.py status --project <current working directory>
```

Use `--fetch` to fetch the latest checkpoint data from the remote before showing status.

## Step 2: Output verbatim

Copy the ENTIRE output from step 1 and output it as a markdown code block.

**IMPORTANT — DO NOT IGNORE:**
- **DO NOT REFORMAT** into a different table style. The script outputs a formatted table — show it exactly as-is.
- **DO NOT ADD COMMENTARY.** No analysis, no suggestions, just the table.

$ARGUMENTS
