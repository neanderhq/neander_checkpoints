"""Main CLI entry point for neander-checkpoints."""

import argparse
import json
import sys
from pathlib import Path

from neander_checkpoints import __version__

CONFIG_PATH = Path(".claude/neander-checkpoints.json")
DEFAULTS = {
    "inject_previous_context": True,
    "auto_summarize": True,
}


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


def cmd_config(args: argparse.Namespace) -> int:
    """Handle the config command."""
    config = _load_config()

    if not args.key:
        # Show all settings
        print("neander-checkpoints config:\n")
        for key, value in {**DEFAULTS, **config}.items():
            default = " (default)" if key not in config else ""
            print(f"  {key}: {_format_value(value)}{default}")
        print(f"\nConfig file: {CONFIG_PATH}")
        return 0

    key = args.key

    if key not in DEFAULTS:
        print(f"Unknown setting: {key}", file=sys.stderr)
        print(f"Available: {', '.join(DEFAULTS.keys())}", file=sys.stderr)
        return 1

    if not args.value:
        # Show single setting
        value = config.get(key, DEFAULTS[key])
        print(f"{key}: {_format_value(value)}")
        return 0

    # Set value
    value = _parse_value(args.value)
    config[key] = value
    _save_config(config)
    print(f"{key}: {_format_value(value)}")
    return 0


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")


def _parse_value(value: str) -> bool | str:
    if value.lower() in ("true", "on", "yes", "1"):
        return True
    if value.lower() in ("false", "off", "no", "0"):
        return False
    return value


def _format_value(value) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value)


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
        help="Restore a session transcript and launch claude --resume",
    )
    p_resume.add_argument(
        "id", nargs="?", default=None,
        help="Checkpoint ID or session ID (omit to list recent)",
    )

    # --- config ---
    p_config = subparsers.add_parser(
        "config",
        help="View or change settings",
    )
    p_config.add_argument(
        "key", nargs="?", default=None,
        help="Setting name (omit to show all)",
    )
    p_config.add_argument(
        "value", nargs="?", default=None,
        help="New value (on/off)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = {
        "install": cmd_install,
        "resume": cmd_resume,
        "config": cmd_config,
    }

    sys.exit(handler[args.command](args))


if __name__ == "__main__":
    main()
