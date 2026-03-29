---
description: Find a previous checkpoint and show the command to resume its session. Use when the user wants to continue previous work, resume a session, or pick up where they left off. Accepts checkpoint IDs (16-char hex) or session IDs (UUIDs). Supports cross-machine resume.
---
# Resume from a checkpoint

Find a previous checkpoint and show the command to resume its session.

## Arguments

`$ARGUMENTS` can be one of:
- **empty** — show the most recent checkpoint for this project with its resume command
- **a checkpoint ID** (16-char hex) — look up the checkpoint, find its session ID, show resume command
- **a session ID** (UUID) — resume that specific session directly
- **a branch name** — find checkpoints associated with that branch
- **"list"** — list all checkpoints and let the user pick

## Finding the checkpoint

- **Most recent**: `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>`
- **By checkpoint ID**: `python3 __SCRIPTS_DIR__/parse_jsonl.py stats --checkpoint <checkpoint_id>`
- **By session ID**: `find __HOME__/.claude/projects -name "<session-id>.jsonl" -type f`
- **By branch**: `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` then filter by branch from the stats

## What to show

For each candidate, get stats:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --checkpoint <checkpoint_id_or_path>
```

Display:
- Checkpoint ID
- Session ID
- Branch it was on
- Last prompt (first 100 chars of the last user message)
- Duration and how long ago it ended (e.g., "45 min session, ended 3h ago")
- Token usage
- Files modified

If multiple checkpoints match (e.g., same branch), show all and let the user pick.

## Resume command

Print the command to resume (using the session ID from the checkpoint):
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
