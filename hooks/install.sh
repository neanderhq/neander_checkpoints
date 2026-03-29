#!/usr/bin/env bash
#
# install.sh — Install neander_code_sessions skills, scripts, and hooks.
#
# Usage:
#   ./hooks/install.sh /path/to/project   # skills + scripts + hooks into project
#   ./hooks/install.sh --global           # everything into ~/.claude/
#
# What gets installed:
#   - Scripts  → <target>/.claude/scripts/
#   - Skills   → <target>/.claude/skills/    (auto-invoked by Claude)
#   - Hooks    → <target>/.claude/settings.json
#   - Perms    → <target>/.claude/settings.json
#   - Pre-push → <target>/.git/hooks/pre-push  (project mode only)
#   - CLAUDE.md appended with session management instructions
#

set -euo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SELF_DIR/.." && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
SKILLS_SRC="$PROJECT_ROOT/.claude/skills"

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
            echo "  ./hooks/install.sh /path/to/project   # install into project"
            echo "  ./hooks/install.sh --global           # install globally"
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
    echo "  ./hooks/install.sh /path/to/project   # install into project"
    echo "  ./hooks/install.sh --global           # install globally"
    exit 1
fi

if [ -z "$MODE" ]; then
    MODE="project"
fi

# --- Resolve targets based on mode ---
case "$MODE" in
    global)
        HOOKS_TARGET="$GLOBAL_CLAUDE_DIR"
        HOOKS_SETTINGS="$HOOKS_TARGET/settings.json"
        GIT_TARGET=""
        echo "Installing neander_code_sessions (global):"
        echo "  Hooks    → $HOOKS_SETTINGS"
        echo "  Pre-push → skipped (global mode)"
        ;;
    project)
        if [[ "$PROJECT_TARGET" == "." ]]; then
            PROJECT_TARGET="$(pwd)"
        else
            PROJECT_TARGET="$(cd "$PROJECT_TARGET" && pwd)"
        fi
        HOOKS_TARGET="$PROJECT_TARGET/.claude"
        HOOKS_SETTINGS="$HOOKS_TARGET/settings.json"
        GIT_TARGET="$PROJECT_TARGET"
        echo "Installing neander_code_sessions into: $PROJECT_TARGET"
        echo "  Hooks    → $HOOKS_SETTINGS"
        ;;
esac

# --- Copy scripts ---
case "$MODE" in
    project)  SCRIPTS_TARGET="$PROJECT_TARGET/.claude/scripts" ;;
    global)   SCRIPTS_TARGET="$GLOBAL_CLAUDE_DIR/scripts" ;;
esac

mkdir -p "$SCRIPTS_TARGET"
for script in "$SCRIPTS_DIR"/*; do
    [ -d "$script" ] && continue
    name="$(basename "$script")"
    cp "$script" "$SCRIPTS_TARGET/$name"
    chmod +x "$SCRIPTS_TARGET/$name"
    echo "  [copy] scripts/$name"
done

INSTALLED_SCRIPTS_DIR="$SCRIPTS_TARGET"
echo "  Scripts  → $INSTALLED_SCRIPTS_DIR"
echo ""

# --- Copy skills (with __SCRIPTS_DIR__ substitution) ---
case "$MODE" in
    project)  SKILLS_TARGET="$PROJECT_TARGET/.claude/skills" ;;
    global)   SKILLS_TARGET="$GLOBAL_CLAUDE_DIR/skills" ;;
esac

for skill_dir in "$SKILLS_SRC"/neander-*; do
    name="$(basename "$skill_dir")"
    target_dir="$SKILLS_TARGET/$name"
    mkdir -p "$target_dir"
    sed -e "s|__SCRIPTS_DIR__|$INSTALLED_SCRIPTS_DIR|g" -e "s|__HOME__|$HOME|g" "$skill_dir/SKILL.md" > "$target_dir/SKILL.md"
    echo "  [copy] skills/$name"
done

# --- Clean up old .claude/commands/ from previous installs ---
case "$MODE" in
    project)  OLD_CMDS="$PROJECT_TARGET/.claude/commands" ;;
    global)   OLD_CMDS="$GLOBAL_CLAUDE_DIR/commands" ;;
esac
if [ -d "$OLD_CMDS" ]; then
    for old_cmd in "$OLD_CMDS"/neander-*.md; do
        [ -f "$old_cmd" ] && rm "$old_cmd" && echo "  [clean] removed old $(basename "$old_cmd")"
    done
fi

# --- Install hooks + permissions ---
mkdir -p "$HOOKS_TARGET"
HOOKS_TEMPLATE="$SELF_DIR/hooks_config.json"

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
    f"Bash(bash {scripts_dir}/on_stop.sh*)",
    f"Bash(bash {scripts_dir}/link_commit.sh*)",
    f"Bash(bash {scripts_dir}/restore.sh*)",
    f"Bash(bash {scripts_dir}/save_summary.sh*)",
    f"Bash(bash {scripts_dir}/persist_summary.sh*)",
    f"Bash(find {os.path.expanduser('~')}/.claude/projects *)",
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

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  [{action}] hooks + permissions into {settings_file}")
if added:
    print(f"  [add] {added} permission rules")
else:
    print(f"  [skip] permissions already present")
PYEOF

# --- Install git pre-push hook (project mode only) ---
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
            sed "s|__SCRIPTS_DIR__|$INSTALLED_SCRIPTS_DIR|g" "$SNIPPET" >> "$CLAUDE_MD"
            echo "  [append] CLAUDE.md"
        else
            # Update existing section with current paths
            python3 - "$CLAUDE_MD" "$SNIPPET" "$INSTALLED_SCRIPTS_DIR" <<'PYEOF'
import re, sys

claude_md = sys.argv[1]
snippet_file = sys.argv[2]
scripts_dir = sys.argv[3]

with open(claude_md) as f:
    content = f.read()

with open(snippet_file) as f:
    snippet = f.read().replace("__SCRIPTS_DIR__", scripts_dir)

# Replace existing section
content = re.sub(
    r'## Session Management \(neander_code_sessions\).*',
    snippet, content, flags=re.DOTALL
)

with open(claude_md, 'w') as f:
    f.write(content)

print("  [update] CLAUDE.md with current paths")
PYEOF
        fi
    else
        sed "s|__SCRIPTS_DIR__|$INSTALLED_SCRIPTS_DIR|g" "$SNIPPET" > "$CLAUDE_MD"
        echo "  [create] CLAUDE.md"
    fi
fi

echo ""
echo "Done! Skills installed (auto-invoked by Claude):"
echo "  /neander-status        — Active and recent sessions"
echo "  /neander-search        — Search across sessions"
echo "  /neander-transcript    — Condensed transcript view"
echo "  /neander-summarize     — AI summary of a session"
echo "  /neander-session-stats — Token usage, costs, file stats"
echo "  /neander-resume        — Resume a session from checkpoint"
echo "  /neander-redact        — Scan and redact secrets (user-invoked only)"
echo ""
echo "Claude will also use these proactively when the conversation calls for it."
echo ""
echo "To uninstall: $SELF_DIR/uninstall.sh $([ "$MODE" = "global" ] && echo "--global" || echo "")"
