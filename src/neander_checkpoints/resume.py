"""Resume command — restore a session and print the resume command."""

import os
import subprocess
import sys
from pathlib import Path


def _find_bundled_restore_sh() -> Path | None:
    """Find restore.sh in the bundled scripts."""
    bundled = Path(__file__).parent / "bundled" / "scripts" / "restore.sh"
    if bundled.exists():
        return bundled
    return None


def _find_installed_restore_sh() -> Path | None:
    """Find restore.sh in the current project's .claude/scripts/."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            repo_root = result.stdout.strip()
            candidate = Path(repo_root) / ".claude" / "scripts" / "restore.sh"
            if candidate.exists():
                return candidate
    except FileNotFoundError:
        pass
    return None


def _resolve_checkpoint_to_session(checkpoint_id: str) -> str | None:
    """
    Given a checkpoint ID (prefix), look up the session ID from index.log
    on the checkpoint branch.
    """
    try:
        result = subprocess.run(
            ["git", "show", "origin/neander/checkpoints/v1:index.log"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try without origin/
            result = subprocess.run(
                ["git", "show", "neander/checkpoints/v1:index.log"],
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            return None

        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                cp_id = parts[0].strip()
                session_id = parts[1].strip()
                if cp_id.startswith(checkpoint_id) or checkpoint_id.startswith(cp_id[:len(checkpoint_id)]):
                    return session_id
    except FileNotFoundError:
        pass
    return None


def _list_recent_checkpoints() -> None:
    """Show recent checkpoints so the user can pick one."""
    try:
        result = subprocess.run(
            ["git", "show", "neander/checkpoints/v1:index.log"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print("No checkpoints found. Run 'neander-checkpoints install' and make some commits first.")
            return

        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        if not lines:
            print("No checkpoints found.")
            return

        # Show most recent (last entries in index)
        # Read metadata for intents
        intents = {}
        for line in lines:
            parts = line.split("|")
            if len(parts) < 4:
                continue
            cp_id = parts[0]
            shard = f"{cp_id[:2]}/{cp_id[2:]}"
            try:
                meta_result = subprocess.run(
                    ["git", "show", f"neander/checkpoints/v1:{shard}/metadata.json"],
                    capture_output=True, text=True, timeout=5,
                )
                if meta_result.returncode == 0:
                    import json
                    metadata = json.loads(meta_result.stdout)
                    summary = metadata.get("summary")
                    if summary and isinstance(summary, dict) and summary.get("intent"):
                        intents[cp_id] = summary["intent"]
            except Exception:
                pass

        # Collect rows, deduplicate by session
        rows = []
        seen = set()
        for line in reversed(lines):
            parts = line.split("|")
            if len(parts) < 4:
                continue
            cp_id, session_id, commit_sha, timestamp = parts[:4]
            if session_id in seen:
                continue
            seen.add(session_id)
            date_str = timestamp.split("T")[0] + " " + timestamp.split("T")[1][:5] if "T" in timestamp else timestamp
            topic = intents.get(cp_id, "")[:40]
            rows.append((cp_id[:16], date_str, topic))
            if len(rows) >= 10:
                break

        # Print table
        print("Recent checkpoints:\n")
        headers = ("Checkpoint", "Date", "Topic")
        widths = [max(len(h), max((len(r[i]) for r in rows), default=0)) for i, h in enumerate(headers)]
        def fmt(cells):
            return "  ".join(cells[i].ljust(widths[i]) for i in range(len(cells)))
        print(fmt(headers))
        print("  ".join("-" * w for w in widths))
        for row in rows:
            print(fmt(row))

        print(f"\nUsage: neander-checkpoints resume <checkpoint-id>")
    except FileNotFoundError:
        print("Error: not in a git repository.", file=sys.stderr)


def run_resume(identifier: str | None = None) -> int:
    """
    Resume a session from a checkpoint or session ID.

    If no identifier given, lists recent checkpoints.

    1. Resolve the ID to a session ID
    2. Check if the session JSONL exists locally
    3. If not, run restore.sh to fetch from remote
    4. Print the resume command

    Returns 0 on success, 1 on failure.
    """
    if not identifier:
        _list_recent_checkpoints()
        return 0

    project_path = os.getcwd()

    # Try to resolve as checkpoint ID first
    session_id = _resolve_checkpoint_to_session(identifier)

    if session_id:
        print(f"Resolved checkpoint {identifier} -> session {session_id}")
    else:
        # Assume it's already a session ID
        session_id = identifier

    # Check if session exists locally
    encoded_dir = project_path.replace("/", "-").replace("_", "-")
    local_path = Path.home() / ".claude" / "projects" / encoded_dir / f"{session_id}.jsonl"

    if local_path.exists():
        print(f"Resuming session {session_id}...")
        os.execvp("claude", ["claude", "--resume", session_id])

    # Find restore.sh
    restore_sh = _find_installed_restore_sh() or _find_bundled_restore_sh()
    if not restore_sh:
        print("Error: restore.sh not found. Run 'neander-checkpoints install' first.", file=sys.stderr)
        return 1

    print(f"Session not found locally. Fetching from remote...")
    result = subprocess.run(
        ["bash", str(restore_sh), session_id, project_path],
        capture_output=False,
    )

    if result.returncode != 0:
        print(f"Error: failed to restore session {session_id}", file=sys.stderr)
        return 1

    print(f"Resuming session {session_id}...")
    os.execvp("claude", ["claude", "--resume", session_id])
