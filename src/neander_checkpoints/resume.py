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


def run_resume(identifier: str) -> int:
    """
    Resume a session from a checkpoint or session ID.

    1. Resolve the ID to a session ID
    2. Check if the session JSONL exists locally
    3. If not, run restore.sh to fetch from remote
    4. Print the resume command

    Returns 0 on success, 1 on failure.
    """
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
        print(f"Session already exists locally: {local_path}")
        print()
        print(f"To resume: claude --resume {session_id}")
        return 0

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

    print()
    print(f"To resume: claude --resume {session_id}")
    return 0
