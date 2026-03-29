#!/usr/bin/env python3
"""Tests for parse_jsonl.py"""

import json
import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

# Add scripts dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from parse_jsonl import (
    Message, SessionFile, SessionMetadata, TokenUsage, FileSnapshot,
    CheckpointData, SessionData, MessageCounts, ToolCall, SearchResult, KeywordMatch,
    CheckpointInfo, CHECKPOINT_BRANCH,
    _encode_project_path, _strip_injected_tags, _tool_detail,
    parse_jsonl, parse_jsonl_from_git, fetch_remote_checkpoints,
    extract_messages, extract_tool_calls,
    extract_modified_files, calculate_token_usage, get_session_metadata,
    get_file_snapshots, format_condensed_transcript, session_summary_data,
    search_checkpoints, search_sessions, resolve_id, get_checkpoint_data,
)


# --- Fixtures ---

def make_user_entry(text, timestamp="2026-03-22T12:21:45.000Z", **kwargs):
    return {
        "type": "user",
        "message": {"role": "user", "content": text},
        "timestamp": timestamp,
        **kwargs,
    }


def make_user_entry_blocks(blocks, timestamp="2026-03-22T12:21:45.000Z", **kwargs):
    return {
        "type": "user",
        "message": {"role": "user", "content": blocks},
        "timestamp": timestamp,
        **kwargs,
    }


def make_assistant_entry(content_blocks, timestamp="2026-03-22T12:22:00.000Z",
                         model="claude-opus-4-6", msg_id="msg_01", **kwargs):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": content_blocks,
            "model": model,
            "id": msg_id,
            "usage": kwargs.pop("usage", {
                "input_tokens": 100,
                "output_tokens": 200,
                "cache_creation_input_tokens": 50,
                "cache_read_input_tokens": 1000,
            }),
        },
        "timestamp": timestamp,
        "sessionId": kwargs.pop("sessionId", "test-session"),
        "gitBranch": kwargs.pop("gitBranch", "main"),
        "cwd": kwargs.pop("cwd", "/test/project"),
        "slug": kwargs.pop("slug", "test-slug"),
        **kwargs,
    }


def make_tool_use_block(name, input_data, tool_id="toolu_01"):
    return {"type": "tool_use", "name": name, "input": input_data, "id": tool_id}


def make_text_block(text):
    return {"type": "text", "text": text}


def make_thinking_block(text):
    return {"type": "thinking", "thinking": text}


def make_snapshot_entry(message_id="msg_01", timestamp="2026-03-22T12:21:45.000Z",
                        backups=None):
    return {
        "type": "file-history-snapshot",
        "messageId": message_id,
        "snapshot": {
            "messageId": message_id,
            "timestamp": timestamp,
            "trackedFileBackups": backups or {},
        },
    }


