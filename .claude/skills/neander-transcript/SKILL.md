---
description: View a condensed session transcript showing the conversation flow. Use when the user wants to see what happened in a session, view the conversation history, or read the transcript.
---
# View condensed session transcript

Run this single command and display the output exactly as-is:

```
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <session_id_or_path>
```

The `--session` flag accepts a full file path, a full session ID, or a partial session ID.

If the user said "current", use your own session ID from the conversation context.
If the user said "list", run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick.

**IMPORTANT**: Display the output exactly as-is in ONE call. Do NOT summarize, rewrite, paginate, or call the script multiple times. This is a transcript, not a summary.

$ARGUMENTS
