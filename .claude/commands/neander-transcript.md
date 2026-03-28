# View condensed session transcript

Display the transcript output from the parser script. Do NOT summarize or rewrite it — show the `[User]`, `[Assistant]`, `[Tool]`, and `[Files Modified]` entries exactly as the script outputs them.

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — show transcript for the current session
- **a session ID or file path** — show transcript for that specific session
- **"list"** — list all sessions for the current project and let the user pick one

## Finding the session file

- **Current session**: Your session ID is in your conversation context. Find it with: `find ~/.claude/projects -name "<your-session-id>.jsonl" -type f`
- **Session ID provided**: `find ~/.claude/projects -name "<session-id>.jsonl" -type f`
- **File path provided**: use it directly
- **"list"**: run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick

## Generating the transcript

Once you have the session file path, run:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <path>
```

**IMPORTANT**: Display the output exactly as-is. This is a transcript, not a summary. Do not rewrite, condense, or reorganize the output. Show it directly to the user.

If the output is very long, show it in chunks — first portion, then ask if the user wants to see more.

If the user asks to filter (e.g., "just tool calls" or "just user messages"), grep the output for the relevant `[Tool]`, `[User]`, or `[Assistant]` prefix.

$ARGUMENTS
