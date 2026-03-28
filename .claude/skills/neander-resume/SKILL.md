---
description: Find a previous Claude Code session and show the command to resume it. Use when the user wants to continue previous work, resume a session, or pick up where they left off. Supports cross-machine resume.
---
# Resume a session

Find a previous Claude Code session and show the command to resume it.

## Arguments

`$ARGUMENTS` can be one of:
- **empty** — show the most recent session for this project with its resume command
- **a session ID** — resume that specific session
- **a branch name** — find sessions associated with that branch
- **"list"** — list all sessions and let the user pick

## Finding the session

- **Most recent**: `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>`
- **By session ID**: `find __HOME__/.claude/projects -name "<session-id>.jsonl" -type f`
- **By branch**: `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` then filter by branch from the stats

## What to show

For each candidate session, get stats:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path>
```

Display:
- Session ID
- Branch it was on
- Last prompt (first 100 chars of the last user message)
- Duration and how long ago it ended (e.g., "45 min session, ended 3h ago")
- Token usage
- Files modified

If multiple sessions match (e.g., same branch), show all and let the user pick.

## Resume command

Print the command to resume:
```
claude --resume <session_id>
```

## Cross-machine resume

If the session JSONL is NOT found locally (e.g., a teammate started it on another machine), use the restore script to fetch it from the checkpoint branch:

```
bash __SCRIPTS_DIR__/restore.sh <session_id> <current working directory>
```

If the restore script succeeds, the user can then run `claude --resume <session_id>`.

If the checkpoint branch doesn't exist on the remote, tell the user the session transcript isn't available remotely.

$ARGUMENTS
