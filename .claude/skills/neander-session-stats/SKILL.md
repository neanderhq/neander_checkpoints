---
description: Show token usage, cost estimate, duration, and file stats for a Claude Code session. Use when the user asks about costs, token usage, how long a session took, or session metrics.
---
# Session statistics

Show token usage, message counts, duration, and file modification stats for a Claude Code session.

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — stats for the current session
- **a session ID or file path** — stats for that specific session
- **"list"** — list all sessions for the current project and let the user pick one

## Finding the session file

- **Current session**: Your session ID is in your conversation context. Find it with: `find ~/.claude/projects -name "<your-session-id>.jsonl" -type f`
- **Session ID provided**: `find ~/.claude/projects -name "<session-id>.jsonl" -type f`
- **File path provided**: use it directly
- **"list"**: run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick

## Generating the stats

1. Get full stats:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path>
   ```

2. Also get file snapshots for checkpoint info:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py snapshots --session <path>
   ```

3. Present the stats in a clear format. Include:
   - Session ID, slug, branch, working directory
   - Models used
   - Duration (start -> end, total minutes)
   - Token usage breakdown (input, output, cache read, cache created, total)
   - Estimated cost (Opus: $15/M input, $75/M output; Sonnet: $3/M input, $15/M output)
   - Message counts (user vs assistant)
   - Files modified (list)
   - Number of checkpoints/snapshots

$ARGUMENTS
