# neander_code_sessions

Session management for Claude Code — checkpoints, summaries, redaction, and rewind built entirely with Claude Code hooks, slash commands, and scripts. No external binaries.

## What it does

Claude Code stores every session as a JSONL transcript under `~/.claude/projects/`. This toolkit turns those raw transcripts into something useful:

- `/summarize` — AI-generated summary of any session (intent, outcome, key decisions, open items)
- `/transcript` — Clean, condensed transcript view stripped of noise
- `/session-stats` — Token usage, estimated cost, duration, files modified
- `/rewind` — List checkpoints and restore files to a previous state
- `/resume` — Find and resume a session from a checkpoint (even cross-machine)
- `/redact` — Scan transcripts for secrets and PII before sharing

Automatic hooks handle:
- **Checkpointing** — saves transcript + metadata to a git orphan branch on every commit and on session stop, so you never lose context
- **Commit linking** — adds `Claude-Session` trailers to commits so you can trace code back to the AI conversation that wrote it
- **Pre-push redaction** — strips secrets from transcripts before they leave your machine

## Install

```bash
git clone <this-repo> ~/checkouts/neander_code_sessions
cd ~/checkouts/neander_code_sessions
```

Then install into a project:

```bash
# Commands go global (~/.claude/commands/), hooks scoped to the target project
./hooks/install.sh /path/to/project

# Or everything global (hooks fire in all sessions)
./hooks/install.sh --global
```

This copies scripts, commands, and hooks into the target project's `.claude/` directory so everything is self-contained and works for anyone who clones the repo.

| Mode | Scripts | Commands | Hooks | Pre-push |
|---|---|---|---|---|
| `/path/to/project` | `<path>/.claude/scripts/` | `<path>/.claude/commands/` | `<path>/.claude/settings.json` | `<path>/.git/hooks/` |
| `--global` | `~/.claude/scripts/` | `~/.claude/commands/` | `~/.claude/settings.json` | skipped |

## Uninstall

```bash
./hooks/uninstall.sh /path/to/project
./hooks/uninstall.sh --global
```

## Standalone CLI usage

The parser works without installation:

```bash
# List all sessions
python3 scripts/parse_jsonl.py list

# List sessions for a specific project
python3 scripts/parse_jsonl.py list --project /path/to/project

# Session stats (tokens, duration, files)
python3 scripts/parse_jsonl.py stats --session ~/.claude/projects/<dir>/<id>.jsonl

# Condensed transcript
python3 scripts/parse_jsonl.py transcript --session <path>

# Files modified in a session
python3 scripts/parse_jsonl.py files --session <path>

# File snapshots / checkpoints
python3 scripts/parse_jsonl.py snapshots --session <path>

# Check for secrets (dry run)
python3 scripts/redact.py --check <path>

# Redact secrets
python3 scripts/redact.py <input.jsonl> <output.jsonl>
```

## How it works

Claude Code sessions are stored as JSONL files with 6 object types:

| Type | Purpose |
|---|---|
| `user` | Your messages and tool results |
| `assistant` | Claude's responses (text, thinking, tool calls) |
| `progress` | Tool execution progress (hooks, bash, agents) |
| `file-history-snapshot` | File state backups for undo |
| `queue-operation` | Messages queued while Claude was busy |
| `system` | Turn duration and metadata |

The parser extracts structured data from these: messages, tool calls, token usage (deduplicated), modified files, and file snapshots.

### Checkpointing

The checkpoint system stores transcripts on a `claude-sessions/checkpoints` orphan branch — a branch with no shared history with your code, so it never pollutes your working tree. Checkpoints are created at two points:

1. **Every git commit** (`PostToolUse:Bash` hook) — detects `git commit` in tool output, links the commit via a `Claude-Session` trailer, and snapshots the transcript in the background
2. **Session end** (`Stop` hook) — catch-all that ensures every session is captured even if no commits were made

Checkpoints are stored in sharded directories (`<id[:2]>/<id[2:]>/`) for scalability, each containing:
- `transcript.jsonl` — full session transcript
- `metadata.json` — session ID, commit SHA, token stats, timestamps
- `condensed.txt` — human-readable summary

Secret redaction uses three layers:
1. **Shannon entropy** — flags high-entropy strings (threshold 4.5, min 16 chars)
2. **Pattern matching** — 15+ known formats (AWS keys, GitHub PATs, JWTs, connection strings, etc.)
3. **PII detection** — emails, phone numbers, SSNs

## Project structure

```
scripts/
  parse_jsonl.py      Core JSONL parser
  checkpoint.sh       Save session to git orphan branch
  redact.py           3-layer secret redaction
  link_commit.sh      Add Claude-Session trailer to commits
  detect_commit.sh    Hook: detect git commit, trigger linking + checkpoint

.claude/commands/
  summarize.md        /summarize slash command
  transcript.md       /transcript slash command
  session-stats.md    /session-stats slash command
  rewind.md           /rewind slash command
  resume.md           /resume slash command
  redact.md           /redact slash command

hooks/
  hooks_config.json   Hook definitions template
  install.sh          Installer (project or global)
  uninstall.sh        Clean removal
```

## Requirements

- Python 3.10+
- Claude Code 2.x
- git (for checkpointing and commit linking)