def write_jsonl(entries):
    """Write entries to a temp JSONL file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for entry in entries:
        f.write(json.dumps(entry) + "\n")
    f.close()
    return f.name


# --- Tests: Helpers ---

class TestEncodeProjectPath:
    def test_slashes_to_dashes(self):
        assert _encode_project_path("/Users/sourab/project") == "-Users-sourab-project"

    def test_underscores_to_dashes(self):
        assert _encode_project_path("/Users/sourab/my_project") == "-Users-sourab-my-project"

    def test_combined(self):
        assert _encode_project_path("/a/b_c/d") == "-a-b-c-d"


class TestStripInjectedTags:
    def test_strips_system_reminder(self):
        text = "hello <system-reminder>secret</system-reminder> world"
        assert _strip_injected_tags(text) == "hello  world"

    def test_strips_ide_tags(self):
        text = "<ide_opened_file>foo.py</ide_opened_file>Fix the bug"
        assert _strip_injected_tags(text) == "Fix the bug"

    def test_strips_command_message(self):
        text = "<command-message>neander-status</command-message>"
        assert _strip_injected_tags(text) == ""

    def test_strips_self_closing(self):
        text = "hello <br/> world"
        assert _strip_injected_tags(text) == "hello  world"

    def test_preserves_normal_text(self):
        assert _strip_injected_tags("normal text") == "normal text"

    def test_empty_string(self):
        assert _strip_injected_tags("") == ""


class TestToolDetail:
    def test_bash_with_description(self):
        assert _tool_detail("Bash", {"description": "Run tests", "command": "npm test"}) == "Run tests"

    def test_bash_without_description(self):
        assert _tool_detail("Bash", {"command": "npm test"}) == "npm test"

    def test_bash_long_command_truncated(self):
        cmd = "x" * 200
        result = _tool_detail("Bash", {"command": cmd})
        assert len(result) == 123  # 120 + "..."
        assert result.endswith("...")

    def test_read(self):
        assert _tool_detail("Read", {"file_path": "/foo/bar.py"}) == "/foo/bar.py"

    def test_grep(self):
        assert _tool_detail("Grep", {"pattern": "foo", "path": "/bar"}) == "foo in /bar"

    def test_grep_no_path(self):
        assert _tool_detail("Grep", {"pattern": "foo"}) == "foo"

    def test_edit(self):
        assert _tool_detail("Edit", {"file_path": "/foo.py"}) == "/foo.py"

    def test_agent(self):
        assert _tool_detail("Agent", {"description": "Explore code"}) == "Explore code"

    def test_unknown_tool(self):
        assert _tool_detail("Unknown", {"foo": "bar"}) == ""


# --- Tests: Core Functions ---

class TestParseJsonl:
    def test_basic(self):
        path = write_jsonl([{"type": "user"}, {"type": "assistant"}])
        try:
            entries = parse_jsonl(path)
            assert len(entries) == 2
            assert entries[0]["type"] == "user"
        finally:
            os.unlink(path)

    def test_with_offset(self):
        path = write_jsonl([{"type": "a"}, {"type": "b"}, {"type": "c"}])
        try:
            entries = parse_jsonl(path, offset=1)
            assert len(entries) == 2
            assert entries[0]["type"] == "b"
        finally:
            os.unlink(path)

    def test_skips_invalid_json(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write('{"valid": true}\n')
        f.write('not json\n')
        f.write('{"also": "valid"}\n')
        f.close()
        try:
            entries = parse_jsonl(f.name)
            assert len(entries) == 2
        finally:
            os.unlink(f.name)

    def test_skips_empty_lines(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write('{"a": 1}\n\n\n{"b": 2}\n')
        f.close()
        try:
            entries = parse_jsonl(f.name)
            assert len(entries) == 2
        finally:
            os.unlink(f.name)


class TestParseJsonlFromGit:
    def test_basic(self):
        """Test parse_jsonl_from_git reads from git show output."""
        jsonl_content = '{"type": "user", "message": {"content": "hello"}}\n{"type": "assistant"}\n'
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = jsonl_content

        with patch("parse_jsonl.subprocess.run", return_value=mock_result) as mock_run:
            entries = parse_jsonl_from_git("06/abc123/transcript-sid.jsonl")
            assert len(entries) == 2
            assert entries[0]["type"] == "user"
            mock_run.assert_called_once_with(
                ["git", "show", f"{CHECKPOINT_BRANCH}:06/abc123/transcript-sid.jsonl"],
                capture_output=True, text=True, timeout=10,
            )

    def test_returns_empty_on_failure(self):
        """Test parse_jsonl_from_git returns empty list on git show failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("parse_jsonl.subprocess.run", return_value=mock_result):
            entries = parse_jsonl_from_git("nonexistent/path.jsonl")
            assert entries == []

    def test_skips_invalid_json_lines(self):
        """Test parse_jsonl_from_git skips invalid JSON like parse_jsonl does."""
        jsonl_content = '{"valid": true}\nnot json\n{"also": "valid"}\n'
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = jsonl_content

        with patch("parse_jsonl.subprocess.run", return_value=mock_result):
            entries = parse_jsonl_from_git("some/path.jsonl")
            assert len(entries) == 2

    def test_returns_empty_on_exception(self):
        """Test parse_jsonl_from_git returns empty list on subprocess exception."""
        with patch("parse_jsonl.subprocess.run", side_effect=Exception("timeout")):
            entries = parse_jsonl_from_git("some/path.jsonl")
            assert entries == []


class TestFetchRemoteCheckpoints:
    def test_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("parse_jsonl.subprocess.run", return_value=mock_result) as mock_run:
            assert fetch_remote_checkpoints() is True
            mock_run.assert_called_once_with(
                ["git", "fetch", "origin", CHECKPOINT_BRANCH, "--quiet"],
                capture_output=True, text=True, timeout=30,
            )

    def test_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("parse_jsonl.subprocess.run", return_value=mock_result):
            assert fetch_remote_checkpoints() is False

    def test_exception(self):
        with patch("parse_jsonl.subprocess.run", side_effect=Exception("network error")):
            assert fetch_remote_checkpoints() is False


