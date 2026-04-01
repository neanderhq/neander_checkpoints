#!/usr/bin/env python3
"""
Core JSONL transcript parser for Claude Code sessions.

Provides functions to parse, filter, and extract structured data
from Claude Code session JSONL files.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
CHECKPOINT_BRANCH = "neander/checkpoints/v1"


# --- Data Models ---

@dataclass
class SessionFile:
    path: str
    session_id: str
    project_dir: str
    size_bytes: int
    modified: datetime


@dataclass
class Message:
    role: str  # "user", "assistant", "tool"
    text: str
    timestamp: str = ""


@dataclass
class ToolCall:
    name: str
    id: str
    input: dict
    timestamp: str = ""
    uuid: str = ""


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    total_tokens: int = 0


@dataclass
class SessionMetadata:
    session_id: str = ""
    slug: str = ""
    git_branch: str = ""
    cwd: str = ""
    first_timestamp: str = ""
    last_timestamp: str = ""
    models: list[str] = field(default_factory=list)


@dataclass
class FileSnapshot:
    message_id: str
    timestamp: str
    files: list[str]
    backups: dict


@dataclass
class MessageCounts:
    user: int = 0
    assistant: int = 0
    total: int = 0


@dataclass
class CheckpointData:
    metadata: SessionMetadata
    token_usage: TokenUsage
    modified_files: list[str]
    snapshots: list[FileSnapshot]
    message_counts: MessageCounts
    first_prompt: str
    messages: list[Message]


# Keep SessionData as alias for backward compatibility
SessionData = CheckpointData


@dataclass
class KeywordMatch:
    role: str
    snippet: str


@dataclass
class SearchResult:
    session_id: str
    path: str
    branch: str
    slug: str
    first_timestamp: str
    last_timestamp: str
    first_prompt: str
    total_tokens: int
    modified: str
    match_reasons: list[str]
    keyword_matches: list[KeywordMatch] = field(default_factory=list)
    checkpoint_id: str = ""


@dataclass
class CheckpointInfo:
    checkpoint_id: str
    session_id: str
    commit_sha: str
    timestamp: str
    has_summary: bool = False
    intent: str = ""
    merged_files: list[str] = field(default_factory=list)
    transcript_git_path: str = ""


# --- Helpers ---

def _encode_project_path(path: str) -> str:
    """Encode a filesystem path the same way Claude Code does for project dir names."""
    return path.replace("/", "-").replace("_", "-")


def _strip_injected_tags(text: str) -> str:
    """Strip IDE-injected and system tags from text."""
    text = re.sub(r"<[a-z_-]+>.*?</[a-z_-]+>", "", text, flags=re.DOTALL)
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


# --- Core Functions ---

def find_session_files(project_path: str = None) -> list[SessionFile]:
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
            sessions.append(SessionFile(
                path=str(f),
                session_id=f.stem,
                project_dir=project_dir.name,
                size_bytes=f.stat().st_size,
                modified=datetime.fromtimestamp(f.stat().st_mtime),
            ))
    sessions.sort(key=lambda s: s.modified, reverse=True)
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


def parse_jsonl_from_git(git_path: str, offset: int = 0) -> list[dict]:
    """Parse a JSONL file from the checkpoint branch via git show.

    Same parsing logic as parse_jsonl() but reads from git instead of filesystem.
    offset: skip first N lines (for scoped transcript reading).
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{CHECKPOINT_BRANCH}:{git_path}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    lines = []
    for i, line in enumerate(result.stdout.split("\n")):
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


