---
description: "MUST invoke when: (1) user asks 'why was this code written this way', 'what's the history of this file', 'who changed this and why'; (2) you are about to refactor or modify code you didn't write in this session; (3) you see a non-obvious pattern, workaround, or TODO comment and want to understand the reasoning. Searches checkpoint transcripts stored on the neander/checkpoints/v1 git branch."
---
# Code context from checkpoints

Spawn a subagent to research why a piece of code was written.

Use the Agent tool with `subagent_type: "general-purpose"` and `description: "Research code history for <FILE_PATH>"`.

Prompt for the subagent:

```
Find out why code in <FILE_PATH> was written the way it is by searching the checkpoint branch in this git repo.

The checkpoint branch `neander/checkpoints/v1` stores AI coding session transcripts and metadata. Each checkpoint is a snapshot of a session at a commit point.

Data structure:
- `git show neander/checkpoints/v1:index.log` — all checkpoints, one per line: checkpoint_id|session_id|commit_sha|timestamp
- `git show neander/checkpoints/v1:<shard>/metadata.json` — checkpoint metadata with:
  - `merged_files`: list of absolute file paths modified in this checkpoint
  - `summary`: AI-generated summary with `intent`, `outcome`, `learnings` (repo/code/workflow), `friction`, `open_items` — may be null
  - `session_ids`: which session(s) this checkpoint is from
  - `commit_sha`: the git commit this checkpoint is linked to
- `git show neander/checkpoints/v1:<shard>/transcript-<session_id>.jsonl` — full conversation transcript (JSONL, each line is a JSON object with `type`, `message`, etc.)
- Shard path = first 2 chars of checkpoint_id / rest of checkpoint_id (e.g., checkpoint `dfe7c7132205d8f6` → `df/e7c7132205d8f6/`)

Strategy:
1. Start with `index.log` to get all checkpoints
2. Check `metadata.json` for each — look at `merged_files` to find which checkpoints touched <FILE_PATH>. Also check `summary` if it exists — it may already answer the question.
3. Only read full transcripts if the summary doesn't explain the reasoning. Transcripts are large — read selectively.

Goal: explain WHY the code exists — the problem being solved, the reasoning behind the approach, alternatives rejected, and any known trade-offs or deferred work.

Return a concise explanation. Do not return raw transcripts.
```

$ARGUMENTS
