## Session Management (neander_code_sessions)

This project has session management tools installed in `.claude/scripts/` and `.claude/commands/`.

### When to use these tools proactively

You don't need to wait for the user to run a slash command. Use these tools naturally when the context calls for it:

- **User asks about previous work** ("what did I do yesterday", "what was that session where I fixed...", "what happened with the auth refactor") → Run the search script to find relevant sessions, then show transcript or summary.
- **User references a past session** ("continue what I was doing on feat/attachments", "go back to before that change") → Use resume or rewind.
- **User asks about code history beyond git** ("why did we make this change", "what was the reasoning behind this approach") → Search sessions that touched the relevant files, read the transcript for context.
- **User seems lost or is re-doing work** → Check if there's a previous session that already solved this, and mention it.

### Available scripts

All scripts are in `.claude/scripts/`. Run them via Bash:

```bash
# List sessions for this project
python3 .claude/scripts/parse_jsonl.py list --project <cwd>

# Search sessions (keyword, branch, file, date, commit — can combine)
python3 .claude/scripts/parse_jsonl.py search --project <cwd> --keyword "text" --branch "name" --file "path" --date-from YYYY-MM-DD --commit SHA

# Session stats
python3 .claude/scripts/parse_jsonl.py stats --session <path>

# Condensed transcript
python3 .claude/scripts/parse_jsonl.py transcript --session <path>

# Restore session from remote (cross-machine)
bash .claude/scripts/restore.sh <session-id> <cwd>
```

### Slash commands

The user can also invoke these explicitly:
`/neander-status`, `/neander-search`, `/neander-transcript`, `/neander-summarize`, `/neander-session-stats`, `/neander-resume`, `/neander-rewind`, `/neander-redact`
