"""Install neander-checkpoints into a project or globally."""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def _bundled_dir() -> Path:
    """Return the path to bundled data files shipped with the package."""
    return Path(__file__).parent / "bundled"


def _validate_prerequisites(project_path: Path | None) -> list[str]:
    """Validate prerequisites for installation. Returns list of error messages."""
    errors = []

    # Python version
    if sys.version_info < (3, 10):
        errors.append(f"Python >= 3.10 required (found {sys.version_info.major}.{sys.version_info.minor})")

    # Claude Code installed
    claude_dir = Path.home() / ".claude"
    claude_on_path = shutil.which("claude") is not None
    if not claude_dir.exists() and not claude_on_path:
        errors.append("Claude Code not found (~/.claude/ missing and 'claude' not on PATH)")

    # Git repo check (project mode only)
    if project_path is not None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(f"{project_path} is not inside a git repository")
        except FileNotFoundError:
            errors.append("git is not installed")

    return errors


def _merge_settings(settings_path: Path, hooks_config: dict, scripts_dir: str) -> None:
    """Merge hooks and permissions into settings.json."""
    if settings_path.exists():
        with open(settings_path) as f:
            settings = json.load(f)
    else:
        settings = {}

    # Merge hooks
    new_hooks = hooks_config.get("hooks", {})
    existing_hooks = settings.get("hooks", {})

    for event, handlers in new_hooks.items():
        if event not in existing_hooks:
            existing_hooks[event] = handlers
        else:
            existing_cmds = {
                h.get("hooks", [{}])[0].get("command", "")
                for h in existing_hooks[event]
            }
            for handler in handlers:
                cmd = handler.get("hooks", [{}])[0].get("command", "")
                if cmd not in existing_cmds:
                    existing_hooks[event].append(handler)

    settings["hooks"] = existing_hooks

    # Merge permissions
    home = str(Path.home())
    new_permissions = [
        f"Bash(python3 {scripts_dir}/parse_jsonl.py*)",
        f"Bash(python3 {scripts_dir}/redact.py*)",
        f"Bash(bash {scripts_dir}/checkpoint.sh*)",
        f"Bash(bash {scripts_dir}/detect_commit.sh*)",
        f"Bash(bash {scripts_dir}/on_stop.sh*)",
        f"Bash(bash {scripts_dir}/link_commit.sh*)",
        f"Bash(bash {scripts_dir}/restore.sh*)",
        f"Bash(bash {scripts_dir}/save_summary.sh*)",
        f"Bash(bash {scripts_dir}/persist_summary.sh*)",
        f"Bash(find {home}/.claude/projects *)",
        "Bash(ls .claude/*)",
        "Bash(*neander-transcript*)",
        "Bash(wc*neander*)",
        "Read(/tmp/neander-*)",
    ]

    permissions = settings.get("permissions", {})
    allow = permissions.get("allow", [])
    added = 0
    for perm in new_permissions:
        if perm not in allow:
            allow.append(perm)
            added += 1
    permissions["allow"] = allow
    settings["permissions"] = permissions

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    action = "merge" if settings_path.exists() else "create"
    print(f"  [{action}] hooks + permissions into {settings_path}")
    if added:
        print(f"  [add] {added} permission rules")
    else:
        print(f"  [skip] permissions already present")


def _install_pre_push_hook(git_dir: Path, scripts_dir: str) -> None:
    """Install the pre-push git hook for auto-redacting transcripts."""
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_push = hooks_dir / "pre-push"

    hook_content = f'''#!/usr/bin/env bash
# Auto-redact session transcripts before push [neander_code_sessions]
SCRIPTS_DIR="{scripts_dir}"
CHECKPOINT_BRANCH="neander/checkpoints/v1"

while read local_ref local_sha remote_ref remote_sha; do
    if echo "$local_ref" | grep -q "$CHECKPOINT_BRANCH"; then
        echo "[neander_code_sessions] Redacting transcripts on checkpoint branch..."
        git diff --name-only "$remote_sha..$local_sha" -- "*.jsonl" 2>/dev/null | while read jsonl; do
            python3 "$SCRIPTS_DIR/redact.py" "$jsonl" "$jsonl" 2>/dev/null || true
        done
    fi
done
'''

    if pre_push.exists():
        existing = pre_push.read_text()
        if "neander_code_sessions" in existing:
            print("  [skip] pre-push hook already installed")
            return
        with open(pre_push, "a") as f:
            f.write("\n" + hook_content)
        print("  [append] pre-push hook")
    else:
        pre_push.write_text(hook_content)
        pre_push.chmod(pre_push.stat().st_mode | stat.S_IEXEC)
        print("  [create] pre-push hook")


def _update_claude_md(claude_md_path: Path, snippet_path: Path, scripts_dir: str) -> None:
    """Append or update the session management section in CLAUDE.md."""
    snippet_text = snippet_path.read_text().replace("__SCRIPTS_DIR__", scripts_dir)

    if claude_md_path.exists():
        content = claude_md_path.read_text()
        if "neander_code_sessions" not in content and "neander_checkpoints" not in content:
            with open(claude_md_path, "a") as f:
                f.write("\n" + snippet_text)
            print("  [append] CLAUDE.md")
        else:
            # Update existing section
            new_content = re.sub(
                r"## (?:Session Management|Checkpoint Management) \(neander_(?:code_sessions|checkpoints)\).*",
                snippet_text,
                content,
                flags=re.DOTALL,
            )
            claude_md_path.write_text(new_content)
            print("  [update] CLAUDE.md with current paths")
    else:
        claude_md_path.write_text(snippet_text)
        print("  [create] CLAUDE.md")


