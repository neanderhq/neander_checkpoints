---
description: Search across Claude Code checkpoints by keyword, branch, file, date, commit, or natural language. Use when the user asks about previous work, what they did, which checkpoint touched a file, or anything about past coding activity.
---
# Search checkpoints

Search across all Claude Code checkpoints for this project by keyword, branch, file, date, or commit.

## Arguments

`$ARGUMENTS` is a natural language query. Parse it to extract filters:

- **Keywords**: any quoted text or descriptive terms → `--keyword`
- **Branch references**: "on branch X", "feat/X" → `--branch`
- **File references**: any file path or filename → `--file`
- **Date references**: "last week", "yesterday", "since March 20" → `--date-from` / `--date-to`. Convert relative dates to YYYY-MM-DD.
- **Commit references**: anything that looks like a SHA → `--commit`

Multiple filters can be combined — they are ANDed together.

## Running the search

```
python3 __SCRIPTS_DIR__/parse_jsonl.py search --project <current working directory> [filters]
```

Available flags:
- `--keyword <text>` or `-k <text>`
- `--branch <name>` or `-b <name>`
- `--file <path>` or `-f <path>`
- `--date-from <YYYY-MM-DD>`
- `--date-to <YYYY-MM-DD>`
- `--commit <sha>`

## Semantic re-ranking

If the user's query is conversational or vague (e.g., "the checkpoint where I refactored the database layer"), the keyword search may return too many or imprecise results. In that case:

1. Run a broad search (use the most distinctive word as `--keyword`, or use `--date-from`/`--branch` if mentioned)
2. For the top results, read their first prompts and match snippets
3. Use your judgment to rank which checkpoints are most relevant to what the user is actually asking about
4. Present only the most relevant results, with a brief explanation of why each matches

If no structured filters can be extracted from the query, fall back to listing recent checkpoints and scanning their first prompts for relevance.

## Follow-up

After showing results, offer:
- `/neander-transcript <checkpoint-id>` to view a specific checkpoint's transcript
- `/neander-summarize <checkpoint-id>` to summarize it

$ARGUMENTS
