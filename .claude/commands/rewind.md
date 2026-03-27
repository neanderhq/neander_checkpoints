# Rewind to a session checkpoint

List available checkpoints and optionally restore files to a previous state.

## Instructions

1. If in a git repo, check for the checkpoint branch:
   ```
   git rev-parse --verify claude-sessions/checkpoints 2>/dev/null
   ```

2. If the branch exists, list checkpoints:
   ```
   git log claude-sessions/checkpoints --oneline --format="%h %s" -20
   ```

3. Also check file-history-snapshots in the session JSONL:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py snapshots --session <path>
   ```

4. Present the checkpoints to the user with timestamps and associated commits.

5. If the user picks a checkpoint to restore:
   - For git-branch checkpoints: show the files stored in that checkpoint
   - For JSONL snapshots: extract the file backups and show what would be restored
   - **Always confirm before restoring files**
   - To restore, write each backed-up file to its original path

6. After restore, print the resume command:
   ```
   claude -r <session_id>
   ```

$ARGUMENTS
