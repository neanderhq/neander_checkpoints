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

## Step 2: Show the file

Use the **Read** tool to read `/tmp/neander-transcript.txt` and display it to the user.

Do NOT summarize, rewrite, or add commentary. Just show the file contents.

$ARGUMENTS
