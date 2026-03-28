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


def _encode_project_path(path: str) -> str:
    """Encode a filesystem path the same way Claude Code does for project dir names."""
    # Claude Code replaces / with - and _ with -
    return path.replace("/", "-").replace("_", "-")


def find_session_files(project_path: str = None) -> list[dict]:
    """Find all session JSONL files, optionally filtered by project path."""
    sessions = []
    encoded_filter = _encode_project_path(project_path) if project_path else None
    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        if encoded_filter:
            if project_dir.name != encoded_filter:
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


def _strip_injected_tags(text: str) -> str:
    """Strip IDE-injected and system tags from text."""
    # Strip all XML-like tags injected by Claude Code / IDE
    text = re.sub(r"<[a-z_-]+>.*?</[a-z_-]+>", "", text, flags=re.DOTALL)
    # Also strip self-closing and empty tags
    text = re.sub(r"<[a-z_-]+\s*/?>", "", text)
    return text.strip()


def _tool_detail(name: str, inp: dict) -> str:
    """Extract a one-line detail string for a tool call."""
    if name == "Bash":
        desc = inp.get("description", "")
        cmd = inp.get("command", "")
        return desc if desc else (cmd[:120] + "..." if len(cmd) > 120 else cmd)
    if name in ("Read", "Glob"):
        return inp.get("file_path", "") or inp.get("pattern", "") or inp.get("path", "")
    if name == "Grep":
        pattern = inp.get("pattern", "")
        path = inp.get("path", "")
        return f"{pattern}" + (f" in {path}" if path else "")
    if name in ("Write", "Edit", "NotebookEdit"):
        return inp.get("file_path", "")
    if name == "Agent":
        return inp.get("description", "")
    if name == "Skill":
        return inp.get("skill", "")
    if name in ("WebFetch", "WebSearch"):
        return inp.get("url", "") or inp.get("query", "")
    return ""


def extract_messages(entries: list[dict]) -> list[dict]:
    """Extract user/assistant/tool entries in order for condensed transcript."""
    messages = []
    for entry in entries:
        t = entry.get("type")
        if t not in ("user", "assistant"):
            continue
        msg = entry.get("message", {})
        content = msg.get("content", "")
        timestamp = entry.get("timestamp")

        if t == "user":
            # Extract user text only (skip tool_result blocks)
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                text = "\n".join(parts)
            else:
                text = str(content)

            text = _strip_injected_tags(text)
            # Skip skill instruction injections
            if text.startswith("Base directory for this skill:"):
                continue
            if not text:
                continue

            messages.append({"role": "user", "text": text, "timestamp": timestamp})

        elif t == "assistant":
            if not isinstance(content, list):
                continue

            # Emit text blocks and tool calls as separate entries
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = _strip_injected_tags(block.get("text", ""))
                    if text:
                        messages.append({"role": "assistant", "text": text, "timestamp": timestamp})
                elif block.get("type") == "tool_use":
                    name = block.get("name", "unknown")
                    inp = block.get("input", {})
                    detail = _tool_detail(name, inp)
                    messages.append({
                        "role": "tool",
                        "text": f"{name}: {detail}" if detail else name,
                        "timestamp": timestamp,
                    })
                # Skip thinking blocks and other types

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
    """Format messages into condensed transcript."""
    lines = []
    current_date = None
    for msg in messages:
        role = msg["role"]
        text = msg["text"]

        ts = msg.get("timestamp", "")
        ts_prefix = ""
        if ts and "T" in ts:
            date_part = ts.split("T")[0]  # YYYY-MM-DD
            if date_part != current_date:
                current_date = date_part
                lines.append(f"--- {date_part} ---")
                lines.append("")
            ts_prefix = ts.split("T")[1][:5] + " "  # HH:MM

        if role == "tool":
            lines.append(f"[Tool] {text}")
        elif role == "user":
            if len(text) > 1000:
                text = text[:1000] + "\n... (truncated)"
            lines.append(f"{ts_prefix}[User] {text}")
        elif role == "assistant":
            if len(text) > 2000:
                text = text[:2000] + "\n... (truncated)"
            lines.append(f"{ts_prefix}[Assistant] {text}")

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


