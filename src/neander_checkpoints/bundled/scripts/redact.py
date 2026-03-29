#!/usr/bin/env python3
"""
Secret redaction for Claude Code session transcripts.

Three-layer detection:
1. Shannon entropy analysis (high-entropy strings likely to be secrets)
2. Pattern matching (known secret formats: API keys, tokens, passwords)
3. PII detection (emails, phone numbers)

Usage:
    python3 redact.py <input.jsonl> [output.jsonl]
    python3 redact.py --check <input.jsonl>   # dry-run, report only
"""

import json
import math
import re
import sys
from pathlib import Path

REDACTED = "[REDACTED]"

# --- Layer 1: Entropy ---

def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())

ENTROPY_THRESHOLD = 4.5
MIN_ENTROPY_LENGTH = 16

# --- Layer 2: Known secret patterns ---

SECRET_PATTERNS = [
    # API keys
    (r"sk-[a-zA-Z0-9]{20,}", "API key (sk-)"),
    (r"sk-ant-[a-zA-Z0-9\-]{20,}", "Anthropic API key"),
    (r"ghp_[a-zA-Z0-9]{36,}", "GitHub PAT"),
    (r"gho_[a-zA-Z0-9]{36,}", "GitHub OAuth"),
    (r"github_pat_[a-zA-Z0-9_]{22,}", "GitHub fine-grained PAT"),
    (r"glpat-[a-zA-Z0-9\-]{20,}", "GitLab PAT"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"xox[bpors]-[a-zA-Z0-9\-]{10,}", "Slack token"),
    (r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+", "Slack webhook"),
    (r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}", "SendGrid key"),
    (r"sq0[a-z]{3}-[a-zA-Z0-9\-_]{22,}", "Square token"),
    (r"eyJ[a-zA-Z0-9_\-]{20,}\.eyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{20,}", "JWT"),

    # Generic secrets
    (r"(?i)(?:password|passwd|pwd)\s*[=:]\s*['\"]?([^\s'\"]{8,})", "Password assignment"),
    (r"(?i)(?:secret|token|api_key|apikey|auth)\s*[=:]\s*['\"]?([^\s'\"]{8,})", "Secret assignment"),
    (r"(?i)Bearer\s+[a-zA-Z0-9\-._~+/]{20,}", "Bearer token"),
    (r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----", "Private key"),

    # Connection strings
    (r"(?:mongodb|postgres|mysql|redis)://[^\s'\"]{10,}", "Database connection string"),
]

COMPILED_PATTERNS = [(re.compile(p), desc) for p, desc in SECRET_PATTERNS]

# --- Layer 3: PII ---

PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email"),
    (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "Phone number"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
]

COMPILED_PII = [(re.compile(p), desc) for p, desc in PII_PATTERNS]

# --- Skip heuristics ---

# Fields that commonly contain high-entropy but non-secret data
SKIP_KEYS = {"id", "uuid", "messageId", "parentUuid", "requestId", "toolUseID",
             "parentToolUseID", "sessionId", "signature", "file_path", "path"}


def find_secrets_in_string(text: str, context: str = "") -> list[dict]:
    """Find potential secrets in a string."""
    findings = []

    # Pattern matching
    for pattern, desc in COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({
                "type": "pattern",
                "description": desc,
                "match": match.group()[:50],
                "start": match.start(),
                "end": match.end(),
                "context": context,
            })

    # PII
    for pattern, desc in COMPILED_PII:
        for match in pattern.finditer(text):
            findings.append({
                "type": "pii",
                "description": desc,
                "match": match.group(),
                "start": match.start(),
                "end": match.end(),
                "context": context,
            })

    # Entropy analysis on word-like tokens
    for token_match in re.finditer(r"[a-zA-Z0-9_\-./+]{16,}", text):
        token = token_match.group()
        # Skip file paths and common patterns
        if token.startswith("/") or token.startswith("./"):
            continue
        if token.count("/") > 2:  # likely a path
            continue
        entropy = shannon_entropy(token)
        if entropy >= ENTROPY_THRESHOLD:
            findings.append({
                "type": "entropy",
                "description": f"High entropy ({entropy:.2f})",
                "match": token[:50],
                "start": token_match.start(),
                "end": token_match.end(),
                "context": context,
            })

    return findings


def redact_string(text: str) -> tuple[str, list[dict]]:
    """Redact secrets from a string, return (redacted_text, findings)."""
    findings = find_secrets_in_string(text)
    if not findings:
        return text, []

    # Sort by position descending so replacements don't shift offsets
    findings.sort(key=lambda f: f["start"], reverse=True)
    result = text
    for f in findings:
        result = result[:f["start"]] + REDACTED + result[f["end"]:]

    return result, findings


def redact_value(obj, key_path: str = "") -> tuple:
    """Recursively redact secrets in a JSON-like object."""
    all_findings = []

    if isinstance(obj, str):
        current_key = key_path.split(".")[-1] if key_path else ""
        if current_key in SKIP_KEYS:
            return obj, []
        redacted, findings = redact_string(obj)
        return redacted, findings

    elif isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            new_path = f"{key_path}.{k}" if key_path else k
            redacted_v, findings = redact_value(v, new_path)
            result[k] = redacted_v
            all_findings.extend(findings)
        return result, all_findings

    elif isinstance(obj, list):
        result = []
        for i, item in enumerate(obj):
            redacted_item, findings = redact_value(item, f"{key_path}[{i}]")
            result.append(redacted_item)
            all_findings.extend(findings)
        return result, all_findings

    return obj, []


def redact_jsonl(input_path: str, output_path: str = None, check_only: bool = False) -> dict:
    """Redact an entire JSONL file."""
    total_findings = []
    output_lines = []

    with open(input_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                output_lines.append("")
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                output_lines.append(line)
                continue

            redacted_obj, findings = redact_value(obj)
            for finding in findings:
                finding["line"] = line_num
            total_findings.extend(findings)
            output_lines.append(json.dumps(redacted_obj, separators=(",", ":")))

    if not check_only and output_path:
        with open(output_path, "w") as f:
            for line in output_lines:
                f.write(line + "\n")

    return {
        "input": input_path,
        "output": output_path,
        "total_findings": len(total_findings),
        "by_type": {
            "pattern": len([f for f in total_findings if f["type"] == "pattern"]),
            "pii": len([f for f in total_findings if f["type"] == "pii"]),
            "entropy": len([f for f in total_findings if f["type"] == "entropy"]),
        },
        "findings": total_findings if check_only else [],
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: redact.py [--check] <input.jsonl> [output.jsonl]", file=sys.stderr)
        sys.exit(1)

    check_only = "--check" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--check"]

    input_file = args[0]
    output_file = args[1] if len(args) > 1 else input_file.replace(".jsonl", ".redacted.jsonl")

    result = redact_jsonl(input_file, output_file, check_only=check_only)

    if check_only:
        print(json.dumps(result, indent=2, default=str))
        if result["total_findings"] > 0:
            print(f"\n⚠ Found {result['total_findings']} potential secrets", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Redacted {result['total_findings']} findings → {output_file}")
