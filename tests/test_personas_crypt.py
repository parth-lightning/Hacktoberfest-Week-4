"""Tests for Personas and The Crypt offline fallback (FR-19, FR-20, FR-32)."""

from wraith.crypt import CRYPT_WHISPERS, get_crypt_error_rewrite, get_crypt_whisper
from wraith.personas import list_personas, load_persona, scaffold_persona


def test_load_bundled_personas():
    for name in ["poltergeist", "victorian-medium", "ancestor"]:
        persona = load_persona(name)
        assert persona.name == name
        assert len(persona.system_prompt) > 10
        assert len(persona.style_rules) >= 2
        assert len(persona.few_shot) >= 3
        assert persona.ghost_glyph in ("👻", "🕯️", "🌼")


def test_list_personas():
    personas = list_personas()
    names = [p["name"] for p in personas]
    assert "poltergeist" in names
    assert "victorian-medium" in names
    assert "ancestor" in names


def test_scaffold_new_persona(tmp_path, monkeypatch):
    monkeypatch.setattr("wraith.personas.get_personas_dir", lambda: tmp_path)
    target = scaffold_persona("test-banshee")
    assert target.is_file()

    p = load_persona("test-banshee")
    assert p.name == "test-banshee"
    assert p.ghost_glyph == "💀"


def test_crypt_has_at_least_20_whispers_per_persona():
    for p_name, triggers in CRYPT_WHISPERS.items():
        total_whispers = sum(len(w_list) for w_list in triggers.values())
        assert total_whispers >= 20, (
            f"Persona {p_name} has only {total_whispers} whispers (need >= 20)"
        )


def test_crypt_whisper_fallback():
    triggers = [
        "dangerous_command",
        "repetition",
        "repeated_failure",
        "command_not_found",
        "late_night",
        "returning",
        "graveyard_recall",
        "session_end",
        "ambient",
    ]
    for p in ["poltergeist", "victorian-medium", "ancestor"]:
        for t in triggers:
            w = get_crypt_whisper(p, t)
            assert isinstance(w, str)
            assert len(w) > 5


def test_crypt_error_rewrite_fact_preservation():
    key_tokens = ["requests", "ModuleNotFoundError"]
    for p in ["poltergeist", "victorian-medium", "ancestor"]:
        rewrite = get_crypt_error_rewrite(p, "error text", key_tokens)
        assert "requests" in rewrite
        assert "ModuleNotFoundError" in rewrite
