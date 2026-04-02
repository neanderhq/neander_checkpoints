#!/usr/bin/env bash
#
# test_auto_summarize.sh — Integration tests for auto_summarize.sh
#
# Tests the JSON extraction from claude --print output, which wraps
# JSON in markdown code fences (```json ... ```).
#
# Usage: bash tests/test_auto_summarize.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"
PASS=0
FAIL=0
TESTS=()

# --- Test helpers ---

fail() {
    echo "  FAIL: $1"
    FAIL=$((FAIL + 1))
}

pass() {
    echo "  PASS: $1"
    PASS=$((PASS + 1))
}

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        pass "$desc"
    else
        fail "$desc"
        echo "    expected: $expected"
        echo "    actual:   $actual"
    fi
}

assert_not_empty() {
    local desc="$1" actual="$2"
    if [ -n "$actual" ]; then
        pass "$desc"
    else
        fail "$desc — got empty string"
    fi
}

assert_empty() {
    local desc="$1" actual="$2"
    if [ -z "$actual" ]; then
        pass "$desc"
    else
        fail "$desc — expected empty, got: $actual"
    fi
}

# The JSON-stripping logic extracted from auto_summarize.sh for testability
strip_fences() {
    python3 -c "
import sys, json, re
raw = sys.stdin.read().strip()
cleaned = re.sub(r'^[^\S\n]*\x60\x60\x60(?:json)?\s*\n?', '', raw)
cleaned = re.sub(r'\n?[^\S\n]*\x60\x60\x60[^\S\n]*$', '', cleaned)
json.loads(cleaned)
print(cleaned)
" 2>/dev/null || echo ""
}

# --- Tests: JSON fence stripping ---

echo "=== JSON fence stripping ==="

# Test 1: JSON wrapped in ```json ... ```
RESULT="$(cat <<'INPUT' | strip_fences
```json
{"intent":"test","outcome":"done"}
```
INPUT
)"
assert_eq "strips json fences" '{"intent":"test","outcome":"done"}' "$RESULT"

# Test 2: JSON wrapped in bare ``` ... ```
RESULT="$(cat <<'INPUT' | strip_fences
```
{"intent":"test","outcome":"done"}
```
INPUT
)"
assert_eq "strips bare fences" '{"intent":"test","outcome":"done"}' "$RESULT"

# Test 3: Raw JSON without fences
RESULT="$(echo '{"intent":"test","outcome":"done"}' | strip_fences)"
assert_eq "passes through raw JSON" '{"intent":"test","outcome":"done"}' "$RESULT"

# Test 4: Invalid JSON returns empty
RESULT="$(echo 'not json at all' | strip_fences)"
assert_empty "rejects non-JSON" "$RESULT"

# Test 5: Fenced but invalid JSON returns empty
RESULT="$(cat <<'INPUT' | strip_fences
```json
not json
```
INPUT
)"
assert_empty "rejects fenced non-JSON" "$RESULT"

# Test 6: Multi-line JSON inside fences
RESULT="$(cat <<'INPUT' | strip_fences
```json
{
  "intent": "test",
  "outcome": "done",
  "learnings": {"repo": [], "code": []}
}
```
INPUT
)"
assert_not_empty "handles multi-line fenced JSON" "$RESULT"
# Validate it's parseable JSON
echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['intent']=='test'" 2>/dev/null
if [ $? -eq 0 ]; then pass "multi-line JSON is valid"; else fail "multi-line JSON is invalid"; fi

# Test 7: Fences with leading whitespace
RESULT="$(cat <<'INPUT' | strip_fences
  ```json
{"intent":"test"}
  ```
INPUT
)"
assert_eq "handles fences with leading whitespace" '{"intent":"test"}' "$RESULT"

# Test 8: Empty input
RESULT="$(echo "" | strip_fences)"
assert_empty "handles empty input" "$RESULT"


# --- Tests: Full auto_summarize.sh with mocked claude ---

echo ""
echo "=== auto_summarize.sh integration ==="

TMPDIR_ROOT="$(mktemp -d)"
cleanup() {
    rm -rf "$TMPDIR_ROOT"
}
trap cleanup EXIT

# Create a minimal transcript
TRANSCRIPT="$TMPDIR_ROOT/session.jsonl"
cat > "$TRANSCRIPT" << 'JSONL'
{"type":"user","message":{"role":"user","content":"fix the bug"},"timestamp":"2026-04-01T10:00:00.000Z"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"I'll fix it."}],"model":"claude-opus-4-6","id":"msg_01","usage":{"input_tokens":100,"output_tokens":50,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"timestamp":"2026-04-01T10:00:05.000Z","sessionId":"test-sess","cwd":"/test"}
JSONL

