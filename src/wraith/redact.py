"""Redaction engine for Wraith.

Ensures sensitive information (passwords, tokens, keys, credentials)
is stripped before storage and before model inference.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

# 1. AWS Access Key ID
AWS_KEY_PATTERN = re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")

# 2. JWT pattern (three base64url segments separated by dots)
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")

# 3. URLs with embedded credentials, e.g. https://user:pass@example.com
URL_CREDENTIALS_PATTERN = re.compile(
    r"(https?|ftp|postgres|postgresql|mysql|mongodb|redis)://([^:\s/@]+):([^@\s/]+)@"
)

# 4. Authorization headers
AUTH_HEADER_PATTERN = re.compile(
    r"(?i)\b(authorization\s*:\s*(?:bearer|basic|token)?\s*)([A-Za-z0-9_.\-+/=]+)"
)

# 5. CLI flags with arguments: --password <val>, -p <val>, --token <val>, --key <val>, --secret <val>
# Handles both `--password=foo` and `--password foo`
CLI_FLAG_EQUALS_PATTERN = re.compile(
    r"(?i)(--(?:password|token|secret|api-?key|auth|access-?token)|-p)\s*=\s*([^\s'\"]+|'[^']*'|\"[^\"]*\")"
)
CLI_FLAG_SPACE_PATTERN = re.compile(
    r"(?i)(--(?:password|token|secret|api-?key|auth|access-?token)|-p)\s+([^\s'\"]+|'[^']*'|\"[^\"]*\")"
)

# 6. Environment variable assignment: KEY=value where KEY contains pass, pwd, secret, token, key, auth
ENV_VAR_PATTERN = re.compile(
    r"(?i)\b([A-Za-z0-9_]*(?:key|token|secret|pass|pwd|auth)[A-Za-z0-9_]*)\s*=\s*([^\s'\"]+|'[^']*'|\"[^\"]*\")"
)

# 7. Generic private key blocks
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
)

# 8. GitHub / Slack / Generic tokens
GENERIC_TOKEN_PATTERN = re.compile(
    r"\b(ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9\-]+)\b"
)


def _shannon_entropy(s: str) -> float:
    """Calculate the Shannon entropy of a string."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for char in s:
        freq[char] = freq.get(char, 0) + 1
    entropy = 0.0
    length = len(s)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def _redact_high_entropy_tokens(text: str) -> str:
    """Mask standalone high-entropy tokens (>= 40 chars alphanumeric without whitespace/path chars)."""
    words = text.split(" ")
    redacted_words = []
    for word in words:
        clean = word.strip("'\"")
        # Don't redact common paths or long url query strings if not standalone token
        if len(clean) >= 40 and "/" not in clean and "\\" not in clean and "=" not in clean:
            # Check if alphanumeric or base64-like
            if re.match(r"^[A-Za-z0-9_\-+/]{40,}$", clean):
                if _shannon_entropy(clean) >= 3.5:
                    redacted_words.append("<redacted>")
                    continue
        redacted_words.append(word)
    return " ".join(redacted_words)


def redact(command_text: str, custom_patterns: Sequence[str] | None = None) -> str:
    """Sanitize command_text by replacing credentials and sensitive tokens with <redacted>.

    Preserves normal commands, flags, filenames, and structure.
    """
    if not command_text:
        return ""

    result = command_text

    # Private key blocks
    result = PRIVATE_KEY_PATTERN.sub("<redacted>", result)

    # URLs with credentials
    result = URL_CREDENTIALS_PATTERN.sub(r"\1://<redacted>@", result)

    # Auth headers
    result = AUTH_HEADER_PATTERN.sub(r"\1<redacted>", result)

    # CLI flag assignments: --password=xxx
    result = CLI_FLAG_EQUALS_PATTERN.sub(r"\1=<redacted>", result)

    # CLI flag with space: --password xxx, -p xxx
    result = CLI_FLAG_SPACE_PATTERN.sub(r"\1 <redacted>", result)

    # KEY=value
    result = ENV_VAR_PATTERN.sub(r"\1=<redacted>", result)

    # AWS keys
    result = AWS_KEY_PATTERN.sub("<redacted>", result)

    # Known token formats (GitHub, Slack)
    result = GENERIC_TOKEN_PATTERN.sub("<redacted>", result)

    # JWTs
    result = JWT_PATTERN.sub("<redacted>", result)

    # High-entropy tokens
    result = _redact_high_entropy_tokens(result)

    # User-defined custom patterns
    if custom_patterns:
        for pat in custom_patterns:
            try:
                rx = re.compile(pat)
                result = rx.sub("<redacted>", result)
            except Exception:
                pass

    return result
