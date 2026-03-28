---
description: Show token usage, cost estimate, duration, and file stats for a Claude Code session. Use when the user asks about costs, token usage, how long a session took, or session metrics.
---
# Session statistics

Run this command and display the output:

```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <session_id_or_path>
```

The `--session` flag accepts a full file path, a full session ID, or a partial session ID.

If the user said "current", use your own session ID from the conversation context.
If the user said "list", run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick.

$ARGUMENTS