def search_sessions(project_path: str = None, keyword: str = None,
                     branch: str = None, file_path: str = None,
                     date_from: str = None, date_to: str = None,
                     commit: str = None) -> list[dict]:
    """Search across all sessions matching any combination of filters.

    Returns a list of matches with session info and match reasons.
    """
    sessions = find_session_files(project_path)
    results = []

    for session in sessions:
        path = session["path"]
        try:
            entries = parse_jsonl(path)
        except Exception:
            continue

        meta = get_session_metadata(entries)
        reasons = []

        # Date range filter
        if date_from or date_to:
            ts = meta.get("first_timestamp", "")
            if not ts:
                continue
            session_date = ts.split("T")[0]
            if date_from and session_date < date_from:
                continue
            if date_to and session_date > date_to:
                continue
            reasons.append(f"date: {session_date}")

        # Branch filter
        if branch:
            session_branch = meta.get("git_branch", "")
            if branch.lower() not in session_branch.lower():
                continue
            reasons.append(f"branch: {session_branch}")

        # File filter
        if file_path:
            files = extract_modified_files(entries)
            matching = [f for f in files if file_path.lower() in f.lower()]
            if not matching:
                continue
            reasons.append(f"files: {', '.join(matching[:3])}")

        # Commit filter (check tool calls for git commits containing the SHA)
        if commit:
            found = False
            for entry in entries:
                raw = json.dumps(entry)
                if commit in raw:
                    found = True
                    break
            if not found:
                continue
            reasons.append(f"commit: {commit}")

        # Keyword search (across user prompts and assistant text)
        if keyword:
            messages = extract_messages(entries)
            keyword_lower = keyword.lower()
            matching_msgs = []
            for msg in messages:
                if msg["role"] in ("user", "assistant") and keyword_lower in msg["text"].lower():
                    # Grab context around the match
                    text = msg["text"]
                    idx = text.lower().find(keyword_lower)
                    start = max(0, idx - 40)
                    end = min(len(text), idx + len(keyword) + 40)
                    snippet = text[start:end].replace("\n", " ").strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(text):
                        snippet = snippet + "..."
                    matching_msgs.append({
                        "role": msg["role"],
                        "snippet": snippet,
                    })
            if not matching_msgs:
                continue
            reasons.append(f"keyword: {len(matching_msgs)} matches")

        # If no filters were specified, include everything
        if not any([keyword, branch, file_path, date_from, date_to, commit]):
            reasons.append("all")

        if reasons or not any([keyword, branch, file_path, date_from, date_to, commit]):
            # Get first user prompt as context
            messages = extract_messages(entries)
            user_msgs = [m for m in messages if m["role"] == "user"]
            first_prompt = user_msgs[0]["text"][:100] if user_msgs else ""

            tokens = calculate_token_usage(entries)

            results.append({
                "session_id": session["session_id"],
                "path": path,
                "branch": meta.get("git_branch", ""),
                "slug": meta.get("slug", ""),
                "first_timestamp": meta.get("first_timestamp", ""),
                "last_timestamp": meta.get("last_timestamp", ""),
                "first_prompt": first_prompt,
                "total_tokens": tokens.get("total_tokens", 0),
                "modified": str(session["modified"]),
                "match_reasons": reasons,
                "keyword_matches": matching_msgs if keyword and matching_msgs else [],
            })

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse Claude Code session JSONL")
    parser.add_argument("command", choices=["list", "stats", "transcript", "files", "snapshots", "search", "status"])
    parser.add_argument("--session", "-s", help="Session JSONL file path")
    parser.add_argument("--project", "-p", help="Project path filter")
    parser.add_argument("--max-lines", "-n", type=int, help="Max transcript lines")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    # Search filters
    parser.add_argument("--keyword", "-k", help="Search keyword in prompts/responses")
    parser.add_argument("--branch", "-b", help="Filter by git branch")
    parser.add_argument("--file", "-f", help="Filter by modified file path")
    parser.add_argument("--date-from", help="Filter sessions from date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="Filter sessions to date (YYYY-MM-DD)")
    parser.add_argument("--commit", help="Filter by commit SHA")
    args = parser.parse_args()

    if args.command == "search":
        results = search_sessions(
            project_path=args.project,
            keyword=args.keyword,
            branch=args.branch,
            file_path=args.file,
            date_from=args.date_from,
            date_to=args.date_to,
            commit=args.commit,
        )
        if args.json:
            print(json.dumps(results, default=str, indent=2))
        else:
            if not results:
                print("No matching sessions found.")
            else:
                print(f"Found {len(results)} matching session(s):\n")
                for r in results:
                    sid = r["session_id"][:12]
                    branch = r["branch"] or "unknown"
                    ts = r["first_timestamp"].split("T")[0] if r["first_timestamp"] else "?"
                    tokens = r["total_tokens"]
                    prompt = r["first_prompt"].replace("\n", " ")[:80]
                    reasons = " · ".join(r["match_reasons"])

                    print(f"  {sid}...  {ts}  {branch}")
                    print(f"  > \"{prompt}\"")
                    print(f"  {reasons}  ·  {tokens:,} tokens")

                    # Show keyword match snippets
                    for match in r.get("keyword_matches", [])[:3]:
                        role = match["role"][:4]
                        print(f"    [{role}] {match['snippet']}")

                    print()
        sys.exit(0)

    if args.command == "status":
        sessions = find_session_files(args.project)
        if not sessions:
            print("No sessions found.")
            sys.exit(0)

        results = []
        for s in sessions[:5]:
            try:
                data = session_summary_data(s["path"])
                meta = data["metadata"]
                tokens = data["token_usage"]
                user_msgs = [m for m in data["messages"] if m["role"] == "user"]
                first_prompt = ""
                for um in user_msgs:
                    text = um["text"].strip()
                    if text and not text.startswith("<"):
                        first_prompt = text[:80].replace("\n", " ")
                        break
                if not first_prompt and user_msgs:
                    first_prompt = _strip_injected_tags(user_msgs[0]["text"])[:80].replace("\n", " ")
                results.append({
                    "session_id": s["session_id"],
                    "slug": meta.get("slug", ""),
                    "branch": meta.get("git_branch", ""),
                    "model": ", ".join(meta.get("models", [])),
                    "first_timestamp": meta.get("first_timestamp", ""),
                    "last_timestamp": meta.get("last_timestamp", ""),
                    "total_tokens": tokens.get("total_tokens", 0),
                    "first_prompt": first_prompt,
                    "files_modified": len(data.get("modified_files", [])),
                })
            except Exception:
                continue

        if args.json:
            print(json.dumps(results, default=str, indent=2))
        else:
            for r in results:
                ts = r["first_timestamp"]
                date_str = ts.split("T")[0] if ts and "T" in ts else "?"
                tokens_k = r["total_tokens"] / 1000
                print(f"{r['model']} · {r['session_id'][:8]}")
                print(f"> \"{r['first_prompt']}\"")
                print(f"{r['branch']} · {date_str} · {tokens_k:.1f}k tokens · {r['files_modified']} files")
                print()
            if results:
                print(f"To resume: claude --resume {results[0]['session_id']}")
        sys.exit(0)

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

    # Resolve session ID to file path if not already a path
    if not os.path.exists(args.session):
        # Could be a session ID — search for the file
        import glob
        matches = glob.glob(f"{CLAUDE_PROJECTS_DIR}/*/{args.session}*.jsonl")
        if matches:
            args.session = matches[0]
        else:
            print(f"Error: session not found: {args.session}", file=sys.stderr)
            print(f"Searched in: {CLAUDE_PROJECTS_DIR}/*/", file=sys.stderr)
            sys.exit(1)

    if args.command == "stats":
        data = session_summary_data(args.session)
        if args.json:
            data.pop("messages", None)
            data["snapshots_count"] = len(data.get("snapshots", []))
            print(json.dumps(data, default=str, indent=2))
        else:
            meta = data["metadata"]
            tokens = data["token_usage"]
            counts = data["message_counts"]
            snapshots = data.get("snapshots", [])

            # Calculate duration
            duration_str = ""
            if meta["first_timestamp"] and meta["last_timestamp"]:
                try:
                    t1 = datetime.fromisoformat(meta["first_timestamp"].replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(meta["last_timestamp"].replace("Z", "+00:00"))
                    mins = int((t2 - t1).total_seconds() / 60)
                    duration_str = f" ({mins} min)" if mins < 60 else f" ({mins // 60}h {mins % 60}m)"
                except Exception:
                    pass

            # Estimate cost
            models = meta.get("models", [])
            is_opus = any("opus" in m for m in models)
            input_rate = 15 if is_opus else 3  # $/M tokens
            output_rate = 75 if is_opus else 15
            input_cost = (tokens["input_tokens"] + tokens["cache_creation_input_tokens"]) * input_rate / 1_000_000
            output_cost = tokens["output_tokens"] * output_rate / 1_000_000
            cache_read_cost = tokens["cache_read_input_tokens"] * (input_rate * 0.1) / 1_000_000
            total_cost = input_cost + output_cost + cache_read_cost

            print(f"Session:    {meta['session_id']}")
            print(f"Slug:       {meta['slug']}")
            print(f"Branch:     {meta['git_branch']}")
            print(f"CWD:        {meta['cwd']}")
            print(f"Models:     {', '.join(models)}")
            print(f"Duration:   {meta['first_timestamp']} → {meta['last_timestamp']}{duration_str}")
            print(f"Messages:   {counts['user']} user, {counts['assistant']} assistant")
            print(f"Tokens:     {tokens['total_tokens']:,} total ({tokens['input_tokens']:,} in, {tokens['output_tokens']:,} out)")
            print(f"Cache:      {tokens['cache_read_input_tokens']:,} read, {tokens['cache_creation_input_tokens']:,} created")
            print(f"Est. cost:  ${total_cost:.2f} (${input_cost:.2f} in + ${output_cost:.2f} out + ${cache_read_cost:.2f} cache)")
            print(f"Files:      {len(data['modified_files'])} modified")
            for f in data["modified_files"]:
                print(f"            {f}")
            print(f"Snapshots:  {len(snapshots)}")

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
