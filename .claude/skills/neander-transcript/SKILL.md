---
description: View a condensed transcript showing the conversation flow for a checkpoint. Use when the user wants to see what happened in a checkpoint or session, view the conversation history, or read the transcript. Accepts checkpoint IDs (16-char hex) or session IDs (UUIDs).
---
# View condensed transcript

## Step 1: Generate transcript

```
python3 __SCRIPTS_DIR__/parse_jsonl.py transcript --session <checkpoint_id_or_session_id_or_path>
```

The `--session` flag accepts a checkpoint ID (16-char hex), a full session ID (UUID), a partial ID, or a full file path.

If the user said "current", use your own session ID.
If the user said "list", run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick.

## Step 2: Output the transcript verbatim

Copy the ENTIRE output from step 1 and output it as a markdown code block:

````
```
<paste the entire transcript output here, every single line>
```
````

**IMPORTANT — DO NOT IGNORE THESE RULES:**
- **DO NOT SUMMARIZE.** Output every single line from the transcript exactly as-is.
- **DO NOT SKIP LINES.** Even if the transcript is 500 lines long, output all of them.
- **DO NOT ADD COMMENTARY.** No "here's the transcript", no summary before or after, no analysis.
- **DO NOT REWRITE OR REPHRASE** any part of the transcript.
- **USE A CODE BLOCK.** Wrap the entire output in triple backticks so it renders as preformatted text.
- If the output is empty, just say "No transcript data found."

This is a DISPLAY command, not an ANALYSIS command. Your only job is to show the raw output.

$ARGUMENTS
