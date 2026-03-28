# Summarize a Claude Code session

Read the session transcript and produce a structured AI summary.

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

1. Get stats and transcript:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path>
   python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <path>
   ```

2. Read the full transcript and produce a summary with this exact structure:

   **Session**: <slug> (<session_id short>)
   **Branch**: <git branch>
   **Duration**: <start> to <end> (<X minutes/hours>)
   **Tokens**: <total> (<input> in / <output> out)

   ### Intent
   What the user was trying to accomplish. 1-2 sentences, be specific.

   ### Outcome
   What was actually achieved. 1-2 sentences, note if anything was left incomplete.

   ### Learnings
   **Repository**:
   - Codebase-specific patterns, conventions, or gotchas discovered during the session

   **Code**:
   - `file/path.py:42-56` — What was learned about this specific code

   **Workflow**:
   - General development practices or tool usage insights

   ### Friction
   - Problems, blockers, or annoyances encountered during the session
   - Include both hard blockers and minor annoyances

   ### Open Items
   - Tech debt or unfinished work intentionally deferred
   - Things to revisit later (not failures, but conscious decisions to defer)

   Skip any section that doesn't apply (e.g., if there was no friction, omit it). Be concise but specific — include file paths and line numbers where relevant.

$ARGUMENTS
