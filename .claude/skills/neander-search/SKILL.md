---
description: Search across Claude Code checkpoints by keyword, branch, file, date, commit, or natural language. Use when the user asks about previous work, what they did, which checkpoint touched a file, or anything about past coding activity.
---
# Search checkpoints

## Arguments

`$ARGUMENTS` is a natural language query. Parse it to extract filters:

- **Keywords**: any quoted text or descriptive terms → `--keyword`
- **Branch references**: "on branch X", "feat/X" → `--branch`
- **File references**: any file path or filename → `--file`
- **Date references**: "last week", "yesterday", "since March 20" → `--date-from` / `--date-to`. Convert relative dates to YYYY-MM-DD.
- **Commit references**: anything that looks like a SHA → `--commit`

If no query is provided, use `--date-from` with a recent date (last 7 days).

## Step 1: Run search

```
python3 __SCRIPTS_DIR__/parse_jsonl.py search --project <current working directory> [filters]
```

Available flags: `--keyword`, `--branch`, `--file`, `--date-from`, `--date-to`, `--commit`

## Step 2: Output verbatim

Copy the ENTIRE output from step 1 and output it as a markdown code block.

**IMPORTANT — DO NOT IGNORE THESE RULES:**
- **DO NOT REFORMAT** into a table. Show the script output exactly as-is.
- **DO NOT SUMMARIZE.** Show all results, not a subset.
- **DO NOT ADD COMMENTARY** before the results.
- **USE A CODE BLOCK.** Wrap the output in triple backticks.

After the code block, you may offer follow-up suggestions:
- `/neander-transcript <checkpoint-id>` to view a transcript
- `/neander-summarize <checkpoint-id>` to summarize

$ARGUMENTS
