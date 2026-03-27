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
        COMMANDS_TARGET="$GLOBAL_CLAUDE_DIR/commands"
        HOOKS_TARGET="$PROJECT_TARGET/.claude"
        HOOKS_SETTINGS="$HOOKS_TARGET/settings.json"
        GIT_TARGET="$PROJECT_TARGET"
        echo "Installing neander_code_sessions into: $PROJECT_TARGET"
        echo "  Commands → $COMMANDS_TARGET (global)"
        echo "  Hooks    → $HOOKS_SETTINGS"
        ;;
esac

echo "  Scripts  → $SCRIPTS_DIR"
echo ""

# --- Make scripts executable ---
chmod +x "$SCRIPTS_DIR"/*.sh "$SCRIPTS_DIR"/*.py

# --- Install commands (symlink) ---
mkdir -p "$COMMANDS_TARGET"

for cmd in "$COMMANDS_SRC"/*.md; do
    name="$(basename "$cmd")"
    target_file="$COMMANDS_TARGET/$name"
    if [ -e "$target_file" ] && [ ! -L "$target_file" ]; then
        echo "  [skip] commands/$name already exists (not a symlink, won't overwrite)"
    elif [ -L "$target_file" ]; then
        # Update existing symlink
        ln -sf "$cmd" "$target_file"
        echo "  [update] commands/$name"
    else
        ln -sf "$cmd" "$target_file"
        echo "  [link] commands/$name"
    fi
done

# --- Install hooks ---
mkdir -p "$HOOKS_TARGET"
HOOKS_TEMPLATE="$SELF_DIR/hooks_config.json"

# Replace placeholder with actual scripts dir
HOOKS_JSON="$(sed "s|__SCRIPTS_DIR__|$SCRIPTS_DIR|g" "$HOOKS_TEMPLATE")"

if [ -f "$HOOKS_SETTINGS" ]; then
    python3 -c "
import json, sys

with open('$HOOKS_SETTINGS') as f:
    settings = json.load(f)

new_hooks = json.loads('''$HOOKS_JSON''')['hooks']
existing_hooks = settings.get('hooks', {})

for event, handlers in new_hooks.items():
    if event not in existing_hooks:
        existing_hooks[event] = handlers
    else:
        existing_cmds = {h.get('hooks', [{}])[0].get('command', '') for h in existing_hooks[event]}
        for handler in handlers:
            cmd = handler.get('hooks', [{}])[0].get('command', '')
            if cmd not in existing_cmds:
                existing_hooks[event].append(handler)

settings['hooks'] = existing_hooks

with open('$HOOKS_SETTINGS', 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')

print('  [merge] hooks merged into $HOOKS_SETTINGS')
"
else
    echo "$HOOKS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
with open('$HOOKS_SETTINGS', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
print('  [create] $HOOKS_SETTINGS')
"
fi

# --- Install git pre-push hook (only if we have a git target) ---
if [ -n "$GIT_TARGET" ]; then
    GIT_DIR="$GIT_TARGET/.git"
    if [ -d "$GIT_DIR" ]; then
        HOOKS_DIR="$GIT_DIR/hooks"
        mkdir -p "$HOOKS_DIR"
        PRE_PUSH="$HOOKS_DIR/pre-push"

        REDACT_HOOK='#!/usr/bin/env bash
# Auto-redact session transcripts before push [neander_code_sessions]
SCRIPTS_DIR="'"$SCRIPTS_DIR"'"
CHECKPOINT_BRANCH="claude-sessions/checkpoints"

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

echo ""
echo "Done! Available slash commands:"
echo "  /summarize     — AI summary of a session"
echo "  /transcript    — Condensed transcript view"
echo "  /session-stats — Token usage, costs, file stats"
echo "  /rewind        — List/restore checkpoints"
echo "  /resume        — Resume a session from checkpoint"
echo "  /redact        — Scan and redact secrets"
echo ""
echo "To uninstall: $SELF_DIR/uninstall.sh $([ "$MODE" = "global" ] && echo "--global" || echo "")"
