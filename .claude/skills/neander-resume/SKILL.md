---
description: Find a previous checkpoint and show the command to resume its session. Use when the user wants to continue previous work, resume a session, or pick up where they left off. Accepts checkpoint IDs (16-char hex) or session IDs (UUIDs). Supports cross-machine resume.
---
# Resume from a checkpoint

## If a checkpoint ID or session ID was provided:

**Step 1**: Get the session ID from the checkpoint:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --checkpoint <id> --json
```
Extract `session_id` from the JSON output's `metadata` field.

**Step 2**: Show the resume command:
```
claude --resume <session_id>
```

**Step 3**: If the session file doesn't exist locally, restore it:
```
bash __SCRIPTS_DIR__/restore.sh <session_id> <current working directory>
```

## If no ID was provided (or "list"):

**Step 1**: Show status so the user can pick a checkpoint:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py status --project <current working directory>
```

**Step 2**: Output the status verbatim as a code block, then ask the user which checkpoint to resume.

**Step 3**: Once selected, get the session ID and show the resume command as above.

$ARGUMENTS
