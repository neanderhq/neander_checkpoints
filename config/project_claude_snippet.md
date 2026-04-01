## Checkpoint Management (neander_checkpoints)

This project has checkpoint management tools installed in `.claude/scripts/`, `.claude/skills/`, and `.claude/agents/`.

### IMPORTANT: Use skills and agents, not raw scripts

When the user asks about checkpoints, summaries, transcripts, or history, **invoke the corresponding skill or agent** — do NOT try to do it yourself with raw git commands or scripts.

| User says | Use |
|---|---|
| "summarize checkpoint ..." | Skill: `/neander-summarize` |
| "show transcript ...", "what happened in ..." | Skill: `/neander-transcript` |
| "search checkpoints ...", "find the checkpoint where ..." | Skill: `/neander-search` |
| "what did I do yesterday/last week" | Skill: `/neander-search` |
| "checkpoint stats", "how much did it cost" | Skill: `/neander-session-stats` |
| "recent checkpoints", "what's been going on" | Skill: `/neander-status` |
| "why was this done this way?", understanding code | Agent: `neander-code-context` (auto-spawns) |
| about to refactor unfamiliar code | Agent: `neander-code-context` (auto-spawns) |

### When to use these tools proactively

- **You're reading code and don't understand a design choice** → the `neander-code-context` agent should auto-spawn. If it doesn't, spawn it yourself via the Agent tool.
- **User asks "why was this done this way?"** → let `neander-code-context` agent handle it
- **User asks about previous work** → invoke `/neander-search`
- **User asks about code history beyond git** → invoke `/neander-search`, then `/neander-transcript`
- **User seems lost or is re-doing work** → invoke `/neander-search` to check if a previous checkpoint solved this
- **You're about to refactor code** → let `neander-code-context` agent research the original intent first

### Available scripts (for direct use only when skills/agents don't cover the case)

```bash
python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <cwd>
python3 __SCRIPTS_DIR__/parse_jsonl.py search --project <cwd> --keyword "text" --branch "name" --fetch
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --checkpoint <checkpoint-id>
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --checkpoint <checkpoint-id>
bash __SCRIPTS_DIR__/restore.sh <session-id> <cwd>
```
