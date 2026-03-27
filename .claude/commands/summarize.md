# Summarize a Claude Code session

Read the session transcript and provide a structured summary.

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — summarize the current session
- **a session ID or file path** — summarize that specific session
- **"list"** — list all sessions for the current project and let the user pick one

## Finding the session file

- **Current session**: Your session ID is in your conversation context. Find it with: `find ~/.claude/projects -name "<your-session-id>.jsonl" -type f`
- **Session ID provided**: `find ~/.claude/projects -name "<session-id>.jsonl" -type f`
- **File path provided**: use it directly
- **"list"**: run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick

## Generating the summary

1. Parse the session to get stats:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path>
   ```

2. Get the condensed transcript:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <path> --max-lines 200
   ```

3. Read the condensed transcript and produce a summary with this structure:

   **Session**: <slug> (<session_id short>)
   **Branch**: <git branch>
   **Duration**: <first -> last timestamp>
   **Tokens**: <total> (<input> in / <output> out)

   ### Intent
   - What the user was trying to accomplish (1-3 bullets)

   ### Outcome
   - What was actually done (1-3 bullets)

   ### Files Modified
   - List of files changed

   ### Key Decisions
   - Non-obvious choices made during the session

   ### Open Items
   - Anything left incomplete or needing follow-up

$ARGUMENTS
