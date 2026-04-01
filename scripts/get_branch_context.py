#!/usr/bin/env python3
"""
Get past checkpoint context for the current branch.

Called by on_session_start.sh. Outputs a concise text block that
Claude Code injects into the session context.

Tier 1: Show summaries (intent + open items) if available
Tier 2: Show first prompts + files modified as fallback
Tier 3: Silent if nothing relevant
"""

import json
import subprocess
import sys

CHECKPOINT_BRANCH = "neander/checkpoints/v1"

# Branches where auto-context is noise (too many unrelated checkpoints)
SKIP_BRANCHES = {"main", "master", "develop", "dev", "staging", "production", "release"}


def git_show(path: str) -> str:
    """Read a file from the checkpoint branch."""
    result = subprocess.run(
        ["git", "show", f"{CHECKPOINT_BRANCH}:{path}"],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout if result.returncode == 0 else ""


def is_commit_on_branch(commit_sha: str) -> bool:
    """Check if a commit is reachable from HEAD (i.e., on current branch)."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
        capture_output=True, timeout=5,
    )
    return result.returncode == 0


def get_first_prompt(transcript_path: str) -> str:
    """Extract the first meaningful user prompt from a checkpoint transcript."""
    content = git_show(transcript_path)
    if not content:
        return ""

    for line in content.strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("type") != "user":
            continue

        msg = entry.get("message", {})
        content_field = msg.get("content", "")

        if isinstance(content_field, str):
            text = content_field
        elif isinstance(content_field, list):
            parts = []
            for block in content_field:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            text = " ".join(parts)
        else:
            continue

        # Strip injected tags
        import re
        text = re.sub(r"<[a-z_-]+>.*?</[a-z_-]+>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[a-z_-]+\s*/?>", "", text)
        text = text.strip()

        # Skip skill invocations and empty prompts
        if not text or text.startswith("Base directory for this skill:"):
            continue

        return text

    return ""


def main(branch: str) -> None:
    if branch in SKIP_BRANCHES:
        return

    # Read index
    index_content = git_show("index.log")
    if not index_content:
        return

    # Parse checkpoints
    checkpoints = []
    for line in index_content.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        checkpoints.append({
            "checkpoint_id": parts[0],
            "session_id": parts[1],
            "commit_sha": parts[2],
            "timestamp": parts[3],
        })

    if not checkpoints:
        return

    # Filter to commits on current branch
    branch_checkpoints = []
    for cp in reversed(checkpoints):  # newest first
        try:
            if is_commit_on_branch(cp["commit_sha"]):
                branch_checkpoints.append(cp)
        except Exception:
            continue

    if not branch_checkpoints:
        return

    # Deduplicate by session (keep latest per session)
    seen_sessions = set()
    unique = []
    for cp in branch_checkpoints:
        if cp["session_id"] in seen_sessions:
            continue
        seen_sessions.add(cp["session_id"])
        unique.append(cp)

    # Read metadata for summaries
    for cp in unique:
        shard = f"{cp['checkpoint_id'][:2]}/{cp['checkpoint_id'][2:]}"
        meta_content = git_show(f"{shard}/metadata.json")
        if meta_content:
            try:
                meta = json.loads(meta_content)
                summary = meta.get("summary")
                if summary and isinstance(summary, dict):
                    cp["intent"] = summary.get("intent", "")
                    cp["outcome"] = summary.get("outcome", "")
                    cp["open_items"] = summary.get("open_items", [])
                cp["merged_files"] = meta.get("merged_files", [])

                # Find transcript path for Tier 2 fallback
                cp["transcript_path"] = f"{shard}/transcript-{cp['session_id']}.jsonl"
            except json.JSONDecodeError:
                pass

    # Tier 1: Checkpoints with summaries
    summarized = [cp for cp in unique if cp.get("intent")]

    if summarized:
        print(f"[neander-checkpoints] Previous work on {branch}:\n")
        for cp in summarized[:5]:
            date = cp["timestamp"].split("T")[0] if "T" in cp["timestamp"] else cp["timestamp"]
            print(f"• {cp['intent']} ({date})")
            open_items = cp.get("open_items", [])
            if open_items:
                items = "; ".join(open_items[:3])
                print(f"  Open: {items}")
            print()
        return

    # Tier 2: No summaries — show first prompts + files
    entries_shown = 0
    output_lines = []
    for cp in unique[:5]:
        date = cp["timestamp"].split("T")[0] if "T" in cp["timestamp"] else cp["timestamp"]
        files = len(cp.get("merged_files", []))
        transcript_path = cp.get("transcript_path", "")

        first_prompt = get_first_prompt(transcript_path) if transcript_path else ""

        if first_prompt:
            prompt_short = first_prompt[:60].replace("\n", " ")
            output_lines.append(f'• {cp["session_id"][:8]} ({date}) — "{prompt_short}..." [{files} files]')
            entries_shown += 1
        elif files > 0:
            output_lines.append(f'• {cp["session_id"][:8]} ({date}) — [{files} files modified]')
            entries_shown += 1

    if entries_shown > 0:
        print(f"[neander-checkpoints] Previous work on {branch}:\n")
        for line in output_lines:
            print(line)
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)
    try:
        main(sys.argv[1])
    except Exception:
        # Never fail — silent exit on any error
        pass
