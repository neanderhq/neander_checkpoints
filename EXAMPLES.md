# Command Examples

## /neander-status

Shows recent sessions for the current project at a glance.

```
> /neander-status

Project: neander_backend · Branch: feat/attachments
Checkpoints: enabled

Recent Sessions

claude-opus-4-6 · 0647b6e9
> "Implement the following plan: Two Chat Streaming..."
refactor/unify-intake · 5d ago · 45.2k tokens

claude-opus-4-6 · 508dd1d0
> "Fix the WebSocket reconnection bug where messages..."
feat/ws-reliability · 6d ago · 128.7k tokens

claude-opus-4-6 · b3ced0ec
> "Refactor the intake service to use the new unified..."
refactor/unify-intake · 6d ago · 89.3k tokens

To resume: claude --resume 0647b6e9-6231-422f-8f9b-f14a4300becd
To view transcript: /neander-transcript 0647b6e9
```

---

## /neander-transcript

### Current session
```
> /neander-transcript

--- 2026-03-22 ---

12:21 [User] Implement the following plan: Two Chat Streaming Reliability Fixes...

12:21 [Assistant] I'll read both files in parallel to understand the current code.

[Tool] Read: modules/chat/chat_websocket_handler.py

[Tool] Read: modules/chat/repositories/message_repository.py

12:21 [Assistant] I'll implement both fixes in parallel.

[Tool] Edit: modules/chat/chat_websocket_handler.py

[Tool] Edit: modules/chat/repositories/message_repository.py

[Tool] Bash: Run chat module tests

12:22 [Assistant] Both fixes are done. The failing test is pre-existing and unrelated.

12:23 [User] both 1 and 2

12:24 [Assistant] I'll address both workflow session recovery and WebSocket...
```

### List mode
```
> /neander-transcript list

  0647b6e9-623...  2026-03-22 18:15    1780.1KB
  b3ced0ec-a26...  2026-03-22 17:51    5943.4KB
  508dd1d0-e9f...  2026-03-26 11:49   32846.7KB

Which session? > 0647b6e9
```

### Filter by session ID
```
> /neander-transcript 508dd1d0

--- 2026-03-26 ---

11:49 [User] The WebSocket connection drops when switching conversations...
...
```

---

## /neander-summarize

```
> /neander-summarize 0647b6e9

Session: delightful-noodling-sprout (0647b6e9)
Branch: refactor/unify-intake-service-and-models
Duration: 12:21 → 12:45 (24 minutes)
Tokens: 4,419 (34 in / 4,385 out)

### Intent
Fix two reliability bugs in chat streaming: replay only working within
60 seconds, and tool call upserts creating duplicates under concurrency.

### Outcome
Both fixes implemented and tested. Replay now works regardless of time
window, and upserts use MongoDB arrayFilters for atomic operations.

### Learnings
**Repository**:
- Chat WebSocket handler uses a `_needs_replay()` predicate to decide
  message replay on reconnect

**Code**:
- `message_repository.py:94-121` — The original two-step upsert
  (query + push) was not atomic; arrayFilters with $set is the right
  pattern for MongoDB array element updates

**Workflow**:
- One pre-existing test failure in chat module (unrelated to changes)

### Friction
- `datetime` import was left unused after removing REPLAY_WINDOW,
  needed a second pass to clean up

### Open Items
- Pre-existing test `test_processing_error_sends_message_failed_event`
  still failing — unrelated but should be investigated
```

---

## /neander-session-stats

```
> /neander-session-stats current

Session:  0647b6e9-6231-422f-8f9b-f14a4300becd
Slug:     delightful-noodling-sprout
Branch:   refactor/unify-intake-service-and-models
CWD:      /Users/sourab/checkouts/neander_backend
Models:   claude-opus-4-6
Duration: 12:21:45 → 12:45:29 (24 min)
Messages: 4 user, 55 assistant
Tokens:   4,419 total (34 in, 4,385 out)
Cache:    1,325,921 read, 82,981 created
Est cost: ~$0.07 input + $0.33 output = $0.40

Files modified (3):
  modules/chat/chat_websocket_handler.py
  modules/chat/repositories/message_repository.py
  .claude/plans/delightful-noodling-sprout.md

Snapshots: 6 checkpoints
```

---

## /neander-resume

### Most recent session
```
> /neander-resume

Most recent session for this project:

Session:  508dd1d0-e9f2-4a3b-9c1d-7f8e6a5b4c3d
Branch:   feat/ws-reliability
Last prompt: "Fix the WebSocket reconnection bug where messages from..."
Duration: 3h 42min session, ended 2d ago
Tokens:   128,700
Files:    8 modified

To resume:
  claude --resume 508dd1d0-e9f2-4a3b-9c1d-7f8e6a5b4c3d
```

### By branch
```
> /neander-resume feat/attachments

Found 2 sessions on feat/attachments:

1. a79e08a0 — "Implement attachment.ts types, useAttachments hook..."
   3h session, ended 1d ago, 89.3k tokens

2. 7b6d0881 — "Fix drag-and-drop not working on Safari..."
   45min session, ended 1d ago, 12.1k tokens

Which session? > 1

To resume:
  claude --resume a79e08a0-0145-4b2c-8d3e-9f7a6c5b4e2d
```

---

## /neander-rewind

```
> /neander-rewind

Available checkpoints:

  1. [git commit]  835718b  2h ago   "feat: consolidate WebSocket hooks"
  2. [git commit]  73fe767  4h ago   "feat: add mermaid diagram support"
  3. [snapshot]    snap-3   6h ago   3 files backed up
  4. [git commit]  a1b2c3d  1d ago   "fix: cross-conversation message leak"

Select checkpoint (1-4) or cancel: > 2

Checkpoint 73fe767 — "feat: add mermaid diagram support"
Files in this checkpoint:
  - src/components/DocumentPanel.tsx
  - package.json

Options:
  1. Restore files (overwrites current versions)
  2. View only (show file contents)
  3. Cancel

> 1

Restored 2 files from checkpoint 73fe767.
To resume the session: claude --resume abc123-session-id
```

---

## /neander-redact

```
> /neander-redact current

Scanning session for secrets and PII...

Found 3 potential secrets:

  pattern  line 42   AWS Access Key (AKIA...)
  pattern  line 187  Database connection string (mongodb://...)
  pii      line 305  Email address

Redact these findings? (y/n) > y

Redacted 3 findings → ~/.claude/projects/.../session.redacted.jsonl
```
