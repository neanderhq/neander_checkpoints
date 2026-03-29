"""Main CLI entry point for neander-checkpoints."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from neander_checkpoints import __version__


def _find_parse_jsonl() -> Path | None:
    """Find parse_jsonl.py — prefer installed copy, fall back to bundled."""
    # Check project-local install
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            repo_root = result.stdout.strip()
            candidate = Path(repo_root) / ".claude" / "scripts" / "parse_jsonl.py"
            if candidate.exists():
                return candidate
    except FileNotFoundError:
        pass

    # Check global install
    global_scripts = Path.home() / ".claude" / "scripts" / "parse_jsonl.py"
    if global_scripts.exists():
        return global_scripts

    # Fall back to bundled copy
    bundled = Path(__file__).parent / "bundled" / "scripts" / "parse_jsonl.py"
    if bundled.exists():
        return bundled

    return None


def _run_parse_jsonl(args: list[str]) -> int:
    """Run parse_jsonl.py with the given arguments."""
    script = _find_parse_jsonl()
    if not script:
        print(
            "Error: parse_jsonl.py not found. Run 'neander-checkpoints install' first.",
            file=sys.stderr,
        )
        return 1

    cmd = [sys.executable, str(script)] + args
    result = subprocess.run(cmd)
    return result.returncode


def _pager_output(text: str) -> None:
    """Display text through a pager if it exceeds terminal height."""
    term_lines = shutil.get_terminal_size().lines
    text_lines = text.count("\n") + 1

    if text_lines <= term_lines - 2:
        print(text)
        return

    pager = os.environ.get("PAGER", "less")
    try:
        proc = subprocess.Popen(
            pager.split(),
            stdin=subprocess.PIPE,
            encoding="utf-8",
        )
        proc.communicate(input=text)
    except (FileNotFoundError, BrokenPipeError):
        # Fall back to plain output if pager not available
        print(text)


def cmd_install(args: argparse.Namespace) -> int:
    """Handle the install command."""
    from neander_checkpoints.install import run_install

    return run_install(
        project_path=args.project,
        global_mode=args.is_global,
    )


def cmd_status(args: argparse.Namespace) -> int:
    """Handle the status command."""
    cmd_args = ["status", "--project", os.getcwd()]
    if args.json:
        cmd_args.append("--json")
    if args.fetch:
        cmd_args.append("--fetch")
    if args.limit:
        cmd_args.extend(["--limit", str(args.limit)])
    return _run_parse_jsonl(cmd_args)


def cmd_search(args: argparse.Namespace) -> int:
    """Handle the search command."""
    cmd_args = ["search", "--project", os.getcwd()]
    if args.query:
        cmd_args.extend(["--keyword", args.query])
    if args.branch:
        cmd_args.extend(["--branch", args.branch])
    if args.file:
        cmd_args.extend(["--file", args.file])
    if args.date_from:
        cmd_args.extend(["--date-from", args.date_from])
    if args.date_to:
        cmd_args.extend(["--date-to", args.date_to])
    if args.commit:
        cmd_args.extend(["--commit", args.commit])
    if args.json:
        cmd_args.append("--json")
    if args.fetch:
        cmd_args.append("--fetch")
    if args.limit:
        cmd_args.extend(["--limit", str(args.limit)])
    return _run_parse_jsonl(cmd_args)


def cmd_transcript(args: argparse.Namespace) -> int:
    """Handle the transcript command with pager support."""
    script = _find_parse_jsonl()
    if not script:
        print(
            "Error: parse_jsonl.py not found. Run 'neander-checkpoints install' first.",
            file=sys.stderr,
        )
        return 1

    cmd_args = [sys.executable, str(script), "transcript", "--checkpoint", args.id]
    if args.max_lines:
        cmd_args.extend(["--max-lines", str(args.max_lines)])

    # Capture output for pager support
    result = subprocess.run(cmd_args, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    output = result.stdout
    if output:
        _pager_output(output.rstrip("\n"))

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Handle the stats command."""
    cmd_args = ["stats", "--checkpoint", args.id]
    if args.json:
        cmd_args.append("--json")
    return _run_parse_jsonl(cmd_args)


def cmd_resume(args: argparse.Namespace) -> int:
    """Handle the resume command."""
    from neander_checkpoints.resume import run_resume

    return run_resume(args.id)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="neander-checkpoints",
        description="Checkpoint management for Claude Code sessions",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- install ---
    p_install = subparsers.add_parser("install", help="Install into current project")
    p_install.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Project path (default: current directory)",
    )
    p_install.add_argument(
        "--global",
        dest="is_global",
        action="store_true",
        help="Install globally into ~/.claude/",
    )

    # --- status ---
    p_status = subparsers.add_parser("status", help="Show checkpoints overview")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")
    p_status.add_argument("--fetch", action="store_true", help="Fetch remote checkpoints first")
    p_status.add_argument("--limit", "-l", type=int, help="Max checkpoints to show")

    # --- search ---
    p_search = subparsers.add_parser("search", help="Search checkpoints")
    p_search.add_argument("query", nargs="?", help="Search keyword")
    p_search.add_argument("--branch", "-b", help="Filter by git branch")
    p_search.add_argument("--file", "-f", help="Filter by modified file")
    p_search.add_argument("--date-from", help="From date (YYYY-MM-DD)")
    p_search.add_argument("--date-to", help="To date (YYYY-MM-DD)")
    p_search.add_argument("--commit", help="Filter by commit SHA")
    p_search.add_argument("--json", action="store_true", help="Output as JSON")
    p_search.add_argument("--fetch", action="store_true", help="Fetch remote checkpoints first")
    p_search.add_argument("--limit", "-l", type=int, help="Max results to show")

    # --- transcript ---
    p_transcript = subparsers.add_parser("transcript", help="Show session transcript")
    p_transcript.add_argument("id", help="Checkpoint or session ID")
    p_transcript.add_argument("--max-lines", "-n", type=int, help="Max transcript lines")

    # --- stats ---
    p_stats = subparsers.add_parser("stats", help="Show session statistics")
    p_stats.add_argument("id", help="Checkpoint or session ID")
    p_stats.add_argument("--json", action="store_true", help="Output as JSON")

    # --- resume ---
    p_resume = subparsers.add_parser("resume", help="Restore and resume a session")
    p_resume.add_argument("id", help="Checkpoint or session ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = {
        "install": cmd_install,
        "status": cmd_status,
        "search": cmd_search,
        "transcript": cmd_transcript,
        "stats": cmd_stats,
        "resume": cmd_resume,
    }

    sys.exit(handler[args.command](args))


if __name__ == "__main__":
    main()
