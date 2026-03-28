#!/usr/bin/env bash
#
# uninstall.sh — Remove neander_code_sessions skills, scripts, hooks, and permissions.
#
# Usage:
#   ./hooks/uninstall.sh /path/to/project   # uninstall from project
#   ./hooks/uninstall.sh --global           # uninstall from global
#

set -euo pipefail

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
            echo "  ./hooks/uninstall.sh /path/to/project   # uninstall from project"
            echo "  ./hooks/uninstall.sh --global           # uninstall from global"
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
    echo "  ./hooks/uninstall.sh /path/to/project   # uninstall from project"
    echo "  ./hooks/uninstall.sh --global           # uninstall from global"
    exit 1
fi

if [ -z "$MODE" ]; then
    MODE="project"
fi

# --- Resolve targets ---
case "$MODE" in
    global)
        TARGET="$GLOBAL_CLAUDE_DIR"
        HOOKS_SETTINGS="$GLOBAL_CLAUDE_DIR/settings.json"
        GIT_TARGET=""
        CLAUDE_MD="$HOME/.claude/CLAUDE.md"
        echo "Uninstalling neander_code_sessions (global):"
        ;;
    project)
        if [[ "$PROJECT_TARGET" == "." ]]; then
            PROJECT_TARGET="$(pwd)"
        else
            PROJECT_TARGET="$(cd "$PROJECT_TARGET" && pwd)"
        fi
        TARGET="$PROJECT_TARGET/.claude"
        HOOKS_SETTINGS="$TARGET/settings.json"
        GIT_TARGET="$PROJECT_TARGET"
        CLAUDE_MD="$PROJECT_TARGET/CLAUDE.md"
        echo "Uninstalling neander_code_sessions from: $PROJECT_TARGET"
        ;;
esac
echo ""

# --- Remove scripts ---
if [ -d "$TARGET/scripts" ]; then
    rm -rf "$TARGET/scripts"
    echo "  [remove] scripts/"
fi

# --- Remove skills ---
for skill_dir in "$TARGET/skills"/neander-*; do
    if [ -d "$skill_dir" ]; then
        rm -rf "$skill_dir"
        echo "  [remove] skills/$(basename "$skill_dir")"
    fi
done

# --- Remove old commands (from previous installs) ---
if [ -d "$TARGET/commands" ]; then
    for old_cmd in "$TARGET/commands"/neander-*.md; do
        [ -f "$old_cmd" ] && rm "$old_cmd" && echo "  [remove] commands/$(basename "$old_cmd")"
    done
fi

# --- Remove hooks + permissions from settings.json ---
if [ -f "$HOOKS_SETTINGS" ]; then
    python3 - "$HOOKS_SETTINGS" <<'PYEOF'
import json, sys

settings_file = sys.argv[1]

with open(settings_file) as f:
    settings = json.load(f)

changed = False

# Remove hooks
hooks = settings.get("hooks", {})
for event in list(hooks.keys()):
    original_len = len(hooks[event])
    hooks[event] = [
        h for h in hooks[event]
        if "checkpoint.sh" not in json.dumps(h)
        and "detect_commit.sh" not in json.dumps(h)
    ]
    if len(hooks[event]) != original_len:
        changed = True
    if not hooks[event]:
        del hooks[event]

if hooks:
    settings["hooks"] = hooks
else:
    settings.pop("hooks", None)

# Remove permissions
permissions = settings.get("permissions", {})
allow = permissions.get("allow", [])
original_len = len(allow)
allow = [p for p in allow if "neander" not in p and ".claude/scripts" not in p and "~/.claude/projects" not in p]
if len(allow) != original_len:
    changed = True
if allow:
    permissions["allow"] = allow
    settings["permissions"] = permissions
else:
    settings.pop("permissions", None)

if changed:
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("  [clean] removed hooks + permissions from settings.json")
else:
    print("  [skip] no hooks or permissions to remove")
PYEOF
else
    echo "  [skip] no settings.json found"
fi

# --- Remove pre-push hook content ---
if [ -n "$GIT_TARGET" ]; then
    GIT_DIR="$GIT_TARGET/.git"
    if [ -d "$GIT_DIR" ]; then
        PRE_PUSH="$GIT_DIR/hooks/pre-push"
        if [ -f "$PRE_PUSH" ] && grep -q "neander_code_sessions" "$PRE_PUSH"; then
            python3 - "$PRE_PUSH" <<'PYEOF'
import re, sys, os

pre_push = sys.argv[1]
with open(pre_push) as f:
    content = f.read()

content = re.sub(
    r'# Auto-redact session transcripts before push \[neander_code_sessions\].*?^done\n?',
    '', content, flags=re.DOTALL | re.MULTILINE
)
content = content.strip()

if content and content != '#!/usr/bin/env bash':
    with open(pre_push, 'w') as f:
        f.write(content + '\n')
    print('  [clean] removed our block from pre-push hook')
else:
    os.remove(pre_push)
    print('  [remove] pre-push hook (was only ours)')
PYEOF
        fi
    fi
fi

# --- Remove session management section from CLAUDE.md ---
if [ -f "$CLAUDE_MD" ] && grep -q "neander_code_sessions" "$CLAUDE_MD"; then
    python3 - "$CLAUDE_MD" <<'PYEOF'
import re, sys

claude_md = sys.argv[1]
with open(claude_md) as f:
    content = f.read()

# Remove the session management section
content = re.sub(
    r'\n*## Session Management \(neander_code_sessions\).*',
    '', content, flags=re.DOTALL
)
content = content.rstrip() + '\n'

with open(claude_md, 'w') as f:
    f.write(content)

print('  [clean] removed session management section from CLAUDE.md')
PYEOF
fi

echo ""
echo "Done!"
