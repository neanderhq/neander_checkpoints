---
description: Generate an AI summary of a Claude Code session with intent, outcome, learnings, friction, and open items. Use when the user wants to understand what happened in a session, needs a summary, or asks about the outcome of previous work.
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

## Execution

Follow these steps IN ORDER. Do not skip any step. Do not show the summary to the user until step 4.

### Step 1: Get stats and transcript

```
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path> --json
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <path>
```

### Step 2: Write the summary JSON file

Analyze the transcript. Then write `/tmp/neander-summary.json` using the Write tool with this structure:

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

Guidelines for each field:
- **intent**: What the user was trying to accomplish. 1-2 sentences, be specific.
- **outcome**: What was actually achieved. 1-2 sentences. Note if anything was left incomplete.
- **learnings.repo**: Codebase-specific patterns, conventions, or gotchas discovered during the session.
- **learnings.code**: File-specific findings with paths and line numbers. Include what was learned about that specific code.
- **learnings.workflow**: General development practices or tool usage insights.
- **friction**: Problems, blockers, or annoyances encountered. Include both hard blockers and minor annoyances.
- **open_items**: Tech debt or unfinished work intentionally deferred. Things to revisit later — not failures, but conscious decisions to defer.

Skip any section that doesn't apply (use empty arrays). Be concise but specific — always include file paths and line numbers where relevant.

### Step 3: Save to checkpoint branch

```
bash __SCRIPTS_DIR__/save_summary.sh <id> /tmp/neander-summary.json
```

Use the **checkpoint ID** if the user specified one, otherwise use the **session ID**.

### Step 4: Display the summary to the user

Read back `/tmp/neander-summary.json` and format it as:

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
