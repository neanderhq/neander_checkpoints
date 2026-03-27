# Session statistics

Show token usage, message counts, duration, and file modification stats for a Claude Code session.

## Instructions

1. If the user provided a session path, use it. Otherwise find recent sessions:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py list --project "$(pwd)"
   ```

2. Get full stats:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path>
   ```

3. Also get file snapshots for checkpoint info:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py snapshots --session <path>
   ```

4. Present the stats in a clear format. Include:
   - Session ID, slug, branch, working directory
   - Models used
   - Duration (start → end, total minutes)
   - Token usage breakdown (input, output, cache read, cache created, total)
   - Estimated cost (Opus: $15/M input, $75/M output; Sonnet: $3/M input, $15/M output)
   - Message counts (user vs assistant)
   - Files modified (list)
   - Number of checkpoints/snapshots

$ARGUMENTS
