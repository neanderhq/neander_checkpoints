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

.claude/commands/ — Slash command skills (all prefixed with neander-)
  neander-status.md        — /neander-status: active and recent sessions
  neander-summarize.md     — /neander-summarize: AI-generated session summary
  neander-transcript.md    — /neander-transcript: condensed readable transcript
  neander-session-stats.md — /neander-session-stats: tokens, costs, duration, files
  neander-rewind.md        — /neander-rewind: list and restore checkpoints
  neander-resume.md        — /neander-resume: resume session from checkpoint
  neander-redact.md        — /neander-redact: scan and redact secrets

hooks/            — Installation and config
  hooks_config.json — Hook definitions (Stop → checkpoint, PostToolUse:Bash → link commit)
  install.sh      — Install into a target project (copies scripts, commands, hooks, permissions)
  uninstall.sh    — Clean removal
```

## Installation

```bash
./hooks/install.sh /path/to/project

# Or everything global
./hooks/install.sh --global
```

Uninstall:
```bash
./hooks/uninstall.sh /path/to/project
./hooks/uninstall.sh --global
```

## Scripts can also be used standalone

```bash
python3 scripts/parse_jsonl.py list
python3 scripts/parse_jsonl.py stats --session <path>
python3 scripts/parse_jsonl.py transcript --session <path>
python3 scripts/redact.py --check <path>
```
