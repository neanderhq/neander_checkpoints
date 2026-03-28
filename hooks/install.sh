#!/usr/bin/env bash
#
# install.sh — Install neander_code_sessions hooks and commands.
#
# Usage:
#   ./hooks/install.sh /path/to/project   # commands global, hooks + pre-push into project
#   ./hooks/install.sh --global           # commands + hooks both global, no pre-push
#
# Default (with path):
#   - Commands → ~/.claude/commands/  (available everywhere)
#   - Hooks    → <path>/.claude/settings.json  (opt-in per repo)
#   - Pre-push → <path>/.git/hooks/pre-push
#
# --global:
#   - Commands → ~/.claude/commands/
#   - Hooks    → ~/.claude/settings.json
#   - Pre-push skipped (makes no sense globally)
#

set -euo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SELF_DIR/.." && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
COMMANDS_SRC="$PROJECT_ROOT/.claude/commands"

GLOBAL_CLAUDE_DIR="$HOME/.claude"
MODE=""
PROJECT_TARGET=""

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --global)
            MODE="global"
            shift
            ;;
        -h|--help)
            echo "Usage:"
            echo "  ./hooks/install.sh /path/to/project   # commands global, hooks into project"
            echo "  ./hooks/install.sh --global           # everything global"
            exit 0
            ;;
        *)
            PROJECT_TARGET="$1"
            shift
            ;;
    esac
done

# --- Validate args ---
if [ -z "$MODE" ] && [ -z "$PROJECT_TARGET" ]; then
    echo "Usage:"
    echo "  ./hooks/install.sh /path/to/project   # commands global, hooks into project"
    echo "  ./hooks/install.sh --global           # everything global"
    exit 1
fi

if [ -z "$MODE" ]; then
    MODE="project"
fi

# --- Resolve targets based on mode ---
case "$MODE" in
    global)
        COMMANDS_TARGET="$GLOBAL_CLAUDE_DIR/commands"
        HOOKS_TARGET="$GLOBAL_CLAUDE_DIR"
        HOOKS_SETTINGS="$HOOKS_TARGET/settings.json"
        GIT_TARGET=""
        echo "Installing neander_code_sessions (global):"
        echo "  Commands → $COMMANDS_TARGET"
        echo "  Hooks    → $HOOKS_SETTINGS"
        echo "  Pre-push → skipped (global mode)"
        ;;
    project)
        # Resolve relative paths
        if [[ "$PROJECT_TARGET" == "." ]]; then
            PROJECT_TARGET="$(pwd)"
        else
            PROJECT_TARGET="$(cd "$PROJECT_TARGET" && pwd)"
        fi
        COMMANDS_TARGET="$PROJECT_TARGET/.claude/commands"
        HOOKS_TARGET="$PROJECT_TARGET/.claude"
        HOOKS_SETTINGS="$HOOKS_TARGET/settings.json"
        GIT_TARGET="$PROJECT_TARGET"
        echo "Installing neander_code_sessions into: $PROJECT_TARGET"
        echo "  Commands → $COMMANDS_TARGET"
        echo "  Hooks    → $HOOKS_SETTINGS"
        ;;
esac

# --- Copy scripts into target ---
case "$MODE" in
    project)
        SCRIPTS_TARGET="$PROJECT_TARGET/.claude/scripts"
        ;;
    global)
        SCRIPTS_TARGET="$GLOBAL_CLAUDE_DIR/scripts"
        ;;
esac

