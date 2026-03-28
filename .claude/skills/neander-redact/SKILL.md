---
description: Scan a session transcript for secrets and PII, then redact them. Use when the user wants to share a session, clean up transcripts, or check for leaked secrets.
disable-model-invocation: true
---
# Redact secrets from session transcript

Scan a session transcript for secrets and PII, then produce a redacted version.

## Arguments

`$ARGUMENTS` can be one of:
- **empty / "current"** — redact the current session
- **a session ID or file path** — redact that specific session
- **"list"** — list all sessions for the current project and let the user pick one

## Finding the session file

- **Current session**: Your session ID is in your conversation context. Find it with: `find ~/.claude/projects -name "<your-session-id>.jsonl" -type f`
- **Session ID provided**: `find ~/.claude/projects -name "<session-id>.jsonl" -type f`
- **File path provided**: use it directly
- **"list"**: run `python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>` and ask the user to pick

## Redacting

1. First do a dry-run check:
   ```
   python3 __SCRIPTS_DIR__/redact.py --check <session_path>
   ```

2. Show the findings to the user — how many secrets found, what types (API keys, passwords, PII, high-entropy strings).

3. If the user wants to proceed with redaction:
   ```
   python3 __SCRIPTS_DIR__/redact.py <session_path> <output_path>
   ```

4. Report what was redacted and where the clean file was saved.

$ARGUMENTS
