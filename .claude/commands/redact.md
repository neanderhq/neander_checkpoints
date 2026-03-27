# Redact secrets from session transcript

Scan a session transcript for secrets and PII, then produce a redacted version.

## Instructions

1. If the user provided a session path, use it. Otherwise find recent sessions:
   ```
   python3 scripts/parse_jsonl.py list --project "$(pwd)"
   ```

2. First do a dry-run check:
   ```
   python3 scripts/redact.py --check <session_path>
   ```

3. Show the findings to the user — how many secrets found, what types (API keys, passwords, PII, high-entropy strings).

4. If the user wants to proceed with redaction:
   ```
   python3 scripts/redact.py <session_path> <output_path>
   ```

5. Report what was redacted and where the clean file was saved.

$ARGUMENTS
