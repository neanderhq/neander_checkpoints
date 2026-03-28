# neander_code_sessions

Session management for Claude Code — checkpoints, summaries, redaction, and rewind built entirely with Claude Code hooks, slash commands, and scripts. No external binaries.

## What it does

Claude Code stores every session as a JSONL transcript under `~/.claude/projects/`. This toolkit turns those raw transcripts into something useful:

- `/neander-status` — Active and recent sessions for the current project
- `/neander-summarize` — AI-generated summary (intent, outcome, learnings, friction, open items)
- `/neander-transcript` — Clean, condensed transcript view (see format below)
- `/neander-session-stats` — Token usage, estimated cost, duration, files modified
- `/neander-rewind` — List checkpoints from all sources and restore files
- `/neander-resume` — Find a session and get the resume command (cross-machine support)
- `/neander-redact` — Scan transcripts for secrets and PII before sharing

All session commands accept arguments to target different sessions:

```
/neander-transcript                  # current session
/neander-transcript current          # current session (explicit)
/neander-transcript list             # list all sessions, pick one
/neander-transcript <session-id>     # specific session by ID
/neander-transcript <path/to/file>   # specific session by file path
```

### Transcript format

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

Date separators only appear when the day changes (useful for overnight sessions). Timestamps on `[User]` and `[Assistant]` entries. Tool results are omitted — only tool calls with a one-line detail.

## Hooks

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
# Install into a project — copies scripts, commands, hooks, and permissions
./hooks/install.sh /path/to/project

# Or everything global (hooks fire in all sessions)
./hooks/install.sh --global
```

This copies everything into the target project's `.claude/` directory so it's self-contained — anyone who clones the repo gets the commands working out of the box.

| | Scripts | Commands | Hooks + Permissions | Pre-push |
|---|---|---|---|---|
| `/path/to/project` | `<path>/.claude/scripts/` | `<path>/.claude/commands/` | `<path>/.claude/settings.json` | `<path>/.git/hooks/` |
| `--global` | `~/.claude/scripts/` | `~/.claude/commands/` | `~/.claude/settings.json` | skipped |

The installer also adds permission rules to `settings.json` so the scripts run without approval prompts.

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
python3 scripts/neander-redact.py --check <path>

# Redact secrets
python3 scripts/neander-redact.py <input.jsonl> <output.jsonl>
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
  status.md           /neander-status slash command
  summarize.md        /neander-summarize slash command
  transcript.md       /neander-transcript slash command
  session-stats.md    /neander-session-stats slash command
  rewind.md           /neander-rewind slash command
  resume.md           /neander-resume slash command
  redact.md           /neander-redact slash command

hooks/
  hooks_config.json   Hook definitions template
  install.sh          Installer (project or global)
  uninstall.sh        Clean removal
```

## Requirements

- Python 3.10+
- Claude Code 2.x
- git (for checkpointing and commit linking)
