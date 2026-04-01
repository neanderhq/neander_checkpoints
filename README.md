# neander_checkpoints

Every Claude Code session tells a story — the problem, the reasoning, the dead ends, the decisions. Your git log only captures the ending. neander_checkpoints captures the whole thing.

## The problem

You spend an hour with Claude refactoring the auth module. Three days later, you're back on the same branch and Claude has no idea what happened. You have to re-explain everything.

Your teammate used Claude to build the payment integration. The code works but you don't understand why they chose Stripe webhooks over polling. `git blame` tells you *who* and *when* — but not *why*.

You ask Claude to refactor the database layer. Halfway through, you realize it's going in the wrong direction. You want to go back to 20 minutes ago, but `git stash` loses everything.

## How neander_checkpoints helps

### Claude remembers across sessions

Start a new session on `feat/payments` and Claude already knows:

```
[neander-checkpoints] Previous work on feat/payments:

• Implement Stripe webhook handler for payment confirmations. (2026-03-28)
  Open: Retry logic for failed webhooks not yet implemented.

• Add idempotency keys to prevent duplicate charges. (2026-03-29)
  Open: Need to handle edge case where webhook arrives before redirect.
```

No re-explaining. Claude picks up where you (or your teammate) left off.

### Claude knows why code was written

You're reading `payment_handler.py` and see a complex retry mechanism. Instead of guessing, Claude automatically looks up the checkpoint where it was written and tells you:

> "This was added in checkpoint a3f8b9c1 on March 28. The user reported that Stripe webhooks were arriving out of order, causing duplicate charge attempts. The retry mechanism with exponential backoff was chosen over a simple queue because the team needed it deployed same-day without infrastructure changes."

### Search across all past sessions

```
> find the session where we discussed the webhook ordering problem

Found 3 results:

Checkpoint    Session   Date        Topic
a3f8b9c1d2e4  b64e871e  2026-03-28  Implement Stripe webhook handler
dfe7c7132205  37252de3  2026-03-29  Fix webhook ordering edge case
```

### Resume from any machine

Your laptop died. On a new machine:

```bash
neander-checkpoints resume a3f8b9c1d2e4
# Fetches transcript from remote → launches claude --resume
```

Claude opens with the full conversation context from that session.

## How it works

Install once, everything is automatic:

1. **You code with Claude** — business as usual
2. **On every commit**, the session transcript is saved as a checkpoint
3. **On session end**, a final checkpoint captures everything
4. **On next session start**, Claude gets context from past checkpoints on this branch
5. **When reading code**, a subagent can look up why any piece of code was written

Checkpoints live on a `neander/checkpoints/v1` orphan branch — separate from your code, pushed to remote automatically, available across machines.

## Install

```bash
pip install neander-checkpoints
cd /path/to/project
neander-checkpoints install
```

Validates prerequisites (git repo, Claude Code, Python 3.10+), then installs scripts, skills, agents, hooks, and permissions into `.claude/`. Self-contained — anyone who clones the repo gets it working.

### Uninstall

```bash
neander-checkpoints uninstall
```

## CLI

| Command | Description |
|---|---|
| `neander-checkpoints install` | Set up a project |
| `neander-checkpoints uninstall` | Remove from a project |
| `neander-checkpoints resume [id]` | List checkpoints or launch `claude --resume` |
| `neander-checkpoints config` | View or change settings |

### Settings

| Setting | Default | Description |
|---|---|---|
| `inject_previous_context` | on | Inject past checkpoint summaries on session start |
| `auto_summarize` | on | Auto-generate summaries when checkpoints are created |

```bash
neander-checkpoints config                              # show all
neander-checkpoints config inject_previous_context off  # disable
```

## What gets installed

### Skills (Claude auto-invokes)

| Skill | When it triggers |
|---|---|
| `/neander-status` | "what's been going on", "recent checkpoints" |
| `/neander-search` | "find the session where...", "what did I do yesterday" |
| `/neander-transcript` | "show me what happened in that session" |
| `/neander-summarize` | "summarize this checkpoint" |
| `/neander-session-stats` | "how much did that cost", "token usage" |
| `/neander-redact` | "scan for secrets before sharing" (user-invoked only) |

### Agents (subagents)

| Agent | When it triggers |
|---|---|
| `neander-code-context` | Claude reads unfamiliar code, user asks "why was this done this way", about to refactor |

### Hooks

| Hook | What it does |
|---|---|
| `SessionStart` | Injects past checkpoint context into new sessions |
| `Stop` | Creates a checkpoint when session ends |
| `PostToolUse:Bash` | Creates a checkpoint on git commits, links commits to sessions |

## Checkpoint format

Stored on `neander/checkpoints/v1` — a versioned orphan branch.

```
neander/checkpoints/v1/
├── index.log                          # checkpoint_id|session_id|commit_sha|timestamp
├── a3/
│   └── f8b9c1d2e4567890/
│       ├── metadata.json              # commit, files, AI summary
│       └── transcript-<session>.jsonl # full conversation
```

Each checkpoint has:
- **Transcript** — full conversation (prompts, responses, tool calls)
- **Metadata** — commit SHA, files modified, timestamps
- **Summary** — AI-generated intent, outcome, learnings, friction, open items (auto-generated or on-demand)

## Project structure

```
scripts/       Source scripts
agents/        Source agents (neander-code-context)
skills/        Source skills (status, search, transcript, summarize, stats, redact)
config/        Hook configs, CLAUDE.md snippet
src/           pip package (CLI)
tests/         Tests
build.sh       Bundle source → package before publishing
```

## Requirements

- Python 3.10+
- Claude Code 2.x
- git

## License

MIT
