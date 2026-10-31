"""Output validation and fact-preservation verification for Wraith."""

from __future__ import annotations

import re

# ANSI escape sequence regex
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Command suggestion detection regex
COMMAND_SUGGESTION_RE = re.compile(
    r"(?i)(?:\b(?:try\s+(?:running|typing|executing)|you\s+should\s+run|pip\s+install|npm\s+install|cargo\s+add|brew\s+install|apt\s+install)\b|\b(?:run|execute|command)\s*[:`])"
)

# Extract key tokens from error text
ERROR_TYPE_RE = re.compile(r"\b([A-Za-z0-9_]+(?:Error|Exception|Fault|Warning))\b")
QUOTED_TOKEN_RE = re.compile(r"['\"]([A-Za-z0-9_./\-]+)['\"]")
LINE_NUM_RE = re.compile(r"\bline\s+([0-9]+)\b", re.IGNORECASE)
FILE_NAME_RE = re.compile(r"\b([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]{1,4})\b")


def clean_output(text: str) -> str:
    """Strip ANSI escapes, control characters, and leading/trailing whitespace/quotes."""
    no_ansi = ANSI_ESCAPE_RE.sub("", text)
    # Remove control characters except newline
    no_ctrl = "".join(ch for ch in no_ansi if ch == "\n" or (ch >= " " and ord(ch) != 127))
    cleaned = no_ctrl.strip()
    # Strip wrapping quotes if the model wrapped the output
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def validate_whisper(text: str, max_words: int = 25) -> tuple[bool, str]:
    """Validate a generated whisper.

    Returns (is_valid, cleaned_text).
    Must be single line, <= max_words, non-empty, and free of command suggestions.
    """
    cleaned = clean_output(text)

    # Must be non-empty
    if not cleaned:
        return False, ""

    # Must be single line (take first non-empty line if multiple returned)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return False, ""
    single_line = lines[0]

    # Check word count
    words = single_line.split()
    if len(words) > max_words:
        # Truncate to max_words gracefully if slightly over, or fail if grossly over
        if len(words) <= max_words + 5:
            single_line = " ".join(words[:max_words]) + "..."
        else:
            return False, single_line

    # Must not suggest commands
    if COMMAND_SUGGESTION_RE.search(single_line):
        return False, single_line

    return True, single_line


def extract_key_tokens(error_text: str, max_tokens: int = 5) -> list[str]:
    """Extract key factual tokens from error text: error names, quoted entities, filenames, line numbers."""
    tokens: list[str] = []

    # 1. Error class/type (e.g. ModuleNotFoundError)
    for match in ERROR_TYPE_RE.finditer(error_text):
        token = match.group(1)
        if token not in tokens:
            tokens.append(token)

    # 2. Quoted entities (e.g. 'requests', "package")
    for match in QUOTED_TOKEN_RE.finditer(error_text):
        token = match.group(1)
        if token not in tokens and len(token) > 1:
            tokens.append(token)

    # 3. Line numbers
    for match in LINE_NUM_RE.finditer(error_text):
        token = f"line {match.group(1)}"
        if token not in tokens:
            tokens.append(token)

    # 4. File names
    for match in FILE_NAME_RE.finditer(error_text):
        token = match.group(1)
        if token not in tokens:
            tokens.append(token)

    return tokens[:max_tokens]


def check_fact_preservation(rewrite: str, key_tokens: list[str]) -> bool:
    """Verify that key tokens extracted from original error are preserved in rewrite.

    Requires at least 50% (or all if <= 2) of key tokens to be present case-insensitively.
    """
    if not key_tokens:
        return True

    rewrite_lower = rewrite.lower()
    matches = sum(1 for token in key_tokens if token.lower() in rewrite_lower)

    if len(key_tokens) <= 2:
        return matches >= len(key_tokens)
    return matches >= (len(key_tokens) + 1) // 2


def validate_rewrite(rewrite: str, key_tokens: list[str], max_lines: int = 3) -> tuple[bool, str]:
    """Validate possessed error rewrite.

    Returns (is_valid, cleaned_text).
    """
    cleaned = clean_output(rewrite)
    if not cleaned:
        return False, ""

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) > max_lines:
        lines = lines[:max_lines]

    result = "\n".join(lines)

    # Must not suggest commands
    if COMMAND_SUGGESTION_RE.search(result):
        return False, result

    # Check fact preservation
    if not check_fact_preservation(result, key_tokens):
        return False, result

    return True, result
