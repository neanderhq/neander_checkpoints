## Checkpoint Management (neander_checkpoints)

This project has checkpoint management tools installed in `.claude/scripts/` and `.claude/skills/`.

### IMPORTANT: Always use skills, not raw scripts

When the user asks about checkpoints, sessions, summaries, transcripts, or history, **invoke the corresponding skill using the Skill tool** — do NOT try to do it yourself with raw git commands or scripts. The skills handle persistence and formatting correctly.

| User says | Invoke this skill |
|---|---|
| "summarize checkpoint ..." | `/neander-summarize` |
| "show transcript ...", "what happened in ..." | `/neander-transcript` |
| "search checkpoints ...", "find the checkpoint where ..." | `/neander-search` |
| "what did I do yesterday/last week" | `/neander-search` |
| "checkpoint stats", "how much did it cost" | `/neander-session-stats` |
| "resume ...", "continue where I left off" | `/neander-resume` |
| "go back", "rewind", "restore checkpoint" | `/neander-rewind` |
| "recent checkpoints", "what's been going on" | `/neander-status` |

### When to use these tools proactively

You don't need to wait for the user to run a slash command. Use the skills naturally when the context calls for it:

- **User asks about previous work** → invoke `/neander-search`
- **User references a past checkpoint or session** → invoke `/neander-resume` or `/neander-rewind`
- **User asks about code history beyond git** → invoke `/neander-search`, then `/neander-transcript`
- **User seems lost or is re-doing work** → invoke `/neander-search` to check if a previous checkpoint solved this

### Available scripts (for direct use only when skills don't cover the case)

All commands read from the git checkpoint branch. Use `--fetch` to pull remote data first. The primary flag is `--checkpoint`/`-c` (`--session`/`-s` still works as alias).

```bash
python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <cwd>
python3 __SCRIPTS_DIR__/parse_jsonl.py search --project <cwd> --keyword "text" --branch "name" --fetch
python3 __SCRIPTS_DIR__/parse_jsonl.py stats --checkpoint <checkpoint-id>
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --checkpoint <checkpoint-id>
bash __SCRIPTS_DIR__/restore.sh <session-id> <cwd>
```
