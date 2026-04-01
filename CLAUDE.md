# neander_checkpoints

Checkpoint management for Claude Code sessions — captures, searches, and resurfaces past session context automatically.

**IMPORTANT:** Do NOT commit or push changes unless explicitly asked by the user. Wait for user to request `git commit` or `git push`.

## Project structure

```
scripts/                     Source scripts
  parse_jsonl.py             JSONL parser (checkpoint-centric, reads from git branch)
  checkpoint.sh              Save session to orphan branch, auto-push, auto-summarize
  auto_summarize.sh          Generate summary via claude --print
  save_summary.sh            Persist summary JSON into checkpoint metadata
  persist_summary.sh         Wrapper for save via stdin
  restore.sh                 Fetch transcript from remote for cross-machine resume
  redact.py                  3-layer secret redaction
  link_commit.sh             Add Claude-Session trailer to commits
  detect_commit.sh           Hook: detect git commit → link + checkpoint
  on_stop.sh                 Hook: checkpoint on session stop
  on_session_start.sh        Hook: inject past checkpoint context
  get_branch_context.py      Read checkpoint summaries for current branch

agents/                      Subagents (run in isolated context)
  neander-code-context/      Research why code was written from checkpoint history

skills/                      Skills (run in main context)
  neander-status/            Checkpoints overview
  neander-search/            Search checkpoints
  neander-transcript/        View transcript
  neander-summarize/         AI summary with caching
  neander-session-stats/     Token usage, costs
  neander-redact/            Redact secrets (user-invoked only)

config/                      Hook configs, CLAUDE.md snippet
src/neander_checkpoints/     pip package (install, uninstall, resume, config CLI)
tests/                       Tests
build.sh                     Bundle source → package before publishing
```

## Key flows

### Session start → context injection
1. `SessionStart` hook runs `on_session_start.sh`
2. `get_branch_context.py` reads checkpoint summaries for current branch
3. Outputs past work context → Claude Code injects into session

### Checkpointing
1. `Stop` hook or `PostToolUse:Bash` (on git commit) triggers `checkpoint.sh`
2. Writes transcript + metadata to orphan branch, commits, pushes
3. If `auto_summarize` is on, runs `claude --print` to generate summary

### Code context agent
1. Claude reads unfamiliar code or user asks "why was this done?"
2. `neander-code-context` agent auto-spawns
3. Searches checkpoint branch for checkpoints that modified the file
4. Returns distilled reasoning from transcripts

### Cross-machine resume
1. `neander-checkpoints resume <id>` on another machine
2. Resolves checkpoint → session ID → fetches transcript from remote
3. Launches `claude --resume <session-id>`

## Settings

Stored in `.claude/neander-checkpoints.json`:
- `inject_previous_context` (default: on) — inject past summaries on session start
- `auto_summarize` (default: on) — auto-generate summaries on checkpoint creation

Manage with: `neander-checkpoints config`
