---
description: Generate an AI summary of a Claude Code session with intent, outcome, learnings, friction, and open items. Use when the user wants to understand what happened in a session, needs a summary, or asks about the outcome of previous work.
---
# Summarize a Claude Code session

Read the session transcript and produce a structured AI summary. Persists the summary to the checkpoint branch so it doesn't need to be regenerated.

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — summarize the current session
- **a session ID or file path** — summarize that specific session
- **"list"** — list all sessions for the current project and let the user pick one
- **"--force"** (appended) — regenerate even if a summary already exists

## Finding the session file

- **Current session**: Your session ID is in your conversation context. Find it with: `find __HOME__/.claude/projects -name "<your-session-id>.jsonl" -type f`
- **Session ID provided**: `find __HOME__/.claude/projects -name "<session-id>.jsonl" -type f`
- **File path provided**: use it directly
- **"list"**: run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick

## Check for existing summary

Before generating, check if a summary already exists in the checkpoint metadata. If the checkpoint branch exists and the session has a checkpoint:

```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path> --json
```

Get the session ID from the stats, then check the checkpoint branch:
```
git show neander/checkpoints/v1:<shard_dir>/metadata.json 2>/dev/null
```

If `metadata.summary` is not null and `--force` was NOT specified, display the existing summary and note it was cached. Skip generation.

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

## Persisting the summary

After generating, save the summary to the checkpoint branch so it's cached for next time. Write the structured sections as JSON to a temp file, then run:

```
bash __SCRIPTS_DIR__/save_summary.sh <session_id> /tmp/neander-summary-<session_id>.json
```

The JSON format to write to the temp file:
```json
{
  "intent": "...",
  "outcome": "...",
  "learnings": {
    "repo": ["..."],
    "code": [{"path": "file.py", "lines": "42-56", "finding": "..."}],
    "workflow": ["..."]
  },
  "friction": ["..."],
  "open_items": ["..."]
}
```

After saving, clean up the temp file.

$ARGUMENTS
