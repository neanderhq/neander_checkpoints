# Session status

Show active and recent Claude Code sessions for the current project.

## Instructions

1. List sessions for the current project:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py list --project <current working directory>
   ```

2. For the most recent 5 sessions, get stats:
   ```
   python3 __SCRIPTS_DIR__/parse_jsonl.py stats --session <path> --json
   ```

3. Check if the checkpoint branch exists:
   ```
   git rev-parse --verify neander/checkpoints/v1 2>/dev/null
   ```

4. Display in this format:

   **Project**: <project name> · **Branch**: <current git branch>
   **Checkpoints**: <enabled/not set up>

   ### Recent Sessions

   For each session show one block:
   ```
   <model> · <session_id short>
   > "<first user prompt, truncated to 80 chars>"
   <branch> · <relative start time> · <token count>
   ```

   Example:
   ```
   claude-opus-4-6 · 0647b6e9
   > "Implement the following plan: Two Chat Streaming..."
   refactor/unify-intake · 2d ago · 45.2k tokens
   ```

   Sort newest first. Show at most 5 sessions.

5. At the bottom, show:
   ```
   To resume: claude --resume <most-recent-session-id>
   To view transcript: /transcript <session-id>
   ```

$ARGUMENTS
