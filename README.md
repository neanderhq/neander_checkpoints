# neander_checkpoints

Capture Claude Code sessions alongside your Git history. Understand *why* code changed, not just *what*. Resume where you left off — even on a different machine.

Built natively for Claude Code using hooks, skills, agents, and scripts. No external binaries. Install once, works automatically.

## Why

Your git log shows what code changed. But when AI writes your code, the *how* and *why* live in the conversation — prompts, reasoning, tool calls, dead ends, decisions. Without capturing that, you lose context the moment a session ends.

neander_checkpoints solves this:

- **Automatic context on session start** — Claude starts every session knowing what was done before on this branch, what's incomplete, and what the friction points were
- **Code context agent** — when Claude reads unfamiliar code or is about to refactor, a subagent automatically looks up WHY it was written that way from past checkpoint transcripts
- **Understand why code changed** — see the full prompt/response transcript and files touched for any checkpoint
- **Search across checkpoints** — find the checkpoint where you fixed the auth bug, by keyword, branch, file, or just asking in natural language
- **Cross-machine resume** — push checkpoints to remote, pull them on another machine, continue exactly where you left off
- **Keep git history clean** — checkpoint data lives on a separate orphan branch, never pollutes your working tree

## How it works

Once installed, everything is automatic:

1. **You code with Claude** — business as usual
2. **On every commit**, a hook captures the session transcript and metadata as a checkpoint on the `neander/checkpoints/v1` orphan branch
3. **On session end**, a final checkpoint captures everything even if no commits were made
4. **On session start**, past checkpoint summaries for the current branch are injected into Claude's context
5. **When reading code**, the code-context agent can look up why any piece of code was written
6. **Commits get linked** — a `Claude-Session` trailer is added so you can trace any commit back to the conversation that produced it

When you need context, just ask naturally:

| You say | What happens |
|---|---|
| "What did I do yesterday?" | Claude searches checkpoints, shows relevant results |
| "Why was this code written this way?" | Code-context agent searches transcripts for the reasoning |
| "How much did that checkpoint cost?" | Claude shows token usage and cost estimate |

## CLI

```bash
pip install neander-checkpoints
```

| Command | Description |
|---|---|
| `neander-checkpoints install` | Install skills, agents, scripts, and hooks into a project |
| `neander-checkpoints uninstall` | Remove everything from a project |
| `neander-checkpoints resume [id]` | List checkpoints or launch `claude --resume` |
| `neander-checkpoints config` | View or change settings |
| `neander-checkpoints config auto_summarize on/off` | Auto-generate summaries on checkpoint creation |
| `neander-checkpoints config inject_previous_context on/off` | Auto-inject past context on session start |

## Skills (inside Claude Code)

Claude auto-invokes these based on conversation context:

| Skill | Description |
|---|---|
| `/neander-status` | Overview of recent checkpoints |
| `/neander-search` | Search checkpoints by keyword, branch, file, date, or natural language |
| `/neander-transcript` | View the condensed conversation transcript |
| `/neander-summarize` | Generate an AI summary and persist it |
| `/neander-session-stats` | Token usage, cost estimate, duration, files modified |
| `/neander-redact` | Scan a transcript for secrets and PII |

## Agents (subagents)

| Agent | Description |
|---|---|
| `neander-code-context` | Researches why code was written by searching checkpoint transcripts. Auto-spawns when Claude reads unfamiliar code or user asks about code history. |

## Features

### Automatic context on session start

When you start a new Claude session on a feature branch, Claude automatically knows what was done before:

```
[neander-checkpoints] Previous work on feat/impl-tasks-from-td:

• Simplify generate_tasks flow — replaced multi-file export with single JSON. (2026-03-28)
  Open: Surgical refinement is LLM-dependent.

• Implement five refinement improvements for generate_tasks. (2026-03-28)
  Open: Patch format must be followed exactly.
```

Controlled by: `neander-checkpoints config inject_previous_context on/off`

### Auto-summarize

Checkpoints are automatically summarized using `claude --print` when created. Summaries are cached in checkpoint metadata and used by the session start context.

Controlled by: `neander-checkpoints config auto_summarize on/off`

### Code context agent

When Claude reads unfamiliar code or is about to refactor, the `neander-code-context` agent searches past checkpoints to explain WHY the code was written that way — the original problem, design reasoning, rejected alternatives, and known trade-offs.

### Transcripts

Clean, readable conversation flow — strips IDE noise, tool results, and thinking blocks.

```
--- 2026-03-22 ---

12:21 [User] Implement the following plan...

12:21 [Assistant] I'll read both files in parallel.

[Tool] Read: modules/chat/chat_websocket_handler.py

[Tool] Edit: modules/chat/chat_websocket_handler.py

[Tool] Bash: Run chat module tests

12:22 [Assistant] Both fixes are done.
```

### AI summaries

Structured summaries with intent, outcome, learnings, friction, and open items. Generated once, persisted to the checkpoint branch, cached across sessions and machines.

### Cross-machine resume

```bash
neander-checkpoints resume <checkpoint-id>
# Fetches transcript from remote → launches claude --resume
```

### Secret redaction

Three-layer detection before transcripts leave your machine:
1. **Shannon entropy** — high-entropy strings (API keys, tokens)
2. **Pattern matching** — 15+ known formats (AWS keys, GitHub PATs, JWTs, connection strings)
3. **PII detection** — emails, phone numbers, SSNs

## Install

```bash
pip install neander-checkpoints
cd /path/to/project
neander-checkpoints install
```

The installer validates prerequisites (git repo, Claude Code, Python 3.10+), then installs:

- **Scripts** — JSONL parser, checkpoint creator, secret redaction, session restore
- **Skills** — 6 auto-invoked skills for searching, viewing, and summarizing checkpoints
- **Agents** — code-context subagent for understanding code history
- **Hooks** — `SessionStart`, `Stop`, and `PostToolUse:Bash` for automatic context injection, checkpointing, and commit linking
- **Permissions** — auto-allow rules so scripts run without approval prompts
- **CLAUDE.md** — instructions telling Claude when to proactively use checkpoint tools

### Uninstall

```bash
cd /path/to/project
neander-checkpoints uninstall
```

## Checkpoint format

Stored on `neander/checkpoints/v1` — a versioned orphan branch that never touches your code history.

```
neander/checkpoints/v1/
├── index.log                          # fast lookup index
├── a3/
│   └── f8b9c1d2e4567890/
│       ├── metadata.json              # checkpoint ID, commit, files, AI summary
│       ├── transcript-<session-1>.jsonl
│       └── transcript-<session-2>.jsonl
```

## Project structure

```
scripts/                     Source scripts (installed into .claude/scripts/)
agents/                      Source agents (installed into .claude/agents/)
  neander-code-context/      Code history research subagent
skills/                      Source skills (installed into .claude/skills/)
  neander-status/            Checkpoints overview
  neander-search/            Search checkpoints
  neander-transcript/        View transcript
  neander-summarize/         AI summary with caching
  neander-session-stats/     Token usage, costs
  neander-redact/            Redact secrets
config/                      Hook configs, CLAUDE.md snippet
src/neander_checkpoints/     pip package (CLI)
tests/                       Tests
build.sh                     Bundle source → package before publishing
```

## Requirements

- Python 3.10+
- Claude Code 2.x
- git

## License

MIT
