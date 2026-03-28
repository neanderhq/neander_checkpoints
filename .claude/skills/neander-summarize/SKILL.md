---
description: Generate an AI summary of a Claude Code session with intent, outcome, learnings, friction, and open items. Use when the user wants to understand what happened in a session, needs a summary, or asks about the outcome of previous work.
---
# Summarize a Claude Code session

Read the session transcript and produce a structured AI summary. Persists the summary to the checkpoint branch so it doesn't need to be regenerated.

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — summarize the current session (latest checkpoint)
- **a session ID (UUID with dashes)** — summarize the latest checkpoint for that session
- **a checkpoint ID (16-char hex like `52e4e8dc46995673`)** — summarize that specific checkpoint
- **a file path** — summarize that specific session file
- **"list"** — list all sessions for the current project and let the user pick one
- **"--force"** (appended) — regenerate even if a summary already exists

## Identifying what to summarize

**Checkpoint ID** (16-char hex, no dashes): The user wants a specific checkpoint summarized. You need to find the transcript stored in that checkpoint:
```
git show neander/checkpoints/v1:<id[:2]>/<id[2:]>/metadata.json 2>/dev/null
```
Get the session ID from `session_ids[0]`, then find the transcript:
```
git show neander/checkpoints/v1:<id[:2]>/<id[2:]>/transcript-<session_id>.jsonl 2>/dev/null > /tmp/neander-transcript-<session_id>.jsonl
```
Use that temp file as the session file for stats/transcript generation. The save_summary.sh call should use the **checkpoint ID**, not the session ID.

**Session ID** (UUID with dashes): Find the JSONL file:
```
find __HOME__/.claude/projects -name "<session-id>.jsonl" -type f
```
The save_summary.sh call should use the **session ID** (it will save to the latest checkpoint).

**Current session**: Your session ID is in your conversation context. Same as session ID flow.

**File path**: Use it directly.

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

**IMPORTANT: You MUST do this step after generating the summary.** Pipe the summary as JSON directly to save_summary.sh:

```
echo '{"intent":"...","outcome":"...","learnings":{"repo":[],"code":[],"workflow":[]},"friction":[],"open_items":[]}' | bash __SCRIPTS_DIR__/save_summary.sh <id> -
```

- If the user specified a **checkpoint ID**, use that as `<id>`
- If the user specified a **session ID**, use that as `<id>` (save_summary.sh will find the latest checkpoint)

Replace the JSON with the actual structured summary you generated. The `-` tells the script to read from stdin.

$ARGUMENTS
