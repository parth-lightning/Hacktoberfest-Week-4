"""Persona loading and management for Wraith."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wraith.config import get_personas_dir

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

BUNDLED_PERSONAS_DIR = Path(__file__).parent / "personas"


def safe_glyph(glyph: str, fallback: str = "~") -> str:
    """Return the glyph if encodable by current stdout, otherwise ASCII fallback."""
    try:
        enc = sys.stdout.encoding or "utf-8"
        glyph.encode(enc)
        return glyph
    except Exception:
        return fallback


@dataclass
class Persona:
    name: str
    description: str
    ghost_glyph: str = "👻"
    temperature: float = 0.8
    system_prompt: str = ""
    style_rules: list[str] = field(default_factory=list)
    few_shot: list[dict[str, str]] = field(default_factory=list)


def load_persona(name: str) -> Persona:
    """Load a persona by name from user personas dir, falling back to bundled personas."""
    user_file = get_personas_dir() / f"{name}.toml"
    bundled_file = BUNDLED_PERSONAS_DIR / f"{name}.toml"

    target_path = user_file if user_file.is_file() else bundled_file
    if not target_path.is_file():
        # Fallback to poltergeist
        target_path = BUNDLED_PERSONAS_DIR / "poltergeist.toml"

    try:
        with open(target_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        data = {
            "name": name,
            "description": "Default ghostly persona",
            "ghost_glyph": "👻",
            "temperature": 0.8,
            "system_prompt": "You are a mischievous ghost haunting the terminal.",
            "style_rules": ["one line", "max 25 words"],
            "few_shot": [],
        }

    return Persona(
        name=data.get("name", name),
        description=data.get("description", ""),
        ghost_glyph=data.get("ghost_glyph", "👻"),
        temperature=float(data.get("temperature", 0.8)),
        system_prompt=data.get("system_prompt", ""),
        style_rules=list(data.get("style_rules", [])),
        few_shot=list(data.get("few_shot", [])),
    )


def list_personas() -> list[dict[str, Any]]:
    """List all available personas (bundled + user created)."""
    found: dict[str, dict[str, Any]] = {}

    # 1. Bundled
    if BUNDLED_PERSONAS_DIR.is_dir():
        for p in BUNDLED_PERSONAS_DIR.glob("*.toml"):
            persona = load_persona(p.stem)
            found[p.stem] = {
                "name": persona.name,
                "description": persona.description,
                "glyph": persona.ghost_glyph,
                "custom": False,
            }

    # 2. User directory
    user_dir = get_personas_dir()
    if user_dir.is_dir():
        for p in user_dir.glob("*.toml"):
            persona = load_persona(p.stem)
            found[p.stem] = {
                "name": persona.name,
                "description": persona.description,
                "glyph": persona.ghost_glyph,
                "custom": True,
            }

    return list(found.values())


def scaffold_persona(name: str) -> Path:
    """Scaffold a new persona template file in user personas dir."""
    target_dir = get_personas_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{name}.toml"
    if target_file.exists():
        raise FileExistsError(f"Persona '{name}' already exists at {target_file}")

    content = f"""name = "{name}"
description = "A custom ghostly companion."
ghost_glyph = "💀"
temperature = 0.8
system_prompt = "You are a spectral entity haunting this terminal. Speak in short, evocative phrases."
style_rules = [
    "exactly one line",
    "maximum 25 words",
    "never suggest commands",
]

[[few_shot]]
event = "rm -rf project"
whisper = "The void swallows the code, leaving only dust and echoes."

[[few_shot]]
event = "git push --force"
whisper = "The timeline fractures beneath your insistent fingers."
"""
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)

    return target_file
