---
description: View a condensed session transcript showing the conversation flow. Use when the user wants to see what happened in a session, view the conversation history, or read the transcript.
---
# View condensed session transcript

## Step 1: Generate transcript file

```
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <session_id_or_path> > /tmp/neander-transcript.txt
```

The `--session` flag accepts a full file path, a full session ID, or a partial session ID.

If the user said "current", use your own session ID.
If the user said "list", run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick.

## Step 2: Count lines

```
wc -l < /tmp/neander-transcript.txt
```

## Step 3: Display in chunks using Read tool

Read `/tmp/neander-transcript.txt` using the Read tool with `limit: 50` to show 50 lines at a time. Start from offset 1.

If the file has more than 50 lines, after showing the first chunk, ask the user if they want to see more. If yes, read the next 50 lines with the appropriate offset.

Do NOT summarize or rewrite the content. Show the raw file contents only.

$ARGUMENTS
