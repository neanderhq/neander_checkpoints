# neander_checkpoints

Capture Claude Code sessions alongside your Git history. Understand *why* code changed, not just *what*. Rewind when things go wrong. Resume where you left off — even on a different machine.

Built natively for Claude Code using hooks, skills, and scripts. No external binaries. Install once, works automatically.

## Why

Your git log shows what code changed. But when AI writes your code, the *how* and *why* live in the conversation — prompts, reasoning, tool calls, dead ends, decisions. Without capturing that, you lose context the moment a session ends.

neander_checkpoints solves this:

- **Understand why code changed** — see the full prompt/response transcript and files touched for any checkpoint
- **Recover instantly** — rewind to a known-good checkpoint when an agent goes sideways, resume seamlessly
- **Keep git history clean** — checkpoint data lives on a separate orphan branch, never pollutes your working tree
- **Onboard faster** — show teammates the path from prompt to change to commit
- **Search across checkpoints** — find the checkpoint where you fixed the auth bug, by keyword, branch, file, or just asking in natural language
- **Cross-machine resume** — push checkpoints to remote, pull them on another machine, continue exactly where you left off

## How it works

Once installed, everything is automatic:

1. **You code with Claude** — business as usual
2. **On every commit**, a hook captures the session transcript and metadata as a checkpoint on the `neander/checkpoints/v1` orphan branch
3. **On session end**, a final checkpoint captures everything even if no commits were made
4. **Commits get linked** — a `Claude-Session` trailer is added so you can trace any commit back to the conversation that produced it

When you need context, just ask naturally:

| You say | What happens |
|---|---|
| "What did I do yesterday?" | Claude searches checkpoints, shows relevant results |
| "Why did we make this change?" | Claude finds the checkpoint that touched the file, reads the transcript |
| "Continue what I was doing on feat/attachments" | Claude finds the checkpoint and shows the resume command |
| "Go back to before that change" | Claude lists checkpoints and offers to restore |
| "How much did that checkpoint cost?" | Claude shows token usage and cost estimate |

## Commands

All commands work as Claude Code skills — Claude auto-invokes them based on conversation context. You can also use them explicitly as slash commands.

All commands accept checkpoint IDs (16-char hex like `a3f8b9c1d2e4`), session IDs (UUIDs), or partial IDs.

| Command | Description |
|---|---|
| `/neander-status` | Overview of active sessions and recent checkpoints |
| `/neander-search` | Search checkpoints by keyword, branch, file, date, commit, or natural language |
| `/neander-transcript` | View the condensed conversation transcript for a checkpoint |
| `/neander-summarize` | Generate an AI summary (intent, outcome, learnings, friction, open items) and persist it |
| `/neander-session-stats` | Token usage, cost estimate, duration, files modified for a checkpoint |
| `/neander-resume` | Find a checkpoint and get the `claude --resume` command (cross-machine support) |
| `/neander-rewind` | List checkpoints and restore files to a previous state |
| `/neander-redact` | Scan a transcript for secrets and PII before sharing |

## Features

### Status

Shows the current session and recent checkpoints at a glance.

```
Current: 17e8f125 · opus · feat/impl-tasks-from-td · 0.4k tokens · 0 files
         (not yet checkpointed)

== Checkpoints (18 total) ==

Checkpoint    Commit    Session   Date              Files  Topic
------------  --------  --------  ----------------  -----  -----
dfe7c7132205  70e684cf  37252de3  2026-03-28 13:20  9      Simplify the generate_tasks flow...
b4d88d5d4fe9  70e684cf  37252de3  2026-03-28 13:20  9      (no summary)
7b02e43d74db  67ff5c5c  37252de3  2026-03-28 13:18  9      (no summary)
```

### Search

Find any checkpoint by keyword, branch, file, date, or commit — or just describe what you're looking for.

```
> "find the checkpoint where I fixed the WebSocket reconnection bugs"
> /neander-search OAuth on feat/auth
```

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

12:30 [User] Can we also handle the edge case for...

12:30 [Assistant] Good catch, I'll add validation.

[Tool] Edit: modules/chat/chat_websocket_handler.py
```

### AI summaries

Structured summaries generated once, persisted to the checkpoint branch, cached across sessions and machines.

```
### Intent
Fix two reliability bugs in chat streaming: replay time window and upsert atomicity.

### Outcome
Both fixes implemented and tested.

