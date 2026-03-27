# Summarize a Claude Code session

Read the session transcript and provide a structured summary.

## Instructions

1. Find the most recent session JSONL file by running:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py list --project "$(pwd)"
   ```
   If the user provided a session ID or path, use that instead.

2. Parse the session to get stats:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path>
   ```

3. Get the condensed transcript:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <path> --max-lines 200
   ```

4. Read the condensed transcript and produce a summary with this structure:

   **Session**: <slug> (<session_id short>)
   **Branch**: <git branch>
   **Duration**: <first → last timestamp>
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
