# Search sessions

Search across all Claude Code sessions for this project by keyword, branch, file, date, or commit.

## Arguments

`$ARGUMENTS` is a natural language query. Parse it to extract filters:

- **Keywords**: any quoted text or descriptive terms → `--keyword`
- **Branch references**: "on branch X", "feat/X" → `--branch`
- **File references**: any file path or filename → `--file`
- **Date references**: "last week", "yesterday", "since March 20" → `--date-from` / `--date-to`. Convert relative dates to YYYY-MM-DD.
- **Commit references**: anything that looks like a SHA → `--commit`

Multiple filters can be combined — they are ANDed together.

## Examples

- `/neander-search OAuth` → `--keyword OAuth`
- `/neander-search sessions on feat/attachments` → `--branch feat/attachments`
- `/neander-search which session edited message_repository.py` → `--file message_repository.py`
- `/neander-search sessions from last week` → `--date-from 2026-03-21`
- `/neander-search what produced commit 835718b` → `--commit 835718b`
- `/neander-search OAuth on feat/auth since March 20` → `--keyword OAuth --branch feat/auth --date-from 2026-03-20`

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

## Displaying results

Show the search output. For each match, the script shows:
- Session ID, date, branch
- First user prompt (truncated)
- Match reasons and token count
- Keyword match snippets with context (if keyword search)

## Semantic re-ranking

If the user's query is conversational or vague (e.g., "the session where I refactored the database layer"), the keyword search may return too many or imprecise results. In that case:

1. Run a broad search (use the most distinctive word as `--keyword`, or use `--date-from`/`--branch` if mentioned)
2. For the top results, read their first prompts and match snippets
3. Use your judgment to rank which sessions are most relevant to what the user is actually asking about
4. Present only the most relevant results, with a brief explanation of why each matches

If no structured filters can be extracted from the query, fall back to listing recent sessions and scanning their first prompts for relevance.

## Follow-up

After showing results, offer:
- `/neander-transcript <session-id>` to view a specific session
- `/neander-summarize <session-id>` to summarize it

$ARGUMENTS
