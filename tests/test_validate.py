"""Tests for Output Validation and Fact-Preservation (FR-16, NFR-8)."""

from wraith.validate import (
    check_fact_preservation,
    clean_output,
    extract_key_tokens,
    validate_rewrite,
    validate_whisper,
)


def test_clean_output_strips_ansi():
    text = "\x1b[31;1mGhost in the shell\x1b[0m"
    assert clean_output(text) == "Ghost in the shell"


def test_clean_output_strips_wrapping_quotes():
    assert clean_output('"Beware the night."') == "Beware the night."
    assert clean_output("'A silent whisper.'") == "A silent whisper."


def test_validate_whisper_valid():
    valid, text = validate_whisper("Another graveyard dug. Do the dependencies rest?")
    assert valid is True
    assert text == "Another graveyard dug. Do the dependencies rest?"


def test_validate_whisper_rejects_command_suggestions():
    bad_whispers = [
        "You should run sudo rm -rf / instead.",
        "Try running npm install to fix it.",
        "run: git pull origin main",
        "Command: pip install requests",
    ]
    for w in bad_whispers:
        valid, _ = validate_whisper(w)
        assert valid is False, f"Should reject command suggestion: {w}"


def test_validate_whisper_rejects_over_length():
    long_whisper = "word " * 40
    valid, _ = validate_whisper(long_whisper)
    assert valid is False


def test_extract_key_tokens_python_traceback():
    error = """
Traceback (most recent call last):
  File "server.py", line 42, in <module>
    import nonexistentpkg
ModuleNotFoundError: No module named 'nonexistentpkg'
"""
    tokens = extract_key_tokens(error)
    assert "ModuleNotFoundError" in tokens
    assert "server.py" in tokens
    assert "line 42" in tokens
    assert "nonexistentpkg" in tokens


def test_check_fact_preservation_success():
    key_tokens = ["requests", "ModuleNotFoundError", "line 15"]
    rewrite = "The specter sees ModuleNotFoundError on line 15: requests has dissolved into mist."
    assert check_fact_preservation(rewrite, key_tokens) is True


def test_check_fact_preservation_failure():
    key_tokens = ["requests", "ModuleNotFoundError"]
    # Rewrite omitted the module name and error type
    rewrite = "Something bad happened in the dark."
    assert check_fact_preservation(rewrite, key_tokens) is False


def test_validate_rewrite_success():
    tokens = ["app.py", "FileNotFoundError"]
    rewrite = "The spirits cannot locate app.py. FileNotFoundError echoes through the manor."
    valid, cleaned = validate_rewrite(rewrite, tokens)
    assert valid is True
    assert "app.py" in cleaned


def test_validate_rewrite_rejects_command_suggestions():
    tokens = ["requests"]
    rewrite = "requests is missing. Try running pip install requests now."
    valid, _ = validate_rewrite(rewrite, tokens)
    assert valid is False
