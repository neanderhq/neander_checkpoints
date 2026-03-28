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
- **By session ID**: `find ~/.claude/projects -name "<session-id>.jsonl" -type f`
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

If the checkpoint branch exists on the remote:
```
git fetch origin claude-sessions/checkpoints 2>/dev/null
```

If the session JSONL doesn't exist locally but is on the checkpoint branch:
1. Extract the transcript from the checkpoint
2. Determine the correct local path: `~/.claude/projects/<encoded-project-dir>/<session-id>.jsonl`
3. Copy it there
4. Print the resume command

$ARGUMENTS