### Learnings
**Code**:
- `message_repository.py:94-121` — arrayFilters with $set is the right pattern for atomic MongoDB array updates

### Friction
- Unused datetime import needed a second cleanup pass

### Open Items
- Pre-existing test failure needs investigation
```

### Cross-machine resume

Checkpoints are pushed to the remote automatically. On another machine:

```
> /neander-resume <checkpoint-id>
# or just: "continue what I was doing on feat/attachments"
```

The restore script fetches the transcript from the remote and places it in the right location for `claude --resume`.

### Secret redaction

Three-layer detection before transcripts leave your machine:
1. **Shannon entropy** — high-entropy strings (API keys, tokens)
2. **Pattern matching** — 15+ known formats (AWS keys, GitHub PATs, JWTs, connection strings)
3. **PII detection** — emails, phone numbers, SSNs

See [EXAMPLES.md](EXAMPLES.md) for full output examples of every command.

## Checkpoint format

Stored on `neander/checkpoints/v1` — a versioned orphan branch that never touches your code history.

```
neander/checkpoints/v1/
├── index.log                          # fast lookup index
├── a3/
│   └── f8b9c1d2e4567890/
│       ├── metadata.json              # checkpoint ID, session IDs, commit, files, AI summary
│       ├── transcript-<session-1>.jsonl
│       └── transcript-<session-2>.jsonl
```

- **Multi-session** — concurrent sessions on the same commit don't collide
- **Persisted summaries** — AI summaries cached in metadata.json
- **Auto-push** — checkpoints pushed to remote after creation

## Install

```bash
git clone git@github.com:neanderhq/neander_checkpoints.git ~/checkouts/neander_checkpoints
cd ~/checkouts/neander_checkpoints
```

Install into any project:

```bash
./hooks/install.sh /path/to/project
```

That's it. The installer copies scripts, skills, hooks, and permissions into the project's `.claude/` directory. Everything is self-contained — anyone who clones the repo gets it working out of the box.

```bash
# Or install globally (hooks fire in all sessions)
./hooks/install.sh --global
```

### What gets installed

| | Scripts | Skills | Hooks + Permissions | Pre-push | CLAUDE.md |
|---|---|---|---|---|---|
| Project | `<path>/.claude/scripts/` | `<path>/.claude/skills/` | `<path>/.claude/settings.json` | `<path>/.git/hooks/` | appended |
| Global | `~/.claude/scripts/` | `~/.claude/skills/` | `~/.claude/settings.json` | skipped | appended |

- **Scripts** — JSONL parser, checkpoint creator, secret redaction, session restore
- **Skills** — 8 auto-invoked skills that Claude triggers based on conversation context
- **Hooks** — `Stop` and `PostToolUse:Bash` hooks for automatic checkpointing and commit linking
- **Permissions** — auto-allow rules so scripts run without approval prompts
- **CLAUDE.md** — instructions telling Claude when to proactively use checkpoint tools
- **Pre-push hook** — redacts secrets from transcripts before they leave your machine

### Uninstall

```bash
./hooks/uninstall.sh /path/to/project
./hooks/uninstall.sh --global
```

## Project structure

```
scripts/
  parse_jsonl.py         JSONL parser (list, search, status, stats, transcript, files, snapshots)
  checkpoint.sh          Save session to orphan branch (multi-session, auto-push)
  save_summary.sh        Persist AI summary into checkpoint metadata
  restore.sh             Fetch transcript from remote for cross-machine resume
  redact.py              3-layer secret redaction
  link_commit.sh         Add Claude-Session trailer to commits
  detect_commit.sh       Hook: detect git commit → link + checkpoint
  on_stop.sh             Hook: checkpoint on session stop

.claude/skills/          Auto-invoked by Claude based on conversation context
  neander-status/        Active sessions + recent checkpoints
  neander-search/        Search by keyword, branch, file, date, commit
  neander-transcript/    Condensed transcript view
  neander-summarize/     AI summary with caching
  neander-session-stats/ Token usage, costs, duration
  neander-resume/        Resume from checkpoint (cross-machine)
  neander-rewind/        Restore checkpoints
  neander-redact/        Redact secrets (user-invoked only)

hooks/
  hooks_config.json      Hook definitions template
  install.sh             Installer (project or global)
  uninstall.sh           Clean removal
```

## Requirements

- Python 3.10+
- Claude Code 2.x
- git

## License

MIT
