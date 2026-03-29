---
description: List checkpoints and restore files to a previous state. Use when the user wants to go back, undo changes, restore a previous version, or rewind to an earlier point. Accepts checkpoint IDs (16-char hex) or commit SHAs.
---
# Rewind to a session checkpoint

List available checkpoints and optionally restore files to a previous state.

## Arguments

`$ARGUMENTS` can be one of:
- **empty** — list all available checkpoints and let the user pick
- **a checkpoint ID or commit SHA** — rewind to that specific checkpoint

## Instructions

### 1. Gather checkpoints from all sources

**Git checkpoint branch:**
```
git rev-parse --verify neander/checkpoints/v1 2>/dev/null
```
If it exists, list checkpoints with metadata:
```
git log neander/checkpoints/v1 --format="%h %s %ai" -20
```

**Claude Code's built-in file snapshots** (from the session JSONL):
```
python3 __SCRIPTS_DIR__/parse_jsonl.py snapshots --checkpoint <path>
```

**Git log** (commits with Claude-Session trailers):
```
git log --format="%h %s %ai" --grep="Claude-Session" -20
```

### 2. Present checkpoints

Show a numbered list with:
- Commit SHA (short) or snapshot ID
- Timestamp (relative, e.g., "2h ago")
- Associated commit message or user prompt
- Source: [checkpoint branch], [file snapshot], or [git commit]

### 3. User selects a checkpoint

Offer options:
- **Restore files** — write backed-up files to their original paths. **Always show which files will be changed and confirm before proceeding.** Check for uncommitted changes first and warn the user.
- **View only** — show what files were in that checkpoint without restoring
- **Cancel**

### 4. After restore

Print the resume command:
```
claude --resume <session_id>
```

$ARGUMENTS