class TestExtractMessages:
    def test_user_string_content(self):
        entries = [make_user_entry("hello")]
        msgs = extract_messages(entries)
        assert len(msgs) == 1
        assert msgs[0].role == "user"
        assert msgs[0].text == "hello"

    def test_user_block_content(self):
        entries = [make_user_entry_blocks([
            {"type": "text", "text": "hello"},
            {"type": "tool_result", "content": "ignored"},
        ])]
        msgs = extract_messages(entries)
        assert len(msgs) == 1
        assert msgs[0].text == "hello"

    def test_strips_injected_tags(self):
        entries = [make_user_entry("<system-reminder>x</system-reminder>Fix bug")]
        msgs = extract_messages(entries)
        assert msgs[0].text == "Fix bug"

    def test_skips_skill_injections(self):
        entries = [make_user_entry("Base directory for this skill: /foo")]
        msgs = extract_messages(entries)
        assert len(msgs) == 0

    def test_skips_empty_after_strip(self):
        entries = [make_user_entry("<system-reminder>only tags</system-reminder>")]
        msgs = extract_messages(entries)
        assert len(msgs) == 0

    def test_assistant_text(self):
        entries = [make_assistant_entry([make_text_block("response")])]
        msgs = extract_messages(entries)
        assert len(msgs) == 1
        assert msgs[0].role == "assistant"
        assert msgs[0].text == "response"

    def test_assistant_tool_use(self):
        entries = [make_assistant_entry([
            make_tool_use_block("Read", {"file_path": "/foo.py"}),
        ])]
        msgs = extract_messages(entries)
        assert len(msgs) == 1
        assert msgs[0].role == "tool"
        assert msgs[0].text == "Read: /foo.py"

    def test_assistant_mixed(self):
        entries = [make_assistant_entry([
            make_text_block("Let me read that"),
            make_tool_use_block("Read", {"file_path": "/foo.py"}),
        ])]
        msgs = extract_messages(entries)
        assert len(msgs) == 2
        assert msgs[0].role == "assistant"
        assert msgs[1].role == "tool"

    def test_skips_thinking_blocks(self):
        entries = [make_assistant_entry([
            make_thinking_block("thinking..."),
            make_text_block("visible"),
        ])]
        msgs = extract_messages(entries)
        assert len(msgs) == 1
        assert msgs[0].text == "visible"

    def test_skips_progress_entries(self):
        entries = [{"type": "progress", "data": {}}]
        msgs = extract_messages(entries)
        assert len(msgs) == 0

    def test_preserves_order(self):
        entries = [
            make_user_entry("q1", timestamp="2026-03-22T12:00:00.000Z"),
            make_assistant_entry([make_text_block("a1")], timestamp="2026-03-22T12:01:00.000Z", msg_id="m1"),
            make_user_entry("q2", timestamp="2026-03-22T12:02:00.000Z"),
        ]
        msgs = extract_messages(entries)
        assert [m.role for m in msgs] == ["user", "assistant", "user"]


class TestExtractToolCalls:
    def test_extracts_tool_use(self):
        entries = [make_assistant_entry([
            make_tool_use_block("Edit", {"file_path": "/foo.py"}, "toolu_01"),
        ])]
        tools = extract_tool_calls(entries)
        assert len(tools) == 1
        assert tools[0].name == "Edit"
        assert tools[0].id == "toolu_01"
        assert tools[0].input == {"file_path": "/foo.py"}

    def test_skips_non_assistant(self):
        entries = [make_user_entry("hello")]
        assert extract_tool_calls(entries) == []

    def test_multiple_tools(self):
        entries = [make_assistant_entry([
            make_tool_use_block("Read", {"file_path": "/a.py"}, "t1"),
            make_tool_use_block("Edit", {"file_path": "/b.py"}, "t2"),
        ])]
        tools = extract_tool_calls(entries)
        assert len(tools) == 2
        assert tools[0].name == "Read"
        assert tools[1].name == "Edit"


class TestExtractModifiedFiles:
    def test_write_and_edit(self):
        entries = [
            make_assistant_entry([make_tool_use_block("Write", {"file_path": "/a.py"})]),
            make_assistant_entry([make_tool_use_block("Edit", {"file_path": "/b.py"})], msg_id="m2"),
        ]
        files = extract_modified_files(entries)
        assert files == ["/a.py", "/b.py"]

    def test_deduplicates(self):
        entries = [
            make_assistant_entry([make_tool_use_block("Edit", {"file_path": "/a.py"})]),
            make_assistant_entry([make_tool_use_block("Edit", {"file_path": "/a.py"})], msg_id="m2"),
        ]
        assert extract_modified_files(entries) == ["/a.py"]

    def test_ignores_read(self):
        entries = [make_assistant_entry([make_tool_use_block("Read", {"file_path": "/a.py"})])]
        assert extract_modified_files(entries) == []


