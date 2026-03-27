# Resume a session from checkpoint

Find and prepare to resume a Claude Code session, optionally from a remote checkpoint.

## Instructions

1. List recent sessions:
   ```
   python3 scripts/parse_jsonl.py list --project "$(pwd)"
   ```

2. If the user specified a branch, check the checkpoint branch for sessions linked to that branch:
   ```
   git log claude-sessions/checkpoints --oneline --grep="<branch>" -10
   ```

3. If resuming from a remote checkpoint:
   ```
   git fetch origin claude-sessions/checkpoints 2>/dev/null
   ```
   Then find the relevant checkpoint metadata.

4. Show the user:
   - Session ID
   - Last prompt / what was being worked on
   - Branch it was on
   - Files that were modified

5. Print the resume command:
   ```
   claude -r <session_id>
   ```

6. If the session's JSONL doesn't exist locally (cross-machine resume):
   - Extract the transcript from the checkpoint branch
   - Place it in the correct location under ~/.claude/projects/

$ARGUMENTS
