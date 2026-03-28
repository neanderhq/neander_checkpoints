#!/usr/bin/env bash
#
# uninstall.sh — Remove neander_code_sessions hooks and commands.
#
# Usage:
#   ./hooks/uninstall.sh /path/to/project   # commands from global, hooks from project
#   ./hooks/uninstall.sh --global           # commands + hooks from global
#

set -euo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SELF_DIR/.." && pwd)"
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
            echo "  ./hooks/uninstall.sh /path/to/project   # commands from global, hooks from project"
            echo "  ./hooks/uninstall.sh --global           # everything from global"
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
    echo "  ./hooks/uninstall.sh /path/to/project   # commands from global, hooks from project"
    echo "  ./hooks/uninstall.sh --global           # everything from global"
    exit 1
fi

if [ -z "$MODE" ]; then
    MODE="project"
fi

# --- Resolve targets ---
case "$MODE" in
    global)
        COMMANDS_TARGET="$GLOBAL_CLAUDE_DIR/commands"
        HOOKS_SETTINGS="$GLOBAL_CLAUDE_DIR/settings.json"
        GIT_TARGET=""
        echo "Uninstalling neander_code_sessions (global):"
        echo "  Commands ← $COMMANDS_TARGET"
        echo "  Hooks    ← $HOOKS_SETTINGS"
        ;;
    project)
        if [[ "$PROJECT_TARGET" == "." ]]; then
            PROJECT_TARGET="$(pwd)"
        else
            PROJECT_TARGET="$(cd "$PROJECT_TARGET" && pwd)"
        fi
        COMMANDS_TARGET="$PROJECT_TARGET/.claude/commands"
        HOOKS_SETTINGS="$PROJECT_TARGET/.claude/settings.json"
        GIT_TARGET="$PROJECT_TARGET"
        echo "Uninstalling neander_code_sessions from: $PROJECT_TARGET"
        echo "  Commands ← $COMMANDS_TARGET"
        echo "  Hooks    ← $HOOKS_SETTINGS"
        ;;
esac
echo ""

# --- Remove installed scripts ---
case "$MODE" in
    project)
        SCRIPTS_TARGET="$PROJECT_TARGET/.claude/scripts"
        ;;
    global)
        SCRIPTS_TARGET="$GLOBAL_CLAUDE_DIR/scripts"
        ;;
esac

if [ -d "$SCRIPTS_TARGET" ]; then
    rm -rf "$SCRIPTS_TARGET"
    echo "  [remove] scripts/"
fi

# --- Remove installed skills ---
case "$MODE" in
    project)  SKILLS_TARGET="$PROJECT_TARGET/.claude/skills" ;;
    global)   SKILLS_TARGET="$GLOBAL_CLAUDE_DIR/skills" ;;
esac

for skill_dir in "$SKILLS_TARGET"/neander-*; do
    if [ -d "$skill_dir" ]; then
        rm -rf "$skill_dir"
        echo "  [remove] skills/$(basename "$skill_dir")"
    fi
done

# --- Remove installed commands ---
for cmd in "$COMMANDS_SRC"/*.md; do
    name="$(basename "$cmd")"
    target_file="$COMMANDS_TARGET/$name"
    if [ -f "$target_file" ]; then
        rm "$target_file"
        echo "  [remove] commands/$name"
    fi
done

# --- Remove hooks from settings.json ---
if [ -f "$HOOKS_SETTINGS" ]; then
    python3 -c "
import json

with open('$HOOKS_SETTINGS') as f:
    settings = json.load(f)

hooks = settings.get('hooks', {})
changed = False

for event in list(hooks.keys()):
    original_len = len(hooks[event])
    hooks[event] = [
        h for h in hooks[event]
        if 'checkpoint.sh' not in json.dumps(h)
        and 'detect_commit.sh' not in json.dumps(h)
    ]
    if len(hooks[event]) != original_len:
        changed = True
    if not hooks[event]:
        del hooks[event]

if changed:
    if hooks:
        settings['hooks'] = hooks
    else:
        settings.pop('hooks', None)
    with open('$HOOKS_SETTINGS', 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')
    print('  [clean] removed hooks from settings.json')
else:
    print('  [skip] no hooks to remove')
"
else
    echo "  [skip] no settings.json found"
fi

# --- Remove pre-push hook content ---
if [ -n "$GIT_TARGET" ]; then
    GIT_DIR="$GIT_TARGET/.git"
    if [ -d "$GIT_DIR" ]; then
        PRE_PUSH="$GIT_DIR/hooks/pre-push"
        if [ -f "$PRE_PUSH" ] && grep -q "neander_code_sessions" "$PRE_PUSH"; then
            # Remove our block: from the comment marker to the closing 'done'
            python3 -c "
import re
with open('$PRE_PUSH') as f:
    content = f.read()
# Remove the neander_code_sessions block
content = re.sub(
    r'# Auto-redact session transcripts before push \[neander_code_sessions\].*?^done\n?',
    '', content, flags=re.DOTALL | re.MULTILINE
)
content = content.strip()
if content and content != '#!/usr/bin/env bash':
    with open('$PRE_PUSH', 'w') as f:
        f.write(content + '\n')
    print('  [clean] removed our block from pre-push hook')
else:
    import os
    os.remove('$PRE_PUSH')
    print('  [remove] pre-push hook (was only ours)')
"
        fi
    fi
fi

echo ""
echo "Done!"