mkdir -p "$SCRIPTS_TARGET"
for script in "$SCRIPTS_DIR"/*; do
    name="$(basename "$script")"
    cp "$script" "$SCRIPTS_TARGET/$name"
    chmod +x "$SCRIPTS_TARGET/$name"
    echo "  [copy] scripts/$name"
done

# Commands and hooks reference the installed scripts location
INSTALLED_SCRIPTS_DIR="$SCRIPTS_TARGET"
echo "  Scripts  → $INSTALLED_SCRIPTS_DIR"
echo ""

# --- Install skills (copy with path substitution) ---
SKILLS_SRC="$PROJECT_ROOT/.claude/skills"
case "$MODE" in
    project)  SKILLS_TARGET="$PROJECT_TARGET/.claude/skills" ;;
    global)   SKILLS_TARGET="$GLOBAL_CLAUDE_DIR/skills" ;;
esac

for skill_dir in "$SKILLS_SRC"/neander-*; do
    name="$(basename "$skill_dir")"
    target_dir="$SKILLS_TARGET/$name"
    mkdir -p "$target_dir"
    sed "s|__SCRIPTS_DIR__|$INSTALLED_SCRIPTS_DIR|g" "$skill_dir/SKILL.md" > "$target_dir/SKILL.md"
    echo "  [copy] skills/$name"
done

# --- Clean up old commands from previous installs ---
COMMANDS_TARGET_OLD=""
case "$MODE" in
    project)  COMMANDS_TARGET_OLD="$PROJECT_TARGET/.claude/commands" ;;
    global)   COMMANDS_TARGET_OLD="$GLOBAL_CLAUDE_DIR/commands" ;;
esac
if [ -d "$COMMANDS_TARGET_OLD" ]; then
    for old_cmd in "$COMMANDS_TARGET_OLD"/neander-*.md; do
        [ -f "$old_cmd" ] && rm "$old_cmd" && echo "  [clean] removed old $(basename "$old_cmd")"
    done
fi

# --- Install hooks ---
mkdir -p "$HOOKS_TARGET"
HOOKS_TEMPLATE="$SELF_DIR/hooks_config.json"

# Create a temp file with the scripts dir substituted
HOOKS_TMPFILE="$(mktemp)"
sed "s|__SCRIPTS_DIR__|$INSTALLED_SCRIPTS_DIR|g" "$HOOKS_TEMPLATE" > "$HOOKS_TMPFILE"
trap "rm -f '$HOOKS_TMPFILE'" EXIT

python3 - "$HOOKS_TMPFILE" "$HOOKS_SETTINGS" "$INSTALLED_SCRIPTS_DIR" <<'PYEOF'
import json, sys, os

hooks_file = sys.argv[1]
settings_file = sys.argv[2]
scripts_dir = sys.argv[3]

with open(hooks_file) as f:
    new_hooks = json.load(f)["hooks"]

if os.path.exists(settings_file):
    with open(settings_file) as f:
        settings = json.load(f)
    action = "merge"
else:
    settings = {}
    action = "create"

# --- Merge hooks ---
existing_hooks = settings.get("hooks", {})

for event, handlers in new_hooks.items():
    if event not in existing_hooks:
        existing_hooks[event] = handlers
    else:
        existing_cmds = {h.get("hooks", [{}])[0].get("command", "") for h in existing_hooks[event]}
        for handler in handlers:
            cmd = handler.get("hooks", [{}])[0].get("command", "")
            if cmd not in existing_cmds:
                existing_hooks[event].append(handler)

settings["hooks"] = existing_hooks

# --- Merge permissions ---
new_permissions = [
    f"Bash(python3 {scripts_dir}/parse_jsonl.py*)",
    f"Bash(python3 {scripts_dir}/redact.py*)",
    f"Bash(bash {scripts_dir}/checkpoint.sh*)",
    f"Bash(bash {scripts_dir}/detect_commit.sh*)",
    f"Bash(bash {scripts_dir}/link_commit.sh*)",
    f"Bash(bash {scripts_dir}/restore.sh*)",
    f"Bash(bash {scripts_dir}/save_summary.sh*)",
    "Bash(find ~/.claude/projects*)",
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

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  [{action}] hooks into {settings_file}")
if added:
    print(f"  [add] {added} permission rules")
else:
    print(f"  [skip] permissions already present")
PYEOF

# --- Install git pre-push hook (only if we have a git target) ---
if [ -n "$GIT_TARGET" ]; then
    GIT_DIR="$GIT_TARGET/.git"
    if [ -d "$GIT_DIR" ]; then
        HOOKS_DIR="$GIT_DIR/hooks"
        mkdir -p "$HOOKS_DIR"
        PRE_PUSH="$HOOKS_DIR/pre-push"

        REDACT_HOOK='#!/usr/bin/env bash
# Auto-redact session transcripts before push [neander_code_sessions]
SCRIPTS_DIR="'"$INSTALLED_SCRIPTS_DIR"'"
CHECKPOINT_BRANCH="neander/checkpoints/v1"

while read local_ref local_sha remote_ref remote_sha; do
    if echo "$local_ref" | grep -q "$CHECKPOINT_BRANCH"; then
        echo "[neander_code_sessions] Redacting transcripts on checkpoint branch..."
        git diff --name-only "$remote_sha..$local_sha" -- "*.jsonl" 2>/dev/null | while read jsonl; do
            python3 "$SCRIPTS_DIR/redact.py" "$jsonl" "$jsonl" 2>/dev/null || true
        done
    fi
done
'

        if [ -f "$PRE_PUSH" ]; then
            if ! grep -q "neander_code_sessions" "$PRE_PUSH"; then
                echo "" >> "$PRE_PUSH"
                echo "$REDACT_HOOK" >> "$PRE_PUSH"
                echo "  [append] pre-push hook"
            else
                echo "  [skip] pre-push hook already installed"
            fi
        else
            echo "$REDACT_HOOK" > "$PRE_PUSH"
            chmod +x "$PRE_PUSH"
            echo "  [create] pre-push hook"
        fi
    else
        echo "  [skip] $GIT_TARGET is not a git repo, skipping pre-push hook"
    fi
fi

# --- Append session management instructions to CLAUDE.md ---
SNIPPET="$SELF_DIR/project_claude_snippet.md"
case "$MODE" in
    project)  CLAUDE_MD="$PROJECT_TARGET/CLAUDE.md" ;;
    global)   CLAUDE_MD="$HOME/.claude/CLAUDE.md" ;;
esac

if [ -f "$SNIPPET" ]; then
    if [ -f "$CLAUDE_MD" ]; then
        if ! grep -q "neander_code_sessions" "$CLAUDE_MD"; then
            echo "" >> "$CLAUDE_MD"
            cat "$SNIPPET" >> "$CLAUDE_MD"
            echo "  [append] CLAUDE.md with session management instructions"
        else
            echo "  [skip] CLAUDE.md already has session management section"
        fi
    else
        cat "$SNIPPET" > "$CLAUDE_MD"
        echo "  [create] CLAUDE.md with session management instructions"
    fi
fi

echo ""
echo "Done! Available slash commands:"
echo "  /neander-status        — Active and recent sessions"
echo "  /neander-search        — Search across sessions"
echo "  /neander-transcript    — Condensed transcript view"
echo "  /neander-summarize     — AI summary of a session"
echo "  /neander-session-stats — Token usage, costs, file stats"
echo "  /neander-resume        — Resume a session from checkpoint"
echo "  /neander-rewind        — List/restore checkpoints"
echo "  /neander-redact        — Scan and redact secrets"
echo ""
echo "Claude will also use these tools proactively when context calls for it."
echo ""
echo "To uninstall: $SELF_DIR/uninstall.sh $([ "$MODE" = "global" ] && echo "--global" || echo "")"