def fetch_remote_checkpoints() -> bool:
    """Fetch the checkpoint branch from remote. Returns True if successful."""
    try:
        result = subprocess.run(
            ["git", "fetch", "origin", CHECKPOINT_BRANCH, "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def extract_messages(entries: list[dict]) -> list[Message]:
    """Extract user/assistant/tool entries in order for condensed transcript."""
    messages = []
    for entry in entries:
        t = entry.get("type")
        if t not in ("user", "assistant"):
            continue
        msg = entry.get("message", {})
        content = msg.get("content", "")
        timestamp = entry.get("timestamp", "")

        if t == "user":
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
            if text.startswith("Base directory for this skill:"):
                continue
            if not text:
                continue

            messages.append(Message(role="user", text=text, timestamp=timestamp))

        elif t == "assistant":
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = _strip_injected_tags(block.get("text", ""))
                    if text:
                        messages.append(Message(role="assistant", text=text, timestamp=timestamp))
                elif block.get("type") == "tool_use":
                    name = block.get("name", "unknown")
                    inp = block.get("input", {})
                    detail = _tool_detail(name, inp)
                    messages.append(Message(
                        role="tool",
                        text=f"{name}: {detail}" if detail else name,
                        timestamp=timestamp,
                    ))

    return messages


def extract_tool_calls(entries: list[dict]) -> list[ToolCall]:
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
                tools.append(ToolCall(
                    name=block.get("name", ""),
                    id=block.get("id", ""),
                    input=block.get("input", {}),
                    timestamp=entry.get("timestamp", ""),
                    uuid=entry.get("uuid", ""),
                ))
    return tools


def extract_modified_files(entries: list[dict]) -> list[str]:
    """Extract file paths modified by Write/Edit/NotebookEdit tools."""
    files = set()
    for tool in extract_tool_calls(entries):
        if tool.name in ("Write", "Edit", "NotebookEdit"):
            path = tool.input.get("file_path", "")
            if path:
                files.add(path)
    return sorted(files)


def calculate_token_usage(entries: list[dict]) -> TokenUsage:
    """Calculate deduplicated token usage across all API calls."""
    seen_ids = set()
    usage = TokenUsage()
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        msg = entry.get("message", {})
        msg_id = msg.get("id")
        if msg_id and msg_id in seen_ids:
            continue
        if msg_id:
            seen_ids.add(msg_id)
        u = msg.get("usage", {})
        usage.input_tokens += u.get("input_tokens", 0)
        usage.output_tokens += u.get("output_tokens", 0)
        usage.cache_creation_input_tokens += u.get("cache_creation_input_tokens", 0)
        usage.cache_read_input_tokens += u.get("cache_read_input_tokens", 0)
    usage.total_tokens = usage.input_tokens + usage.output_tokens
    return usage


def get_session_metadata(entries: list[dict]) -> SessionMetadata:
    """Extract session-level metadata."""
    meta = SessionMetadata()
    models = set()

    for entry in entries:
        ts = entry.get("timestamp")
        if ts:
            if not meta.first_timestamp:
                meta.first_timestamp = ts
            meta.last_timestamp = ts
        if not meta.git_branch:
            meta.git_branch = entry.get("gitBranch", "")
        if not meta.cwd:
            meta.cwd = entry.get("cwd", "")
        if not meta.session_id:
            meta.session_id = entry.get("sessionId", "")
        if not meta.slug:
            meta.slug = entry.get("slug", "")
        model = entry.get("message", {}).get("model")
        if model:
            models.add(model)

    meta.models = sorted(models)
    return meta


def get_file_snapshots(entries: list[dict]) -> list[FileSnapshot]:
    """Extract file-history-snapshot entries for rewind support."""
    snapshots = []
    for entry in entries:
        if entry.get("type") != "file-history-snapshot":
            continue
        snapshot = entry.get("snapshot", {})
        snapshots.append(FileSnapshot(
            message_id=entry.get("messageId", ""),
            timestamp=snapshot.get("timestamp", ""),
            files=list(snapshot.get("trackedFileBackups", {}).keys()),
            backups=snapshot.get("trackedFileBackups", {}),
        ))
    return snapshots


def format_condensed_transcript(messages: list[Message], max_lines: int = None) -> str:
    """Format messages into condensed transcript."""
    lines = []
    current_date = None
    for msg in messages:
        ts = msg.timestamp
        ts_prefix = ""
        if ts and "T" in ts:
            date_part = ts.split("T")[0]
            if date_part != current_date:
                current_date = date_part
                lines.append(f"--- {date_part} ---")
                lines.append("")
            ts_prefix = ts.split("T")[1][:5] + " "

        if msg.role == "tool":
            lines.append(f"[Tool] {msg.text}")
        elif msg.role == "user":
            text = msg.text[:1000] + "\n... (truncated)" if len(msg.text) > 1000 else msg.text
            lines.append(f"{ts_prefix}[User] {text}")
        elif msg.role == "assistant":
            text = msg.text[:2000] + "\n... (truncated)" if len(msg.text) > 2000 else msg.text
            lines.append(f"{ts_prefix}[Assistant] {text}")

        lines.append("")

    output = "\n".join(lines)
    if max_lines:
        output = "\n".join(output.split("\n")[:max_lines])
    return output


def _build_entries_summary(entries: list[dict]) -> CheckpointData:
    """Build CheckpointData from parsed JSONL entries."""
    messages = extract_messages(entries)
    tokens = calculate_token_usage(entries)
    meta = get_session_metadata(entries)
    files = extract_modified_files(entries)
    snapshots = get_file_snapshots(entries)

    user_msgs = [m for m in messages if m.role == "user"]
    assistant_msgs = [m for m in messages if m.role == "assistant"]

    return CheckpointData(
        metadata=meta,
        token_usage=tokens,
        modified_files=files,
        snapshots=snapshots,
        message_counts=MessageCounts(
            user=len(user_msgs),
            assistant=len(assistant_msgs),
            total=len(messages),
        ),
        first_prompt=user_msgs[0].text[:500] if user_msgs else "",
        messages=messages,
    )


def session_summary_data(filepath: str) -> CheckpointData:
    """Get all structured data for a session. Thin wrapper around get_checkpoint_data for file paths."""
    entries = parse_jsonl(filepath)
    return _build_entries_summary(entries)


def get_all_checkpoints() -> list[CheckpointInfo]:
    """Read all checkpoints from the checkpoint branch. Returns list sorted newest first.

    Reads index.log once, then batch-reads metadata for each unique checkpoint.
    Also does one git ls-tree call to populate transcript_git_path.
    """
    checkpoints = []
    try:
        result = subprocess.run(
            ["git", "show", f"{CHECKPOINT_BRANCH}:index.log"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []

        # Parse index
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 4:
                continue
            checkpoints.append(CheckpointInfo(
                checkpoint_id=parts[0],
                session_id=parts[1],
                commit_sha=parts[2],
                timestamp=parts[3],
            ))

        # Build transcript path map from git ls-tree
        transcript_map = {}  # shard_prefix -> transcript path
        try:
            tree_result = subprocess.run(
                ["git", "ls-tree", "-r", CHECKPOINT_BRANCH, "--name-only"],
                capture_output=True, text=True, timeout=5,
            )
            if tree_result.returncode == 0:
                for fpath in tree_result.stdout.strip().split("\n"):
                    if "/transcript-" in fpath and fpath.endswith(".jsonl"):
                        # e.g. "06/f5256d51c2d78b/transcript-sid.jsonl"
                        parts_path = fpath.split("/")
                        if len(parts_path) >= 3:
                            shard_prefix = f"{parts_path[0]}/{parts_path[1]}"
                            transcript_map[shard_prefix] = fpath
        except Exception:
            pass

        # Read metadata for each checkpoint and populate transcript_git_path
        for cp in checkpoints:
            shard = f"{cp.checkpoint_id[:2]}/{cp.checkpoint_id[2:]}"

            # Set transcript path from ls-tree map
            if shard in transcript_map:
                cp.transcript_git_path = transcript_map[shard]

            try:
                result = subprocess.run(
                    ["git", "show", f"{CHECKPOINT_BRANCH}:{shard}/metadata.json"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    metadata = json.loads(result.stdout)
                    cp.merged_files = metadata.get("merged_files", [])
                    summary = metadata.get("summary")
                    if summary and isinstance(summary, dict):
                        cp.has_summary = True
                        cp.intent = summary.get("intent", "")
            except Exception:
                pass

    except Exception:
        pass

    # Newest first
    checkpoints.reverse()
    return checkpoints


def resolve_id(id_str: str) -> tuple[str, str]:
    """Universal ID resolver. Takes any identifier and returns (source_type, source_path).

    Resolution order:
    1. Existing file path -> ("file", path)
    2. Checkpoint ID (hex) -> look up in get_all_checkpoints() -> ("git", transcript_git_path)
    3. Session ID (UUID) -> find latest checkpoint for that session -> ("git", transcript_git_path)
    4. Partial match -> try checkpoint IDs first, then session IDs
    5. Fallback -> search ~/.claude/projects/ for local file -> ("file", path)
    """
    # 1. File path
    if os.path.exists(id_str):
        return ("file", id_str)

    # 2-4. Look up in checkpoints
    checkpoints = get_all_checkpoints()

    # 2. Exact checkpoint ID match
    for cp in checkpoints:
        if cp.checkpoint_id == id_str and cp.transcript_git_path:
            return ("git", cp.transcript_git_path)

    # 3. Exact session ID match -> find latest checkpoint (checkpoints are newest-first)
    for cp in checkpoints:
        if cp.session_id == id_str and cp.transcript_git_path:
            return ("git", cp.transcript_git_path)

    # 4. Partial match - checkpoint IDs first
    for cp in checkpoints:
        if cp.checkpoint_id.startswith(id_str) and cp.transcript_git_path:
            return ("git", cp.transcript_git_path)

    # 4b. Partial match - session IDs
    for cp in checkpoints:
        if cp.session_id.startswith(id_str) and cp.transcript_git_path:
            return ("git", cp.transcript_git_path)

    # 5. Fallback to local files
    import glob as glob_module
    matches = glob_module.glob(f"{CLAUDE_PROJECTS_DIR}/*/{id_str}*.jsonl")
    if matches:
        return ("file", matches[0])

    return ("file", "")


def get_checkpoint_data(id_str: str) -> CheckpointData:
    """Get structured data for a checkpoint or session by ID.

    Uses resolve_id() to find the source, then reads and processes the transcript.
    """
    source_type, source_path = resolve_id(id_str)
    if not source_path:
        return _build_entries_summary([])

    if source_type == "git":
        entries = parse_jsonl_from_git(source_path)
    else:
        entries = parse_jsonl(source_path)

    return _build_entries_summary(entries)


def search_checkpoints(keyword: str = None, branch: str = None,
                       file_path: str = None, date_from: str = None,
                       date_to: str = None, commit: str = None,
                       project_path: str = None) -> list[SearchResult]:
    """Search across all checkpoints matching any combination of filters.

    Reads from the checkpoint branch. Deduplicates per session (only searches
    the latest checkpoint per session to avoid duplicate results).
    Also searches current uncheckpointed session from local file.
    """
    results = []
    checkpoints = get_all_checkpoints()

    # Deduplicate: only keep the latest checkpoint per session
    # checkpoints are newest-first, so first occurrence wins
    seen_sessions = set()
    unique_checkpoints = []
    for cp in checkpoints:
        if cp.session_id not in seen_sessions:
            seen_sessions.add(cp.session_id)
            unique_checkpoints.append(cp)

    # Search each unique checkpoint
    for cp in unique_checkpoints:
        if not cp.transcript_git_path:
            continue

        try:
            entries = parse_jsonl_from_git(cp.transcript_git_path)
        except Exception:
            continue

        if not entries:
            continue

        meta = get_session_metadata(entries)
        reasons = []

        if date_from or date_to:
            ts = meta.first_timestamp or cp.timestamp
            if not ts:
                continue
            session_date = ts.split("T")[0]
            if date_from and session_date < date_from:
                continue
            if date_to and session_date > date_to:
                continue
            reasons.append(f"date: {session_date}")

        if branch:
            if branch.lower() not in meta.git_branch.lower():
                continue
            reasons.append(f"branch: {meta.git_branch}")

        if file_path:
            files = extract_modified_files(entries)
            matching = [f for f in files if file_path.lower() in f.lower()]
            if not matching:
                continue
            reasons.append(f"files: {', '.join(matching[:3])}")

        if commit:
            found = False
            for entry in entries:
                if commit in json.dumps(entry):
                    found = True
                    break
            if not found:
                continue
            reasons.append(f"commit: {commit}")

        keyword_matches = []
        if keyword:
            messages = extract_messages(entries)
            keyword_lower = keyword.lower()
            for msg in messages:
                if msg.role in ("user", "assistant") and keyword_lower in msg.text.lower():
                    idx = msg.text.lower().find(keyword_lower)
                    start = max(0, idx - 40)
                    end = min(len(msg.text), idx + len(keyword) + 40)
                    snippet = msg.text[start:end].replace("\n", " ").strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(msg.text):
                        snippet = snippet + "..."
                    keyword_matches.append(KeywordMatch(role=msg.role, snippet=snippet))
            if not keyword_matches:
                continue
            reasons.append(f"keyword: {len(keyword_matches)} matches")

        if not any([keyword, branch, file_path, date_from, date_to, commit]):
            reasons.append("all")

        if reasons or not any([keyword, branch, file_path, date_from, date_to, commit]):
            messages = extract_messages(entries)
            user_msgs = [m for m in messages if m.role == "user"]
            first_prompt = user_msgs[0].text[:100] if user_msgs else ""
            tokens = calculate_token_usage(entries)

            results.append(SearchResult(
                session_id=cp.session_id,
                path=cp.transcript_git_path,
                branch=meta.git_branch,
                slug=meta.slug,
                first_timestamp=meta.first_timestamp,
                last_timestamp=meta.last_timestamp,
                first_prompt=first_prompt,
                total_tokens=tokens.total_tokens,
                modified=cp.timestamp,
                match_reasons=reasons,
                keyword_matches=keyword_matches,
                checkpoint_id=cp.checkpoint_id,
            ))

    # Also search current uncheckpointed session from local files
    try:
        sessions = find_session_files(project_path)
        checkpointed_session_ids = {cp.session_id for cp in checkpoints}
        for session in sessions:
            if session.session_id in checkpointed_session_ids:
                continue
            # Already have a result for this session from checkpoints
            if session.session_id in {r.session_id for r in results}:
                continue

            try:
                entries = parse_jsonl(session.path)
            except Exception:
                continue

            meta = get_session_metadata(entries)
            reasons = []

            if date_from or date_to:
                ts = meta.first_timestamp
                if not ts:
                    continue
                session_date = ts.split("T")[0]
                if date_from and session_date < date_from:
                    continue
                if date_to and session_date > date_to:
                    continue
                reasons.append(f"date: {session_date}")

            if branch:
                if branch.lower() not in meta.git_branch.lower():
                    continue
                reasons.append(f"branch: {meta.git_branch}")

            if file_path:
                files = extract_modified_files(entries)
                matching = [f for f in files if file_path.lower() in f.lower()]
                if not matching:
                    continue
                reasons.append(f"files: {', '.join(matching[:3])}")

            if commit:
                found = False
                for entry in entries:
                    if commit in json.dumps(entry):
                        found = True
                        break
                if not found:
                    continue
                reasons.append(f"commit: {commit}")

            keyword_matches = []
            if keyword:
                messages = extract_messages(entries)
                # Split into words — all must match somewhere in the transcript
                words = keyword.lower().split()
                all_text = " ".join(m.text.lower() for m in messages if m.role in ("user", "assistant"))
                if not all(w in all_text for w in words):
                    continue

                # Find snippet matches for the most distinctive word (longest)
                best_word = max(words, key=len)
                for msg in messages:
                    if msg.role in ("user", "assistant") and best_word in msg.text.lower():
                        idx = msg.text.lower().find(best_word)
                        start = max(0, idx - 40)
                        end = min(len(msg.text), idx + len(best_word) + 40)
                        snippet = msg.text[start:end].replace("\n", " ").strip()
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(msg.text):
                            snippet = snippet + "..."
                        keyword_matches.append(KeywordMatch(role=msg.role, snippet=snippet))
                if not keyword_matches:
                    continue
                reasons.append(f"keyword: {len(keyword_matches)} matches")

            if not any([keyword, branch, file_path, date_from, date_to, commit]):
                reasons.append("all")

            if reasons or not any([keyword, branch, file_path, date_from, date_to, commit]):
                messages = extract_messages(entries)
                user_msgs = [m for m in messages if m.role == "user"]
                first_prompt = user_msgs[0].text[:100] if user_msgs else ""
                tokens = calculate_token_usage(entries)

                results.append(SearchResult(
                    session_id=session.session_id,
                    path=session.path,
                    branch=meta.git_branch,
                    slug=meta.slug,
                    first_timestamp=meta.first_timestamp,
                    last_timestamp=meta.last_timestamp,
                    first_prompt=first_prompt,
                    total_tokens=tokens.total_tokens,
                    modified=str(session.modified),
                    match_reasons=reasons,
                    keyword_matches=keyword_matches,
                    checkpoint_id="",
                ))
    except Exception:
        pass

    return results


# Keep search_sessions as alias for backward compatibility
search_sessions = search_checkpoints


if __name__ == "__main__":
    import argparse
    import glob as glob_module

    parser = argparse.ArgumentParser(description="Parse Claude Code session JSONL")
    parser.add_argument("command", choices=["list", "stats", "transcript", "files", "snapshots", "search", "status"])
    parser.add_argument("--checkpoint", "-c", dest="checkpoint", help="Checkpoint ID, session ID, or file path")
    parser.add_argument("--session", "-s", dest="session", help="Alias for --checkpoint (backward compat)")
    parser.add_argument("--project", "-p", help="Project path filter")
    parser.add_argument("--max-lines", "-n", type=int, help="Max transcript lines")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--keyword", "-k", help="Search keyword in prompts/responses")
    parser.add_argument("--branch", "-b", help="Filter by git branch")
    parser.add_argument("--file", "-f", help="Filter by modified file path")
    parser.add_argument("--date-from", help="Filter sessions from date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="Filter sessions to date (YYYY-MM-DD)")
    parser.add_argument("--commit", help="Filter by commit SHA")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Max sessions to show (default 10)")
    parser.add_argument("--fetch", action="store_true", help="Fetch remote checkpoints before running command")
    parser.add_argument("--offset", type=int, default=0, help="Transcript line offset (skip first N lines of JSONL)")
    args = parser.parse_args()

    # --session is alias for --checkpoint
    id_arg = args.checkpoint or args.session

    # Fetch remote if requested
    if args.fetch:
        fetch_remote_checkpoints()

    if args.command == "search":
        results = search_checkpoints(
            project_path=args.project,
            keyword=args.keyword,
            branch=args.branch,
            file_path=args.file,
            date_from=args.date_from,
            date_to=args.date_to,
            commit=args.commit,
        )
        if args.json:
            print(json.dumps([asdict(r) for r in results], default=str, indent=2))
        else:
            if not results:
                print("No matching checkpoints found.")
            else:
                print(f"Found {len(results)} result(s):\n")

                rows = []
                for r in results:
                    ts = r.first_timestamp.split("T")[0] if r.first_timestamp else "?"
                    tokens_k = f"{r.total_tokens / 1000:.1f}k"
                    prompt = r.first_prompt.replace("\n", " ")[:40] or ""
                    rows.append((
                        r.checkpoint_id[:12] if r.checkpoint_id else "-",
                        r.session_id[:8],
                        r.branch or "",
                        ts,
                        tokens_k,
                        prompt,
                    ))

                headers = ("Checkpoint", "Session", "Branch", "Date", "Tokens", "Topic")
                widths = [len(h) for h in headers]
                for row in rows:
                    for i, cell in enumerate(row):
                        widths[i] = max(widths[i], len(cell))
                def fmt(cells):
                    return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))
                print(fmt(headers))
                print("  ".join("-" * w for w in widths))
                for row in rows:
                    print(fmt(row))

                # Show keyword snippets below the table if any
                has_snippets = any(r.keyword_matches for r in results)
                if has_snippets:
                    print()
                    print("Keyword matches:")
                    for r in results:
                        if r.keyword_matches:
                            print(f"  {r.session_id[:8]}:")
                            for match in r.keyword_matches[:3]:
                                print(f"    [{match.role[:4]}] {match.snippet}")
        sys.exit(0)

    if args.command == "status":
        checkpoints = get_all_checkpoints()

        if not checkpoints:
            print("No checkpoints found.")
            print("Checkpoints are created automatically on git commits and session stops.")
            sys.exit(0)

        if args.json:
            print(json.dumps([asdict(cp) for cp in checkpoints[:args.limit]], default=str, indent=2))
            sys.exit(0)

        # --- Helper for table formatting ---
        def print_table(headers, rows):
            if not rows:
                return
            widths = [len(h) for h in headers]
            for row in rows:
                for i, cell in enumerate(row):
                    widths[i] = max(widths[i], len(cell))
            def fmt(cells):
                return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))
            print(fmt(headers))
            print("  ".join("-" * w for w in widths))
            for row in rows:
                print(fmt(row))

        # --- Current session ---
        sessions = find_session_files(args.project)
        if sessions:
            s = sessions[0]
            checkpointed_sessions = {cp.session_id for cp in checkpoints}
            if s.session_id not in checkpointed_sessions:
                try:
                    data = session_summary_data(s.path)
                    user_msgs = [m for m in data.messages if m.role == "user"]
                    topic = ""
                    for um in user_msgs:
                        text = um.text.strip()
                        if text and not text.startswith("<"):
                            topic = text[:60].replace("\n", " ")
                            break
                    if not topic and user_msgs:
                        topic = _strip_injected_tags(user_msgs[0].text)[:60].replace("\n", " ")
                    model = ", ".join(data.metadata.models).replace("claude-", "").replace("-4-6", "")
                    tokens_k = f"{data.token_usage.total_tokens / 1000:.1f}k"
                    branch = data.metadata.git_branch or ""
                    files = len(data.modified_files)
                    print(f"Current: {s.session_id[:8]} · {model} · {branch} · {tokens_k} tokens · {files} files")
                    if topic:
                        print(f"         {topic}")
                    print(f"         (not yet checkpointed)\n")
                except Exception:
                    pass

        # --- Checkpoints ---
        if checkpoints:
            print(f"== Checkpoints ({len(checkpoints)} total) ==\n")
            cp_rows = []
            for cp in checkpoints[:args.limit]:
                date_str = cp.timestamp.split("T")[0] if "T" in cp.timestamp else "?"
                time_str = cp.timestamp.split("T")[1][:5] if "T" in cp.timestamp else ""
                topic = cp.intent[:45] if cp.intent else ""
                files = str(len(cp.merged_files)) if cp.merged_files else "-"
                cp_rows.append((
                    cp.checkpoint_id[:12],
                    cp.commit_sha[:8],
                    cp.session_id[:8],
                    f"{date_str} {time_str}",
                    files,
                    topic,
                ))

            print_table(
                ("Checkpoint", "Commit", "Session", "Date", "Files", "Topic"),
                cp_rows,
            )

        # --- Footer ---
        print()
        latest_cp = checkpoints[0]
        print(f"Resume:     /neander-resume {latest_cp.checkpoint_id[:12]}")
        print("Summarize:  /neander-summarize <checkpoint_id>")
        print("Transcript: /neander-transcript <checkpoint_id>")

        sys.exit(0)

    if args.command == "list":
        sessions = find_session_files(args.project)
        if args.json:
            print(json.dumps([asdict(s) for s in sessions], default=str, indent=2))
        else:
            for s in sessions[:args.limit]:
                size_kb = s.size_bytes / 1024
                print(f"  {s.session_id[:12]}...  {s.modified:%Y-%m-%d %H:%M}  {size_kb:>8.1f}KB  {s.project_dir}")
        sys.exit(0)

    if not id_arg:
        print("Error: --checkpoint (or --session) required for this command", file=sys.stderr)
        sys.exit(1)

    # Use resolve_id + get_checkpoint_data for all remaining commands
    source_type, source_path = resolve_id(id_arg)

    if not source_path:
        print(f"Error: checkpoint/session not found: {id_arg}", file=sys.stderr)
        sys.exit(1)

    if args.command == "stats":
        data = get_checkpoint_data(id_arg)
        if args.json:
            d = asdict(data)
            d.pop("messages", None)
            d["snapshots_count"] = len(data.snapshots)
            print(json.dumps(d, default=str, indent=2))
        else:
            meta = data.metadata
            tokens = data.token_usage
            counts = data.message_counts

            duration_str = ""
            if meta.first_timestamp and meta.last_timestamp:
                try:
                    t1 = datetime.fromisoformat(meta.first_timestamp.replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(meta.last_timestamp.replace("Z", "+00:00"))
                    mins = int((t2 - t1).total_seconds() / 60)
                    duration_str = f" ({mins} min)" if mins < 60 else f" ({mins // 60}h {mins % 60}m)"
                except Exception:
                    pass

            models = meta.models
            is_opus = any("opus" in m for m in models)
            input_rate = 15 if is_opus else 3
            output_rate = 75 if is_opus else 15
            input_cost = (tokens.input_tokens + tokens.cache_creation_input_tokens) * input_rate / 1_000_000
            output_cost = tokens.output_tokens * output_rate / 1_000_000
            cache_read_cost = tokens.cache_read_input_tokens * (input_rate * 0.1) / 1_000_000
            total_cost = input_cost + output_cost + cache_read_cost

            print(f"Session:    {meta.session_id}")
            print(f"Slug:       {meta.slug}")
            print(f"Branch:     {meta.git_branch}")
            print(f"CWD:        {meta.cwd}")
            print(f"Models:     {', '.join(models)}")
            print(f"Duration:   {meta.first_timestamp} → {meta.last_timestamp}{duration_str}")
            print(f"Messages:   {counts.user} user, {counts.assistant} assistant")
            print(f"Tokens:     {tokens.total_tokens:,} total ({tokens.input_tokens:,} in, {tokens.output_tokens:,} out)")
            print(f"Cache:      {tokens.cache_read_input_tokens:,} read, {tokens.cache_creation_input_tokens:,} created")
            print(f"Est. cost:  ${total_cost:.2f} (${input_cost:.2f} in + ${output_cost:.2f} out + ${cache_read_cost:.2f} cache)")
            print(f"Files:      {len(data.modified_files)} modified")
            for f in data.modified_files:
                print(f"            {f}")
            print(f"Snapshots:  {len(data.snapshots)}")

    elif args.command == "transcript":
        if args.offset > 0:
            # Scoped transcript: read only from offset
            if source_type == "git":
                entries = parse_jsonl_from_git(source_path, offset=args.offset)
            else:
                entries = parse_jsonl(source_path, offset=args.offset)
            messages = extract_messages(entries)
            print(format_condensed_transcript(messages, args.max_lines))
        else:
            data = get_checkpoint_data(id_arg)
            print(format_condensed_transcript(data.messages, args.max_lines))

    elif args.command == "files":
        if source_type == "git":
            entries = parse_jsonl_from_git(source_path)
        else:
            entries = parse_jsonl(source_path)
        files = extract_modified_files(entries)
        if args.json:
            print(json.dumps(files, indent=2))
        else:
            for f in files:
                print(f)

    elif args.command == "snapshots":
        if source_type == "git":
            entries = parse_jsonl_from_git(source_path)
        else:
            entries = parse_jsonl(source_path)
        snapshots = get_file_snapshots(entries)
        if args.json:
            print(json.dumps([asdict(s) for s in snapshots], default=str, indent=2))
        else:
            for i, snap in enumerate(snapshots):
                print(f"Snapshot {i+1}: {snap.timestamp}")
                print(f"  Message: {snap.message_id}")
                print(f"  Files:   {len(snap.files)}")
                for f in snap.files:
                    print(f"           {f}")
                print()
