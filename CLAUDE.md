# neander_code_sessions

Claude Code session management toolkit — checkpoints, summaries, redaction, and rewind built entirely with Claude Code hooks, skills, and scripts.

## Project structure

```
scripts/          — Core logic (Python + Bash)
  parse_jsonl.py  — JSONL parser: list sessions, extract messages/tools/tokens/files/snapshots
  checkpoint.sh   — Save session to git orphan branch (claude-sessions/checkpoints)
  redact.py       — 3-layer secret redaction (entropy, patterns, PII)
  link_commit.sh  — Add Claude-Session trailer to git commits
  detect_commit.sh— Hook: detect git commit in Bash output, trigger link_commit

.claude/commands/ — Slash command skills
  summarize.md    — /summarize: AI-generated session summary
  transcript.md   — /transcript: condensed readable transcript
  session-stats.md— /session-stats: tokens, costs, duration, files
  rewind.md       — /rewind: list and restore checkpoints
  resume.md       — /resume: resume session from checkpoint
  redact.md       — /redact: scan and redact secrets

hooks/            — Installation and config
  hooks_config.json — Hook definitions (Stop → checkpoint, PostToolUse:Bash → link commit)
  install.sh      — Install into a target project (symlinks commands, merges hooks, adds pre-push)
  uninstall.sh    — Clean removal
```

## Installation

```bash
# Commands go global, hooks scoped to target project
./hooks/install.sh /path/to/project

# Or everything global
./hooks/install.sh --global
```

Uninstall:
```bash
./hooks/uninstall.sh /path/to/project
./hooks/uninstall.sh --global
```

## Slash commands

Once installed, use in any Claude Code session:
- `/summarize` — AI-generated session summary (intent, outcome, decisions, open items)
- `/transcript` — condensed readable transcript
- `/session-stats` — token usage, costs, duration, files
- `/rewind` — list and restore checkpoints
- `/resume` — resume session from checkpoint
- `/redact` — scan and redact secrets from transcripts

## Scripts can also be used standalone

```bash
python3 scripts/parse_jsonl.py list
python3 scripts/parse_jsonl.py stats --session <path>
python3 scripts/parse_jsonl.py transcript --session <path>
python3 scripts/redact.py --check <path>
```