# Create a fake `claude` that returns fenced JSON (simulating the real behavior)
MOCK_BIN="$TMPDIR_ROOT/bin"
mkdir -p "$MOCK_BIN"
cat > "$MOCK_BIN/claude" << 'SCRIPT'
#!/usr/bin/env bash
# Mock claude --print that returns fenced JSON (like real claude does)
echo '```json'
echo '{"intent":"Fixed the bug","outcome":"Bug resolved","learnings":{"repo":[],"code":[],"workflow":[]},"friction":[],"open_items":[]}'
echo '```'
SCRIPT
chmod +x "$MOCK_BIN/claude"

# Create a mock save_summary.sh that just records what it received
MOCK_SCRIPTS="$TMPDIR_ROOT/mock_scripts"
mkdir -p "$MOCK_SCRIPTS"
cp "$SCRIPT_DIR/parse_jsonl.py" "$MOCK_SCRIPTS/"
cat > "$MOCK_SCRIPTS/save_summary.sh" << 'SCRIPT'
#!/usr/bin/env bash
# Record the summary that was passed
CHECKPOINT_ID="$1"
SUMMARY_FILE="$2"
cp "$SUMMARY_FILE" "/tmp/test-saved-summary-$CHECKPOINT_ID.json"
echo "MOCK: saved summary for $CHECKPOINT_ID"
SCRIPT
chmod +x "$MOCK_SCRIPTS/save_summary.sh"

# Create a modified auto_summarize.sh that uses our mock scripts dir
MOCK_AUTO="$MOCK_SCRIPTS/auto_summarize.sh"
sed "s|SCRIPT_DIR=.*|SCRIPT_DIR=\"$MOCK_SCRIPTS\"|" "$SCRIPT_DIR/auto_summarize.sh" > "$MOCK_AUTO"
chmod +x "$MOCK_AUTO"

# Run auto_summarize with mocked claude in PATH
SAVED_SUMMARY="/tmp/test-saved-summary-testcheckpoint1.json"
rm -f "$SAVED_SUMMARY"
PATH="$MOCK_BIN:$PATH" bash "$MOCK_AUTO" "testcheckpoint1" "$TRANSCRIPT" 0 2>&1

if [ -f "$SAVED_SUMMARY" ]; then
    # Verify the saved summary is valid JSON
    INTENT="$(python3 -c "import json; print(json.load(open('$SAVED_SUMMARY'))['intent'])" 2>/dev/null || echo "")"
    assert_eq "auto_summarize saves valid summary through fenced output" "Fixed the bug" "$INTENT"
    rm -f "$SAVED_SUMMARY"
else
    fail "auto_summarize did not save summary (save_summary.sh was never called)"
fi

# Test with mock claude returning raw JSON (no fences)
cat > "$MOCK_BIN/claude" << 'SCRIPT'
#!/usr/bin/env bash
echo '{"intent":"Raw output","outcome":"No fences","learnings":{"repo":[],"code":[],"workflow":[]},"friction":[],"open_items":[]}'
SCRIPT
chmod +x "$MOCK_BIN/claude"

rm -f "$SAVED_SUMMARY"
PATH="$MOCK_BIN:$PATH" bash "$MOCK_AUTO" "testcheckpoint1" "$TRANSCRIPT" 0 2>&1

if [ -f "$SAVED_SUMMARY" ]; then
    INTENT="$(python3 -c "import json; print(json.load(open('$SAVED_SUMMARY'))['intent'])" 2>/dev/null || echo "")"
    assert_eq "auto_summarize handles raw JSON (no fences)" "Raw output" "$INTENT"
    rm -f "$SAVED_SUMMARY"
else
    fail "auto_summarize did not save summary for raw JSON output"
fi

# Test with empty transcript offset past end of file
rm -f "$SAVED_SUMMARY"
PATH="$MOCK_BIN:$PATH" bash "$MOCK_AUTO" "testcheckpoint1" "$TRANSCRIPT" 9999 2>&1

if [ ! -f "$SAVED_SUMMARY" ]; then
    pass "auto_summarize skips when transcript offset is past end of file"
else
    fail "auto_summarize should not save summary when transcript is empty"
    rm -f "$SAVED_SUMMARY"
fi


# --- Summary ---

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
