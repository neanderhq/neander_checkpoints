#!/usr/bin/env bash
#
# build.sh — Bundle source files into the pip package before publishing.
#
# Copies scripts, skills, and hook configs from source into
# src/neander_checkpoints/bundled/ so they're included in the package.
#
# Usage: ./build.sh
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BUNDLED="$REPO_ROOT/src/neander_checkpoints/bundled"

echo "Building neander-checkpoints package..."

# Clean previous bundle
rm -rf "$BUNDLED"
mkdir -p "$BUNDLED/scripts" "$BUNDLED/skills" "$BUNDLED/agents" "$BUNDLED/hooks"

# Copy scripts
for f in "$REPO_ROOT/scripts/"*; do
    [ -d "$f" ] && continue  # skip __pycache__
    cp "$f" "$BUNDLED/scripts/"
    echo "  [bundle] scripts/$(basename "$f")"
done

# Copy skills
for skill_dir in "$REPO_ROOT/skills/neander-"*; do
    name="$(basename "$skill_dir")"
    mkdir -p "$BUNDLED/skills/$name"
    cp "$skill_dir/SKILL.md" "$BUNDLED/skills/$name/"
    echo "  [bundle] skills/$name"
done

# Copy agents
for agent_dir in "$REPO_ROOT/agents/neander-"*; do
    name="$(basename "$agent_dir")"
    mkdir -p "$BUNDLED/agents/$name"
    cp "$agent_dir/SKILL.md" "$BUNDLED/agents/$name/"
    echo "  [bundle] agents/$name"
done

# Copy hook configs
for f in "$REPO_ROOT/config/"*; do
    cp "$f" "$BUNDLED/hooks/"
    echo "  [bundle] hooks/$(basename "$f")"
done

echo ""
echo "Bundle created at: $BUNDLED"
echo "To build the package: python -m build"
echo "To install locally: pip install -e ."
