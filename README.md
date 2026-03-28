# neander_code_sessions

Session management for Claude Code — checkpoints, summaries, redaction, and rewind built entirely with Claude Code hooks, slash commands, and scripts. No external binaries.

## What it does

Claude Code stores every session as a JSONL transcript under `~/.claude/projects/`. This toolkit turns those raw transcripts into something useful:

- `/neander-status` — Active and recent sessions for the current project
- `/neander-search` — Search across sessions by keyword, branch, file, date, commit, or natural language
- `/neander-transcript` — Clean, condensed transcript view (see format below)
- `/neander-summarize` — AI-generated summary with caching (intent, outcome, learnings, friction, open items)
- `/neander-session-stats` — Token usage, estimated cost, duration, files modified
- `/neander-resume` — Find a session and get the resume command (cross-machine support)
- `/neander-rewind` — List checkpoints from all sources and restore files
- `/neander-redact` — Scan transcripts for secrets and PII before sharing

All session skills accept arguments to target different sessions:

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

See [EXAMPLES.md](EXAMPLES.md) for full output examples of every command.

## Hooks

Automatic hooks handle:
- **Checkpointing** — saves transcript + metadata to the `neander/checkpoints/v1` orphan branch on every commit and session stop, pushes to remote automatically
- **Commit linking** — adds `Claude-Session` trailers to commits so you can trace code back to the AI conversation that wrote it
- **Pre-push redaction** — strips secrets from transcripts before they leave your machine
- **Cross-machine resume** — `/neander-resume` fetches session transcripts from the checkpoint branch on the remote via `restore.sh`

## Install

```bash
git clone git@github.com:NeanderAI/neander_checkpoints.git ~/checkouts/neander_checkpoints
cd ~/checkouts/neander_checkpoints
```

Then install into a project:

```bash
# Install into a project — copies scripts, skills, hooks, and permissions
./hooks/install.sh /path/to/project

# Or everything global (hooks fire in all sessions)
./hooks/install.sh --global
```

This copies everything into the target project's `.claude/` directory so it's self-contained — anyone who clones the repo gets the skills working out of the box.

| | Scripts | Skills | Hooks + Permissions | Pre-push | CLAUDE.md |
|---|---|---|---|---|---|
| `/path/to/project` | `<path>/.claude/scripts/` | `<path>/.claude/skills/` | `<path>/.claude/settings.json` | `<path>/.git/hooks/` | appended |
| `--global` | `~/.claude/scripts/` | `~/.claude/skills/` | `~/.claude/settings.json` | skipped | appended |

The installer also:
- Adds permission rules to `settings.json` so scripts run without approval prompts
- Appends session management instructions to the project's `CLAUDE.md`

### Skills vs commands

These are installed as **skills** (`.claude/skills/name/SKILL.md`), not commands. The difference: skills have a `description` field that Claude matches against conversation context, so **Claude auto-invokes them without the user typing a slash command**.

For example, when the user says "what did I do yesterday?", Claude recognizes this matches the `neander-search` skill description and automatically runs the session search — no `/neander-search` needed.

| Trigger | What happens |
|---|---|
| "What did I do yesterday?" | Claude auto-invokes `neander-search` |
| "What was that session where I fixed the auth bug?" | Claude auto-invokes `neander-search` |
| "Why did we make this change?" | Claude searches sessions that touched the file |
| "Continue what I was doing on feat/attachments" | Claude auto-invokes `neander-resume` |
| "Go back to before that change" | Claude auto-invokes `neander-rewind` |
| "How much did that session cost?" | Claude auto-invokes `neander-session-stats` |

The slash commands (`/neander-search`, `/neander-transcript`, etc.) still work for explicit use.

`neander-redact` has `disable-model-invocation: true` — it modifies files, so the user must invoke it explicitly.

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

# Search sessions
python3 scripts/parse_jsonl.py search --project /path/to/project --keyword "text" --branch "name" --file "path"

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