class TestCalculateTokenUsage:
    def test_basic(self):
        entries = [make_assistant_entry(
            [make_text_block("hi")],
            usage={"input_tokens": 10, "output_tokens": 20,
                   "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100},
        )]
        usage = calculate_token_usage(entries)
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20
        assert usage.cache_creation_input_tokens == 5
        assert usage.cache_read_input_tokens == 100
        assert usage.total_tokens == 30

    def test_deduplicates_by_msg_id(self):
        entry = make_assistant_entry(
            [make_text_block("hi")], msg_id="same",
            usage={"input_tokens": 10, "output_tokens": 20,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        )
        entries = [entry, entry]
        usage = calculate_token_usage(entries)
        assert usage.total_tokens == 30  # not 60

    def test_sums_different_messages(self):
        e1 = make_assistant_entry(
            [make_text_block("a")], msg_id="m1",
            usage={"input_tokens": 10, "output_tokens": 20,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        )
        e2 = make_assistant_entry(
            [make_text_block("b")], msg_id="m2",
            usage={"input_tokens": 30, "output_tokens": 40,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        )
        usage = calculate_token_usage([e1, e2])
        assert usage.input_tokens == 40
        assert usage.output_tokens == 60
        assert usage.total_tokens == 100


class TestGetSessionMetadata:
    def test_extracts_fields(self):
        entries = [make_assistant_entry(
            [make_text_block("hi")],
            sessionId="sid-123", gitBranch="feat/test",
            cwd="/my/project", slug="happy-slug",
        )]
        meta = get_session_metadata(entries)
        assert meta.session_id == "sid-123"
        assert meta.git_branch == "feat/test"
        assert meta.cwd == "/my/project"
        assert meta.slug == "happy-slug"
        assert "claude-opus-4-6" in meta.models

    def test_timestamps(self):
        entries = [
            make_assistant_entry([make_text_block("a")], timestamp="2026-03-22T10:00:00Z", msg_id="m1"),
            make_assistant_entry([make_text_block("b")], timestamp="2026-03-22T11:00:00Z", msg_id="m2"),
        ]
        meta = get_session_metadata(entries)
        assert meta.first_timestamp == "2026-03-22T10:00:00Z"
        assert meta.last_timestamp == "2026-03-22T11:00:00Z"


class TestGetFileSnapshots:
    def test_extracts_snapshots(self):
        entries = [make_snapshot_entry(
            backups={"/a.py": "content_a", "/b.py": "content_b"},
        )]
        snapshots = get_file_snapshots(entries)
        assert len(snapshots) == 1
        assert set(snapshots[0].files) == {"/a.py", "/b.py"}
        assert snapshots[0].backups["/a.py"] == "content_a"

    def test_skips_non_snapshots(self):
        entries = [make_user_entry("hello")]
        assert get_file_snapshots(entries) == []


# --- Tests: Transcript Formatting ---

class TestFormatCondensedTranscript:
    def test_basic_format(self):
        msgs = [
            Message(role="user", text="hello", timestamp="2026-03-22T12:00:00Z"),
            Message(role="assistant", text="hi there", timestamp="2026-03-22T12:01:00Z"),
            Message(role="tool", text="Read: /foo.py", timestamp="2026-03-22T12:01:00Z"),
        ]
        output = format_condensed_transcript(msgs)
        assert "--- 2026-03-22 ---" in output
        assert "12:00 [User] hello" in output
        assert "12:01 [Assistant] hi there" in output
        assert "[Tool] Read: /foo.py" in output

    def test_date_separator_on_change(self):
        msgs = [
            Message(role="user", text="day1", timestamp="2026-03-22T23:59:00Z"),
            Message(role="user", text="day2", timestamp="2026-03-23T00:01:00Z"),
        ]
        output = format_condensed_transcript(msgs)
        assert "--- 2026-03-22 ---" in output
        assert "--- 2026-03-23 ---" in output

    def test_no_duplicate_date(self):
        msgs = [
            Message(role="user", text="a", timestamp="2026-03-22T10:00:00Z"),
            Message(role="user", text="b", timestamp="2026-03-22T11:00:00Z"),
        ]
        output = format_condensed_transcript(msgs)
        assert output.count("--- 2026-03-22 ---") == 1

    def test_truncates_long_user(self):
        msgs = [Message(role="user", text="x" * 2000, timestamp="2026-03-22T10:00:00Z")]
        output = format_condensed_transcript(msgs)
        assert "... (truncated)" in output

    def test_max_lines(self):
        msgs = [Message(role="user", text=f"msg{i}", timestamp=f"2026-03-22T{i:02d}:00:00Z")
                for i in range(20)]
        output = format_condensed_transcript(msgs, max_lines=5)
        assert len(output.split("\n")) == 5


# --- Tests: Session Summary Data ---

class TestSessionSummaryData:
    def test_returns_checkpoint_data(self):
        entries = [
            make_user_entry("hello"),
            make_assistant_entry([
                make_text_block("response"),
                make_tool_use_block("Edit", {"file_path": "/foo.py"}),
            ]),
        ]
        path = write_jsonl(entries)
        try:
            data = session_summary_data(path)
            assert isinstance(data, CheckpointData)
            assert isinstance(data, SessionData)  # SessionData is alias
            assert isinstance(data.metadata, SessionMetadata)
            assert isinstance(data.token_usage, TokenUsage)
            assert isinstance(data.message_counts, MessageCounts)
            assert data.message_counts.user == 1
            assert data.message_counts.assistant == 1
            assert "/foo.py" in data.modified_files
            assert len(data.messages) > 0
        finally:
            os.unlink(path)


# --- Tests: Dataclass Serialization ---

class TestSerialization:
    def test_message_fields(self):
        m = Message(role="user", text="hi", timestamp="2026-01-01T00:00:00Z")
        assert m.role == "user"
        assert m.text == "hi"

    def test_token_usage_defaults(self):
        t = TokenUsage()
        assert t.input_tokens == 0
        assert t.total_tokens == 0

    def test_session_file(self):
        s = SessionFile(path="/a.jsonl", session_id="abc", project_dir="dir",
                        size_bytes=1024, modified=datetime(2026, 1, 1))
        assert s.session_id == "abc"
        assert s.size_bytes == 1024

    def test_search_result(self):
        r = SearchResult(
            session_id="abc", path="/a.jsonl", branch="main", slug="s",
            first_timestamp="t1", last_timestamp="t2", first_prompt="hi",
            total_tokens=100, modified="2026", match_reasons=["keyword"],
        )
        assert r.branch == "main"
        assert r.keyword_matches == []
        assert r.checkpoint_id == ""

    def test_search_result_with_checkpoint_id(self):
        r = SearchResult(
            session_id="abc", path="/a.jsonl", branch="main", slug="s",
            first_timestamp="t1", last_timestamp="t2", first_prompt="hi",
            total_tokens=100, modified="2026", match_reasons=["keyword"],
            checkpoint_id="a3f8b9c1d2e45678",
        )
        assert r.checkpoint_id == "a3f8b9c1d2e45678"

    def test_checkpoint_info(self):
        cp = CheckpointInfo(
            checkpoint_id="a3f8b9c1d2e45678",
            session_id="abc-123",
            commit_sha="deadbeef",
            timestamp="2026-03-22T12:00:00Z",
        )
        assert cp.checkpoint_id == "a3f8b9c1d2e45678"
        assert cp.has_summary is False
        assert cp.intent == ""
        assert cp.merged_files == []
        assert cp.transcript_git_path == ""

    def test_checkpoint_info_with_summary(self):
        cp = CheckpointInfo(
            checkpoint_id="a3f8b9c1d2e45678",
            session_id="abc-123",
            commit_sha="deadbeef",
            timestamp="2026-03-22T12:00:00Z",
            has_summary=True,
            intent="Fix the auth bug",
            merged_files=["/a.py", "/b.py"],
            transcript_git_path="a3/f8b9c1d2e45678/transcript-abc-123.jsonl",
        )
        assert cp.has_summary is True
        assert cp.intent == "Fix the auth bug"
        assert len(cp.merged_files) == 2
        assert cp.transcript_git_path == "a3/f8b9c1d2e45678/transcript-abc-123.jsonl"

    def test_checkpoint_data_is_session_data(self):
        """CheckpointData and SessionData should be the same class."""
        assert CheckpointData is SessionData

    def test_asdict(self):
        from dataclasses import asdict
        m = Message(role="tool", text="Read: /foo.py", timestamp="t")
        d = asdict(m)
        assert d == {"role": "tool", "text": "Read: /foo.py", "timestamp": "t"}

    def test_checkpoint_info_asdict(self):
        from dataclasses import asdict
        cp = CheckpointInfo(
            checkpoint_id="abc123", session_id="s1",
            commit_sha="dead", timestamp="t",
            has_summary=True, intent="Fix bug",
        )
        d = asdict(cp)
        assert d["intent"] == "Fix bug"
        assert d["has_summary"] is True
        assert d["transcript_git_path"] == ""


# --- Tests: resolve_id ---

class TestResolveId:
    def test_resolves_existing_file(self):
        """File path that exists on disk should resolve to ('file', path)."""
        f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        f.close()
        try:
            source_type, source_path = resolve_id(f.name)
            assert source_type == "file"
            assert source_path == f.name
        finally:
            os.unlink(f.name)

    def test_resolves_checkpoint_id(self):
        """Checkpoint ID should resolve to ('git', transcript_git_path)."""
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="a3f8b9c1d2e45678",
                session_id="sid-1234",
                commit_sha="deadbeef",
                timestamp="2026-03-22T12:00:00Z",
                transcript_git_path="a3/f8b9c1d2e45678/transcript-sid-1234.jsonl",
            ),
        ]
        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            source_type, source_path = resolve_id("a3f8b9c1d2e45678")
            assert source_type == "git"
            assert source_path == "a3/f8b9c1d2e45678/transcript-sid-1234.jsonl"

    def test_resolves_session_id(self):
        """Session ID should resolve to latest checkpoint's transcript."""
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="newer_checkpoint1",
                session_id="session-uuid-1234",
                commit_sha="abc",
                timestamp="2026-03-22T13:00:00Z",
                transcript_git_path="ne/wer_checkpoint1/transcript-session-uuid-1234.jsonl",
            ),
            CheckpointInfo(
                checkpoint_id="older_checkpoint1",
                session_id="session-uuid-1234",
                commit_sha="def",
                timestamp="2026-03-22T12:00:00Z",
                transcript_git_path="ol/der_checkpoint1/transcript-session-uuid-1234.jsonl",
            ),
        ]
        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            source_type, source_path = resolve_id("session-uuid-1234")
            assert source_type == "git"
            # newest first, so first match wins
            assert "wer_checkpoint1" in source_path

    def test_resolves_partial_checkpoint_id(self):
        """Partial checkpoint ID should match via startswith."""
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="a3f8b9c1d2e45678",
                session_id="sid-1",
                commit_sha="dead",
                timestamp="t",
                transcript_git_path="a3/f8b9c1d2e45678/transcript-sid-1.jsonl",
            ),
        ]
        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            source_type, source_path = resolve_id("a3f8b9")
            assert source_type == "git"
            assert "f8b9c1d2e45678" in source_path

    def test_resolves_partial_session_id(self):
        """Partial session ID should match via startswith."""
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="cp1234567890abcd",
                session_id="session-uuid-abcd",
                commit_sha="dead",
                timestamp="t",
                transcript_git_path="cp/1234567890abcd/transcript-session-uuid-abcd.jsonl",
            ),
        ]
        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            source_type, source_path = resolve_id("session-uuid")
            assert source_type == "git"

    def test_falls_back_to_local_files(self):
        """When nothing matches in checkpoints, falls back to local glob."""
        with patch("parse_jsonl.get_all_checkpoints", return_value=[]):
            with patch("glob.glob", return_value=["/home/user/.claude/projects/foo/abc123.jsonl"]):
                source_type, source_path = resolve_id("abc123")
                assert source_type == "file"
                assert source_path == "/home/user/.claude/projects/foo/abc123.jsonl"

    def test_returns_empty_path_when_not_found(self):
        """When nothing matches at all, returns ('file', '')."""
        with patch("parse_jsonl.get_all_checkpoints", return_value=[]):
            with patch("glob.glob", return_value=[]):
                source_type, source_path = resolve_id("nonexistent")
                assert source_type == "file"
                assert source_path == ""

    def test_skips_checkpoints_without_transcript_path(self):
        """Checkpoints without transcript_git_path should be skipped."""
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="a3f8b9c1d2e45678",
                session_id="sid-1",
                commit_sha="dead",
                timestamp="t",
                transcript_git_path="",  # no transcript path
            ),
        ]
        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            with patch("glob.glob", return_value=[]):
                source_type, source_path = resolve_id("a3f8b9c1d2e45678")
                assert source_path == ""


