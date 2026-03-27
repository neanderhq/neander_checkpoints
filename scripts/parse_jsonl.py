#!/usr/bin/env python3
"""
Core JSONL transcript parser for Claude Code sessions.

Provides functions to parse, filter, and extract structured data
from Claude Code session JSONL files.
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def find_session_files(project_path: str = None) -> list[dict]:
    """Find all session JSONL files, optionally filtered by project path."""
    sessions = []
    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        if project_path:
            decoded = project_dir.name.replace("-", "/", 1).replace("-", "/")
            if project_path not in decoded and decoded not in project_path:
                continue
        for f in project_dir.glob("*.jsonl"):
            if f.stem == "memory" or f.name.startswith("."):
                continue
            sessions.append({
                "path": str(f),
                "session_id": f.stem,
                "project_dir": project_dir.name,
                "size_bytes": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime),
            })
    sessions.sort(key=lambda s: s["modified"], reverse=True)
    return sessions


def parse_jsonl(filepath: str, offset: int = 0) -> list[dict]:
    """Parse a JSONL file, optionally starting from a line offset."""
    lines = []
    with open(filepath, "r") as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return lines


def extract_messages(entries: list[dict]) -> list[dict]:
    """Extract user/assistant message pairs in order."""
    messages = []
    for entry in entries:
        t = entry.get("type")
        if t not in ("user", "assistant"):
            continue
        msg = entry.get("message", {})
        content = msg.get("content", "")

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        name = block.get("name", "unknown")
                        inp = block.get("input", {})
                        parts.append(f"[Tool: {name}]")
                        if name in ("Read", "Glob", "Grep"):
                            path = inp.get("file_path") or inp.get("pattern") or inp.get("path", "")
                            if path:
                                parts.append(f"  → {path}")
                        elif name == "Bash":
                            cmd = inp.get("command", "")
                            parts.append(f"  → {cmd[:200]}")
                        elif name in ("Write", "Edit"):
                            path = inp.get("file_path", "")
                            parts.append(f"  → {path}")
                        elif name == "Agent":
                            desc = inp.get("description", "")
                            parts.append(f"  → {desc}")
                    elif block.get("type") == "tool_result":
                        continue  # skip tool results in condensed view
                    elif block.get("type") == "thinking":
                        continue  # skip thinking blocks
            text = "\n".join(parts)
        else:
            text = str(content)

        # Strip IDE-injected context tags
        text = re.sub(r"<(?:ide_opened_file|system-reminder|context)>.*?</(?:ide_opened_file|system-reminder|context)>", "", text, flags=re.DOTALL)
        text = text.strip()

        if not text:
            continue

        messages.append({
            "role": t,
            "uuid": entry.get("uuid"),
            "timestamp": entry.get("timestamp"),
            "text": text,
            "model": msg.get("model"),
            "stop_reason": msg.get("stop_reason"),
        })
    return messages


def extract_tool_calls(entries: list[dict]) -> list[dict]:
    """Extract all tool calls from assistant messages."""
    tools = []
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools.append({
                    "name": block.get("name"),
                    "id": block.get("id"),
                    "input": block.get("input", {}),
                    "timestamp": entry.get("timestamp"),
                    "uuid": entry.get("uuid"),
                })
    return tools


def extract_modified_files(entries: list[dict]) -> list[str]:
    """Extract file paths modified by Write/Edit/NotebookEdit tools."""
    files = set()
    for tool in extract_tool_calls(entries):
        if tool["name"] in ("Write", "Edit", "NotebookEdit"):
            path = tool["input"].get("file_path", "")
            if path:
                files.add(path)
    return sorted(files)


def calculate_token_usage(entries: list[dict]) -> dict:
    """Calculate deduplicated token usage across all API calls."""
    seen_ids = set()
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        msg = entry.get("message", {})
        msg_id = msg.get("id")
        if msg_id and msg_id in seen_ids:
            continue
        if msg_id:
            seen_ids.add(msg_id)
        usage = msg.get("usage", {})
        for key in totals:
            totals[key] += usage.get(key, 0)
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    return totals


def get_session_metadata(entries: list[dict]) -> dict:
    """Extract session-level metadata."""
    first_ts = None
    last_ts = None
    git_branch = None
    cwd = None
    session_id = None
    slug = None
    models = set()

    for entry in entries:
        ts = entry.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts
        if not git_branch:
            git_branch = entry.get("gitBranch")
        if not cwd:
            cwd = entry.get("cwd")
        if not session_id:
            session_id = entry.get("sessionId")
        if not slug:
            slug = entry.get("slug")
        model = entry.get("message", {}).get("model")
        if model:
            models.add(model)

    return {
        "session_id": session_id,
        "slug": slug,
        "git_branch": git_branch,
        "cwd": cwd,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "models": sorted(models),
    }


def get_file_snapshots(entries: list[dict]) -> list[dict]:
    """Extract file-history-snapshot entries for rewind support."""
    snapshots = []
    for entry in entries:
        if entry.get("type") != "file-history-snapshot":
            continue
        snapshot = entry.get("snapshot", {})
        snapshots.append({
            "message_id": entry.get("messageId"),
            "timestamp": snapshot.get("timestamp"),
            "files": list(snapshot.get("trackedFileBackups", {}).keys()),
            "backups": snapshot.get("trackedFileBackups", {}),
        })
    return snapshots


def format_condensed_transcript(messages: list[dict], max_lines: int = None) -> str:
    """Format messages into a condensed readable transcript."""
    lines = []
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        ts = msg.get("timestamp", "")
        if ts:
            ts = ts.split("T")[1][:8] if "T" in ts else ts
        header = f"[{role}] {ts}"
        lines.append(header)
        text = msg["text"]
        # Truncate very long messages
        if len(text) > 2000:
            text = text[:2000] + "\n... (truncated)"
        lines.append(text)
        lines.append("")

    output = "\n".join(lines)
    if max_lines:
        output = "\n".join(output.split("\n")[:max_lines])
    return output


def session_summary_data(filepath: str) -> dict:
    """Get all structured data for a session — used by skills and scripts."""
    entries = parse_jsonl(filepath)
    messages = extract_messages(entries)
    tokens = calculate_token_usage(entries)
    meta = get_session_metadata(entries)
    files = extract_modified_files(entries)
    snapshots = get_file_snapshots(entries)

    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]

    return {
        "metadata": meta,
        "token_usage": tokens,
        "modified_files": files,
        "snapshots": snapshots,
        "message_counts": {
            "user": len(user_msgs),
            "assistant": len(assistant_msgs),
            "total": len(messages),
        },
        "first_prompt": user_msgs[0]["text"][:500] if user_msgs else "",
        "messages": messages,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse Claude Code session JSONL")
    parser.add_argument("command", choices=["list", "stats", "transcript", "files", "snapshots"])
    parser.add_argument("--session", "-s", help="Session JSONL file path")
    parser.add_argument("--project", "-p", help="Project path filter")
    parser.add_argument("--max-lines", "-n", type=int, help="Max transcript lines")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.command == "list":
        sessions = find_session_files(args.project)
        if args.json:
            print(json.dumps(sessions, default=str, indent=2))
        else:
            for s in sessions[:20]:
                size_kb = s["size_bytes"] / 1024
                print(f"  {s['session_id'][:12]}...  {s['modified']:%Y-%m-%d %H:%M}  {size_kb:>8.1f}KB  {s['project_dir']}")
        sys.exit(0)

    if not args.session:
        print("Error: --session required for this command", file=sys.stderr)
        sys.exit(1)

    if args.command == "stats":
        data = session_summary_data(args.session)
        if args.json:
            # Remove messages for JSON stats output
            data.pop("messages", None)
            print(json.dumps(data, default=str, indent=2))
        else:
            meta = data["metadata"]
            tokens = data["token_usage"]
            counts = data["message_counts"]
            print(f"Session:  {meta['session_id']}")
            print(f"Slug:     {meta['slug']}")
            print(f"Branch:   {meta['git_branch']}")
            print(f"CWD:      {meta['cwd']}")
            print(f"Models:   {', '.join(meta['models'])}")
            print(f"Duration: {meta['first_timestamp']} → {meta['last_timestamp']}")
            print(f"Messages: {counts['user']} user, {counts['assistant']} assistant")
            print(f"Tokens:   {tokens['total_tokens']:,} total ({tokens['input_tokens']:,} in, {tokens['output_tokens']:,} out)")
            print(f"Cache:    {tokens['cache_read_input_tokens']:,} read, {tokens['cache_creation_input_tokens']:,} created")
            print(f"Files:    {len(data['modified_files'])} modified")
            for f in data["modified_files"]:
                print(f"          {f}")

    elif args.command == "transcript":
        data = session_summary_data(args.session)
        print(format_condensed_transcript(data["messages"], args.max_lines))

    elif args.command == "files":
        entries = parse_jsonl(args.session)
        files = extract_modified_files(entries)
        if args.json:
            print(json.dumps(files, indent=2))
        else:
            for f in files:
                print(f)

    elif args.command == "snapshots":
        entries = parse_jsonl(args.session)
        snapshots = get_file_snapshots(entries)
        if args.json:
            print(json.dumps(snapshots, default=str, indent=2))
        else:
            for i, snap in enumerate(snapshots):
                print(f"Snapshot {i+1}: {snap['timestamp']}")
                print(f"  Message: {snap['message_id']}")
                print(f"  Files:   {len(snap['files'])}")
                for f in snap["files"]:
                    print(f"           {f}")
                print()
