# View condensed session transcript

Show a clean, readable version of a Claude Code session transcript.

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — show transcript for the current session
- **a session ID or file path** — show transcript for that specific session
- **"list"** — list all sessions for the current project and let the user pick one

## Instructions

### If showing the current session:
Your session ID is available in your conversation context. Find the matching JSONL file:
```
find ~/.claude/projects -name "<your-session-id>.jsonl" -type f
```
Then generate the transcript from that file.

### If a session ID or path was provided:
If it looks like a file path, use it directly. If it's a session ID (UUID format), find it:
```
find ~/.claude/projects -name "<session-id>.jsonl" -type f
```

### If "list" was specified:
List all sessions for the current project and ask the user to pick one:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>
```

## Generating the transcript

Once you have the session file path:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <path>
```

Display the output directly. If it's very long, show the first and last sections with a note about what's in between.

If the user asks to filter (e.g., "just show tool calls" or "just show user messages"), re-read the transcript and filter accordingly.

$ARGUMENTS
