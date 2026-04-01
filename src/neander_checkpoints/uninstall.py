"""Uninstall neander-checkpoints from a project."""

import json
import re
import shutil
from pathlib import Path


def run_uninstall(project_path: str | None = None) -> int:
    """Remove neander-checkpoints from a project."""
    if project_path:
        resolved = Path(project_path).resolve()
    else:
        resolved = Path.cwd()

    claude_dir = resolved / ".claude"
    if not claude_dir.exists():
        print("Nothing to uninstall — .claude/ directory not found.")
        return 0

    print(f"Uninstalling neander-checkpoints from: {resolved}\n")

    # --- Remove scripts ---
    scripts_dir = claude_dir / "scripts"
    if scripts_dir.exists():
        shutil.rmtree(scripts_dir)
        print("  [remove] .claude/scripts/")

    # --- Remove skills ---
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        for skill in sorted(skills_dir.iterdir()):
            if skill.is_dir() and skill.name.startswith("neander-"):
                shutil.rmtree(skill)
                print(f"  [remove] .claude/skills/{skill.name}")

    # --- Remove agents ---
    agents_dir = claude_dir / "agents"
    if agents_dir.exists():
        for agent in sorted(agents_dir.iterdir()):
            if agent.is_dir() and agent.name.startswith("neander-"):
                shutil.rmtree(agent)
                print(f"  [remove] .claude/agents/{agent.name}")

    # --- Remove hooks + permissions from settings.json ---
    settings_file = claude_dir / "settings.json"
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
            changed = False

            # Remove hooks
            hooks = settings.get("hooks", {})
            for event in list(hooks.keys()):
                original = len(hooks[event])
                hooks[event] = [
                    h for h in hooks[event]
                    if "checkpoint.sh" not in json.dumps(h)
                    and "detect_commit.sh" not in json.dumps(h)
                    and "on_stop.sh" not in json.dumps(h)
                    and "on_session_start.sh" not in json.dumps(h)
                ]
                if len(hooks[event]) != original:
                    changed = True
                if not hooks[event]:
                    del hooks[event]

            if hooks:
                settings["hooks"] = hooks
            else:
                settings.pop("hooks", None)

            # Remove permissions
            perms = settings.get("permissions", {}).get("allow", [])
            original_len = len(perms)
            perms = [
                p for p in perms
                if "neander" not in p
                and ".claude/scripts" not in p
                and ".claude/projects" not in p
            ]
            if len(perms) != original_len:
                changed = True
            if perms:
                settings["permissions"] = {"allow": perms}
            else:
                settings.pop("permissions", None)

            if changed:
                settings_file.write_text(json.dumps(settings, indent=2) + "\n")
                print("  [clean] hooks + permissions from settings.json")

        except (json.JSONDecodeError, OSError):
            print("  [skip] could not parse settings.json")

    # --- Remove config file ---
    config_file = claude_dir / "neander-checkpoints.json"
    if config_file.exists():
        config_file.unlink()
        print("  [remove] .claude/neander-checkpoints.json")

    # --- Remove session management section from CLAUDE.md ---
    claude_md = resolved / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        if "neander_checkpoints" in content or "neander-checkpoints" in content:
            content = re.sub(
                r"\n*## Checkpoint Management \(neander_checkpoints\).*",
                "", content, flags=re.DOTALL,
            )
            content = content.rstrip() + "\n"
            claude_md.write_text(content)
            print("  [clean] CLAUDE.md")

    # --- Remove pre-push hook ---
    pre_push = resolved / ".git" / "hooks" / "pre-push"
    if pre_push.exists():
        content = pre_push.read_text()
        if "neander_code_sessions" in content or "neander-checkpoints" in content:
            content = re.sub(
                r"# Auto-redact session transcripts before push \[neander_code_sessions\].*?^done\n?",
                "", content, flags=re.DOTALL | re.MULTILINE,
            )
            content = content.strip()
            if content and content != "#!/usr/bin/env bash":
                pre_push.write_text(content + "\n")
                print("  [clean] .git/hooks/pre-push")
            else:
                pre_push.unlink()
                print("  [remove] .git/hooks/pre-push")

    print("\nDone!")
    return 0
