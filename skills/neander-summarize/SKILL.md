---
description: Summarize a Claude Code session or checkpoint. MUST be invoked when the user says "summarize", "summarise", or "summary" followed by a session ID, checkpoint ID, or "current". Also use when the user asks about the outcome of previous work. This skill persists summaries to the checkpoint branch.
---
# Summarize a Claude Code session

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — summarize the current session (latest checkpoint)
- **a session ID (UUID with dashes)** — summarize the latest checkpoint for that session
- **a checkpoint ID (16-char hex like `52e4e8dc46995673`)** — summarize that specific checkpoint
- **a file path** — summarize that specific session file
- **"list"** — list all sessions for the current project and let the user pick one
- **"--force"** (appended) — regenerate even if a summary already exists

## Identifying what to summarize

**Checkpoint ID** (16-char hex, no dashes): Find the transcript stored in that checkpoint:
```
git show neander/checkpoints/v1:<id[:2]>/<id[2:]>/metadata.json 2>/dev/null
```
Get the session ID from `session_ids[0]`, then extract the transcript:
```
git show neander/checkpoints/v1:<id[:2]>/<id[2:]>/transcript-<session_id>.jsonl 2>/dev/null > /tmp/neander-transcript.jsonl
```
Use `/tmp/neander-transcript.jsonl` as the session file. Remember to use the **checkpoint ID** for saving.

**Session ID** (UUID with dashes): `find __HOME__/.claude/projects -name "<session-id>.jsonl" -type f`

**Current session**: Your session ID is in your conversation context. Same as session ID flow.

**File path**: Use it directly.

## Step 1: Get stats and scoped transcript

First get stats:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --checkpoint <id> --json
```

Then get the **scoped** transcript. If summarizing a checkpoint ID, read the `transcript_offset` from its metadata first:
```
git show neander/checkpoints/v1:<id[:2]>/<id[2:]>/metadata.json 2>/dev/null
```
Extract the `transcript_offset` value from the JSON. Then get only the delta transcript:
```
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --checkpoint <id> --offset <transcript_offset>
```

If `transcript_offset` is 0 or not found, omit `--offset` (reads full transcript).

**IMPORTANT**: The `--offset` ensures the summary describes what THIS checkpoint changed, not the entire session. A session may have multiple checkpoints at different commits — each should get its own scoped summary.

## Step 2: Generate, persist, and display summary — ALL IN ONE Bash command

Analyze the transcript. Then run a SINGLE Bash command that writes the JSON, saves it to the checkpoint branch, and outputs the result. Use the **checkpoint ID** if the user specified one, otherwise use the **session ID** as `<id>`.

```bash
cat > /tmp/neander-summary.json << 'SUMMARY_EOF'
<YOUR JSON HERE>
SUMMARY_EOF
bash __SCRIPTS_DIR__/persist_summary.sh <id> /tmp/neander-summary.json
```

The JSON must have this structure:

```json
{
  "intent": "What the user was trying to accomplish. 1-2 specific sentences.",
  "outcome": "What was achieved. 1-2 sentences. Note if incomplete.",
  "learnings": {
    "repo": ["Codebase-specific patterns, conventions, or gotchas discovered"],
    "code": [{"path": "file.py", "lines": "42-56", "finding": "What was learned"}],
    "workflow": ["Development practices or tool usage insights"]
  },
  "friction": ["Problems, blockers, or annoyances encountered"],
  "open_items": ["Deferred work — conscious decisions to revisit later"]
}
```

Use empty arrays for sections that don't apply. Include file paths and line numbers where relevant.

## Step 3: Display the summary

Format the output from the command above as:

**Session**: <slug> (<session_id short>)
**Branch**: <git branch>
**Duration**: <start> to <end> (<X minutes/hours>)
**Tokens**: <total> (<input> in / <output> out)

### Intent
<from JSON>

### Outcome
<from JSON>

### Learnings
(format repo/code/workflow sections)

### Friction
<from JSON>

### Open Items
<from JSON>

$ARGUMENTS
