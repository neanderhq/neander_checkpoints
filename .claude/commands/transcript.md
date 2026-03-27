# View condensed session transcript

Show a clean, readable version of a Claude Code session transcript.

## Instructions

1. If the user provided a session path, use it directly. Otherwise find recent sessions:
   ```
   python3 scripts/parse_jsonl.py list --project "$(pwd)"
   ```
   Ask the user which session if multiple are found.

2. Generate the condensed transcript:
   ```
   python3 scripts/parse_jsonl.py transcript --session <path>
   ```

3. Display the output directly. If it's very long, show the first and last sections with a note about what's in between.

4. If the user asks to filter (e.g., "just show tool calls" or "just show user messages"), re-read the transcript and filter accordingly.

$ARGUMENTS