# --- Tests: get_checkpoint_data ---

class TestGetCheckpointData:
    def test_from_file(self):
        """get_checkpoint_data reads from file when resolve_id returns file source."""
        entries = [
            make_user_entry("hello"),
            make_assistant_entry([make_text_block("response")]),
        ]
        path = write_jsonl(entries)
        try:
            with patch("parse_jsonl.resolve_id", return_value=("file", path)):
                data = get_checkpoint_data("some-id")
                assert isinstance(data, CheckpointData)
                assert data.message_counts.user == 1
                assert data.first_prompt == "hello"
        finally:
            os.unlink(path)

    def test_from_git(self):
        """get_checkpoint_data reads from git when resolve_id returns git source."""
        jsonl_content = (
            json.dumps(make_user_entry("git hello")) + "\n"
            + json.dumps(make_assistant_entry([make_text_block("git response")])) + "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = jsonl_content

        with patch("parse_jsonl.resolve_id", return_value=("git", "some/path.jsonl")):
            with patch("parse_jsonl.subprocess.run", return_value=mock_result):
                data = get_checkpoint_data("some-id")
                assert isinstance(data, CheckpointData)
                assert data.message_counts.user == 1
                assert data.first_prompt == "git hello"

    def test_empty_on_not_found(self):
        """get_checkpoint_data returns empty data when source_path is empty."""
        with patch("parse_jsonl.resolve_id", return_value=("file", "")):
            data = get_checkpoint_data("nonexistent")
            assert data.message_counts.total == 0
            assert data.first_prompt == ""


# --- Tests: Search ---

class TestSearchCheckpoints:
    def _make_checkpoint_entries(self, text="hello world", session_id="test-session",
                                  branch="main"):
        """Create JSONL entries for a checkpoint."""
        return [
            make_user_entry(text, sessionId=session_id, gitBranch=branch),
            make_assistant_entry(
                [make_text_block(f"Response about {text}")],
                sessionId=session_id, gitBranch=branch,
            ),
        ]

    def test_search_sessions_is_alias(self):
        """search_sessions should be the same function as search_checkpoints."""
        assert search_sessions is search_checkpoints

    def test_search_result_keyword_matches(self):
        km = KeywordMatch(role="user", snippet="...fixed the OAuth bug...")
        assert km.role == "user"
        assert "OAuth" in km.snippet

    def test_search_result_with_matches(self):
        r = SearchResult(
            session_id="abc", path="/a.jsonl", branch="feat/auth",
            slug="s", first_timestamp="2026-03-22T12:00:00Z",
            last_timestamp="2026-03-22T13:00:00Z",
            first_prompt="fix OAuth", total_tokens=5000,
            modified="2026-03-22", match_reasons=["keyword: 3 matches", "branch: feat/auth"],
            keyword_matches=[
                KeywordMatch(role="user", snippet="...OAuth callback..."),
                KeywordMatch(role="assistant", snippet="...OAuth handler..."),
            ],
            checkpoint_id="cp123456",
        )
        assert len(r.match_reasons) == 2
        assert len(r.keyword_matches) == 2
        assert r.branch == "feat/auth"
        assert r.checkpoint_id == "cp123456"

    def test_deduplication_per_session(self):
        """Only the latest checkpoint per session should be searched."""
        # Two checkpoints for the same session
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="newer_cp_id12345",
                session_id="session-abc",
                commit_sha="abc",
                timestamp="2026-03-22T13:00:00Z",
                transcript_git_path="ne/wer_cp_id12345/transcript-session-abc.jsonl",
            ),
            CheckpointInfo(
                checkpoint_id="older_cp_id12345",
                session_id="session-abc",
                commit_sha="def",
                timestamp="2026-03-22T12:00:00Z",
                transcript_git_path="ol/der_cp_id12345/transcript-session-abc.jsonl",
            ),
        ]

        entries = self._make_checkpoint_entries("OAuth bug fix", session_id="session-abc")
        jsonl_content = "\n".join(json.dumps(e) for e in entries) + "\n"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = jsonl_content

        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            with patch("parse_jsonl.subprocess.run", return_value=mock_result):
                with patch("parse_jsonl.find_session_files", return_value=[]):
                    results = search_checkpoints(keyword="OAuth")
                    # Should only have 1 result, not 2 (deduplication)
                    assert len(results) == 1
                    assert results[0].checkpoint_id == "newer_cp_id12345"

    def test_search_includes_checkpoint_id(self):
        """Search results should include checkpoint_id."""
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="cp_abc12345678",
                session_id="session-xyz",
                commit_sha="abc",
                timestamp="2026-03-22T12:00:00Z",
                transcript_git_path="cp/abc12345678/transcript-session-xyz.jsonl",
            ),
        ]

        entries = self._make_checkpoint_entries("test content", session_id="session-xyz")
        jsonl_content = "\n".join(json.dumps(e) for e in entries) + "\n"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = jsonl_content

        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            with patch("parse_jsonl.subprocess.run", return_value=mock_result):
                with patch("parse_jsonl.find_session_files", return_value=[]):
                    results = search_checkpoints()
                    assert len(results) == 1
                    assert results[0].checkpoint_id == "cp_abc12345678"

    def test_search_no_filters_returns_all(self):
        """With no filters, all checkpoints should be returned."""
        checkpoints = [
            CheckpointInfo(
                checkpoint_id="cp1_abcdef01234",
                session_id="session-1",
                commit_sha="aaa",
                timestamp="2026-03-22T12:00:00Z",
                transcript_git_path="cp/1_abcdef01234/transcript-session-1.jsonl",
            ),
            CheckpointInfo(
                checkpoint_id="cp2_abcdef01234",
                session_id="session-2",
                commit_sha="bbb",
                timestamp="2026-03-22T13:00:00Z",
                transcript_git_path="cp/2_abcdef01234/transcript-session-2.jsonl",
            ),
        ]

        entries1 = self._make_checkpoint_entries("first session", session_id="session-1")
        entries2 = self._make_checkpoint_entries("second session", session_id="session-2")

        call_count = [0]
        def mock_run_side_effect(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if call_count[0] == 0:
                result.stdout = "\n".join(json.dumps(e) for e in entries1) + "\n"
            else:
                result.stdout = "\n".join(json.dumps(e) for e in entries2) + "\n"
            call_count[0] += 1
            return result

        with patch("parse_jsonl.get_all_checkpoints", return_value=checkpoints):
            with patch("parse_jsonl.subprocess.run", side_effect=mock_run_side_effect):
                with patch("parse_jsonl.find_session_files", return_value=[]):
                    results = search_checkpoints()
                    assert len(results) == 2


# --- Tests: CLI Output Formatting ---

class TestCLIOutput:
    def test_stats_output(self):
        """Test that stats command produces output for a session."""
        entries = [
            make_user_entry("hello", timestamp="2026-03-22T10:00:00Z"),
            make_assistant_entry(
                [make_text_block("hi"), make_tool_use_block("Edit", {"file_path": "/foo.py"})],
                timestamp="2026-03-22T10:05:00Z",
            ),
        ]
        path = write_jsonl(entries)
        try:
            data = session_summary_data(path)
            assert data.token_usage.total_tokens > 0
            assert data.message_counts.user == 1
            assert data.message_counts.assistant == 1
            assert "/foo.py" in data.modified_files
        finally:
            os.unlink(path)

    def test_transcript_output_format(self):
        """Test transcript output has expected format markers."""
        msgs = [
            Message(role="user", text="hello world", timestamp="2026-03-22T10:00:00Z"),
            Message(role="assistant", text="hi there", timestamp="2026-03-22T10:01:00Z"),
            Message(role="tool", text="Read: /foo.py", timestamp="2026-03-22T10:01:00Z"),
        ]
        output = format_condensed_transcript(msgs)
        assert "[User] hello world" in output
        assert "[Assistant] hi there" in output
        assert "[Tool] Read: /foo.py" in output
        assert "--- 2026-03-22 ---" in output
        assert "10:00" in output
        assert "10:01" in output

    def test_transcript_no_timestamp_on_tools(self):
        """Tools should not have timestamps in output."""
        msgs = [
            Message(role="tool", text="Edit: /foo.py", timestamp="2026-03-22T10:00:00Z"),
        ]
        output = format_condensed_transcript(msgs)
        assert "[Tool] Edit: /foo.py" in output
        # Tool lines should NOT have a timestamp prefix
        lines = [l for l in output.split("\n") if "[Tool]" in l]
        assert lines[0].startswith("[Tool]")

    def test_empty_messages_produce_empty_transcript(self):
        output = format_condensed_transcript([])
        assert output.strip() == ""
