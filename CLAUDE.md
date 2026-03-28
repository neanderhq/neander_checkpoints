# neander_code_sessions

Claude Code session management toolkit — checkpoints, summaries, redaction, and rewind built entirely with Claude Code hooks, skills, and scripts.

## Project structure

```
scripts/                — Core logic (Python + Bash)
  parse_jsonl.py        — JSONL parser: list sessions, extract messages/tools/tokens/files/snapshots
  checkpoint.sh         — Save session(s) to neander/checkpoints/v1 orphan branch, auto-push
  save_summary.sh       — Persist AI summary JSON into checkpoint metadata
  restore.sh            — Fetch session transcript from remote for cross-machine resume
  redact.py             — 3-layer secret redaction (entropy, patterns, PII)
  link_commit.sh        — Add Claude-Session trailer to git commits
  detect_commit.sh      — Hook: detect git commit → trigger link_commit + checkpoint

.claude/skills/         — Skills (auto-invoked by Claude based on conversation context)
  neander-status/          — /neander-status: active and recent sessions
  neander-search/          — /neander-search: search by keyword/branch/file/date/commit
  neander-transcript/      — /neander-transcript: condensed transcript
  neander-summarize/       — /neander-summarize: AI summary with caching
  neander-session-stats/   — /neander-session-stats: tokens, costs, duration
  neander-resume/          — /neander-resume: resume session (cross-machine)
  neander-rewind/          — /neander-rewind: list and restore checkpoints
  neander-redact/          — /neander-redact: scan and redact secrets (user-invoked only)

hooks/                  — Installation and config
  hooks_config.json     — Hook definitions (Stop → checkpoint, PostToolUse:Bash → detect commit)
  install.sh            — Install into a target project (copies scripts, skills, hooks, permissions)
  uninstall.sh          — Clean removal
```

## Checkpoint format (neander/checkpoints/v1)

Stored on a versioned orphan branch. Each checkpoint is sharded:

```
<id[:2]>/<id[2:]>/
  metadata.json                    — id, session_ids[], commit_sha, merged_files[], summary
  transcript-<session-id>.jsonl    — one per session (multi-session support)
```

- `summary` is null until `/neander-summarize` generates and persists it via `save_summary.sh`
- `index.log` at branch root maps checkpoint_id|session_id|commit_sha|timestamp for fast lookup
- Auto-pushed to remote after every checkpoint creation

## Installation

```bash
./hooks/install.sh /path/to/project   # copies scripts + skills + hooks + permissions
./hooks/install.sh --global           # everything into ~/.claude/
```

Uninstall:
```bash
./hooks/uninstall.sh /path/to/project
./hooks/uninstall.sh --global
```

## Key flows

### Checkpointing
1. `Stop` hook or `PostToolUse:Bash` (on git commit) triggers `checkpoint.sh`
2. `checkpoint.sh` switches to orphan branch, writes transcript + metadata, commits, pushes
3. `detect_commit.sh` also runs `link_commit.sh` to add Claude-Session trailer to the commit

### Cross-machine resume
1. User runs `/neander-resume <session-id>` on machine B
2. Session not found locally → `restore.sh` fetches `neander/checkpoints/v1` from remote
3. Finds session in index.log or metadata, extracts transcript to `~/.claude/projects/`
4. User runs `claude --resume <session-id>`

### AI summary caching
1. `/neander-summarize` checks `metadata.summary` on checkpoint branch
2. If cached and not `--force`, displays cached summary
3. If generating fresh, produces structured JSON (intent, outcome, learnings, friction, open_items)
4. `save_summary.sh` writes summary into metadata.json, commits, pushes

## Scripts can also be used standalone

```bash
python3 scripts/parse_jsonl.py list
python3 scripts/parse_jsonl.py stats --session <path>
python3 scripts/parse_jsonl.py transcript --session <path>
python3 scripts/redact.py --check <path>
```