def run_install(project_path: str | None = None, global_mode: bool = False) -> int:
    """
    Install neander-checkpoints into a project or globally.

    Returns 0 on success, 1 on failure.
    """
    bundled = _bundled_dir()
    home = Path.home()

    if not global_mode and not project_path:
        # Default to current directory
        project_path = os.getcwd()

    # Resolve project path
    resolved_project = Path(project_path).resolve() if project_path else None

    # Validate
    errors = _validate_prerequisites(resolved_project)
    if errors:
        print("Installation failed — prerequisites not met:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if global_mode:
        target_base = home / ".claude"
        git_dir = None
        print("Installing neander-checkpoints (global):")
    else:
        target_base = resolved_project / ".claude"
        git_dir = resolved_project / ".git"
        print(f"Installing neander-checkpoints into: {resolved_project}")

    # --- Clean stale neander files from previous installs ---
    scripts_target = target_base / "scripts"
    skills_target = target_base / "skills"
    agents_target = target_base / "agents"

    # Wipe old scripts (all files in .claude/scripts/ are ours)
    if scripts_target.exists():
        for old in scripts_target.iterdir():
            if old.is_file():
                old.unlink()
        print("  [clean] removed old scripts")

    # Wipe old neander-* skills (preserve non-neander skills)
    if skills_target.exists():
        for old in skills_target.iterdir():
            if old.is_dir() and old.name.startswith("neander-"):
                shutil.rmtree(old)
        print("  [clean] removed old neander skills")

    # Wipe old neander-* agents (preserve non-neander agents)
    if agents_target.exists():
        for old in agents_target.iterdir():
            if old.is_dir() and old.name.startswith("neander-"):
                shutil.rmtree(old)
        print("  [clean] removed old neander agents")

    # Wipe old neander-* commands (legacy format)
    old_cmds = target_base / "commands"
    if old_cmds.is_dir():
        for old_cmd in old_cmds.glob("neander-*.md"):
            old_cmd.unlink()
            print(f"  [clean] removed old command {old_cmd.name}")

    # --- Copy scripts (fresh) ---
    scripts_src = bundled / "scripts"
    scripts_target.mkdir(parents=True, exist_ok=True)

    if scripts_src.exists():
        for script in scripts_src.iterdir():
            if script.is_dir():
                continue
            dest = scripts_target / script.name
            shutil.copy2(script, dest)
            dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
            print(f"  [copy] scripts/{script.name}")

    installed_scripts_dir = str(scripts_target)
    print(f"  Scripts  -> {installed_scripts_dir}\n")

    # --- Copy skills (fresh, with substitution) ---
    skills_src = bundled / "skills"

    if skills_src.exists():
        for skill_dir in sorted(skills_src.iterdir()):
            if not skill_dir.is_dir() or not skill_dir.name.startswith("neander-"):
                continue
            target_skill = skills_target / skill_dir.name
            target_skill.mkdir(parents=True, exist_ok=True)
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text()
                content = content.replace("__SCRIPTS_DIR__", installed_scripts_dir)
                content = content.replace("__HOME__", str(home))
                (target_skill / "SKILL.md").write_text(content)
                print(f"  [copy] skills/{skill_dir.name}")

    # --- Copy agents (fresh, with substitution) ---
    agents_src = bundled / "agents"

    if agents_src.exists():
        for agent_dir in sorted(agents_src.iterdir()):
            if not agent_dir.is_dir() or not agent_dir.name.startswith("neander-"):
                continue
            target_agent = agents_target / agent_dir.name
            target_agent.mkdir(parents=True, exist_ok=True)
            agent_md = agent_dir / "SKILL.md"
            if agent_md.exists():
                content = agent_md.read_text()
                content = content.replace("__SCRIPTS_DIR__", installed_scripts_dir)
                content = content.replace("__HOME__", str(home))
                (target_agent / "SKILL.md").write_text(content)
                print(f"  [copy] agents/{agent_dir.name}")

    # --- Merge hooks + permissions into settings.json ---
    hooks_config_src = bundled / "hooks" / "hooks_config.json"
    if hooks_config_src.exists():
        with open(hooks_config_src) as f:
            raw = f.read().replace("__SCRIPTS_DIR__", installed_scripts_dir)
        hooks_config = json.loads(raw)
    else:
        hooks_config = {"hooks": {}}

    settings_path = target_base / "settings.json"
    _merge_settings(settings_path, hooks_config, installed_scripts_dir)

    # --- Install pre-push hook (project mode only) ---
    if git_dir and git_dir.is_dir():
        _install_pre_push_hook(git_dir, installed_scripts_dir)
    elif git_dir:
        print(f"  [skip] {resolved_project} is not a git repo, skipping pre-push hook")

    # --- Update CLAUDE.md ---
    snippet_path = bundled / "hooks" / "project_claude_snippet.md"
    if snippet_path.exists():
        if global_mode:
            claude_md = home / ".claude" / "CLAUDE.md"
        else:
            claude_md = resolved_project / "CLAUDE.md"
        _update_claude_md(claude_md, snippet_path, installed_scripts_dir)

    print()
    print("Done! Installed:")
    print()
    print("  Skills (Claude auto-invokes based on conversation):")
    print("    /neander-status        — Checkpoints overview")
    print("    /neander-search        — Search checkpoints")
    print("    /neander-transcript    — View transcript")
    print("    /neander-summarize     — AI summary with caching")
    print("    /neander-session-stats — Token usage, costs")
    print("    /neander-redact        — Scan for secrets (user-invoked only)")
    print()
    print("  CLI (run in terminal):")
    print("    neander-checkpoints resume <checkpoint-id>")
    print()

    return 0
