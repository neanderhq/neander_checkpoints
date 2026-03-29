"""Main CLI entry point for neander-checkpoints."""

import argparse
import sys

from neander_checkpoints import __version__


def cmd_install(args: argparse.Namespace) -> int:
    """Handle the install command."""
    from neander_checkpoints.install import run_install

    return run_install(
        project_path=args.project,
        global_mode=args.is_global,
    )


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
    p_install = subparsers.add_parser(
        "install",
        help="Install skills, scripts, and hooks into a project",
    )
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

    # --- resume ---
    p_resume = subparsers.add_parser(
        "resume",
        help="Restore a session transcript and show the resume command",
    )
    p_resume.add_argument("id", nargs="?", default=None, help="Checkpoint ID or session ID (omit to list recent)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = {
        "install": cmd_install,
        "resume": cmd_resume,
    }

    sys.exit(handler[args.command](args))


if __name__ == "__main__":
    main()