### Checkpoint format

Checkpoints are stored on the `neander/checkpoints/v1` orphan branch — a branch with no shared history with your code, so it never pollutes your working tree. The `/v1` suffix is for schema versioning.

Checkpoints are created at two points:
1. **Every git commit** (`PostToolUse:Bash` hook) — detects `git commit` in tool output, links the commit via a `Claude-Session` trailer, and snapshots the transcript in the background
2. **Session end** (`Stop` hook) — catch-all that ensures every session is captured even if no commits were made

Each checkpoint is stored in a sharded directory (`<id[:2]>/<id[2:]>/`):

```
neander/checkpoints/v1/               # orphan branch
├── README.md
├── index.log                          # checkpoint_id|session_id|commit_sha|timestamp
├── a3/
│   └── f8b9c1d2e4567890/
│       ├── metadata.json
│       ├── transcript-<session-id-1>.jsonl
│       └── transcript-<session-id-2>.jsonl   # multi-session support
└── b7/
    └── ...
```

**metadata.json**:
```json
{
  "id": "a3f8b9c1d2e45678",
  "session_ids": ["0647b6e9-6231-...", "b3ced0ec-a260-..."],
  "commit_sha": "835718b",
  "created_at": "2026-03-22T12:45:00Z",
  "merged_files": ["modules/chat/handler.py", "modules/chat/repo.py"],
  "summary": {
    "intent": "Fix two reliability bugs in chat streaming",
    "outcome": "Both fixes implemented and tested",
    "learnings": {
      "repo": ["Chat handler uses _needs_replay() for reconnect"],
      "code": [{"path": "message_repository.py", "lines": "94-121", "finding": "..."}],
      "workflow": ["One pre-existing test failure unrelated to changes"]
    },
    "friction": ["Unused datetime import needed a second cleanup pass"],
    "open_items": ["Pre-existing test failure needs investigation"]
  }
}
```

Key features:
- **Multi-session** — each transcript is namespaced as `transcript-<session_id>.jsonl`, so concurrent sessions on the same commit don't collide
- **Persisted AI summaries** — `/neander-summarize` saves its output to `metadata.summary`, cached across sessions and machines
- **Auto-push** — checkpoints are pushed to remote after creation, enabling cross-machine resume
- **Versioned schema** — `/v1` branch allows future format changes without breaking existing data

### Secret redaction

Three-layer detection applied before pushing transcripts:
1. **Shannon entropy** — flags high-entropy strings (threshold 4.5, min 16 chars)
2. **Pattern matching** — 15+ known formats (AWS keys, GitHub PATs, JWTs, connection strings, etc.)
3. **PII detection** — emails, phone numbers, SSNs

## Project structure

```
scripts/
  parse_jsonl.py      Core JSONL parser
  checkpoint.sh       Save session to git orphan branch (multi-session, auto-push)
  save_summary.sh     Persist AI summary into checkpoint metadata
  restore.sh          Fetch session transcript from remote for cross-machine resume
  redact.py           3-layer secret redaction
  link_commit.sh      Add Claude-Session trailer to commits
  detect_commit.sh    Hook: detect git commit, trigger linking + checkpoint

.claude/skills/              Auto-invoked by Claude based on conversation context
  neander-status/            Recent sessions overview
  neander-search/            Search by keyword, branch, file, date, commit
  neander-transcript/        Condensed transcript view
  neander-summarize/         AI summary with caching
  neander-session-stats/     Token usage, costs, duration
  neander-resume/            Resume session (cross-machine)
  neander-rewind/            Restore checkpoints
  neander-redact/            Redact secrets (user-invoked only)

hooks/
  hooks_config.json   Hook definitions template
  install.sh          Installer (project or global)
  uninstall.sh        Clean removal
```

## Requirements

- Python 3.10+
- Claude Code 2.x
- git (for checkpointing and commit linking)
