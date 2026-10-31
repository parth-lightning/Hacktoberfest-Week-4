"""Configuration management for Wraith."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def get_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "wraith"
    return Path.home() / ".config" / "wraith"


def get_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "wraith"
    return Path.home() / ".local" / "share" / "wraith"


def get_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "wraith"
    return Path.home() / ".cache" / "wraith"


def get_state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "wraith"
    return Path.home() / ".local" / "state" / "wraith"


def get_runtime_dir() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return Path(xdg) / "wraith"
    return get_cache_dir()


def get_socket_path() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return Path(xdg) / "wraith.sock"
    return get_cache_dir() / "wraith.sock"


def get_graveyard_db_path() -> Path:
    return get_data_dir() / "graveyard.db"


def get_log_file_path() -> Path:
    return get_state_dir() / "wraith.log"


def get_sessions_dir() -> Path:
    return get_runtime_dir() / "sessions"


def get_personas_dir() -> Path:
    return get_config_dir() / "personas"


@dataclass
class ModelConfig:
    backend: str = "ollama"  # "ollama" or "openai-compatible"
    name: str = "gemma3:1b"
    base_url: str = "http://127.0.0.1:11434"
    allow_remote: bool = False
    whisper_timeout: float = 3.0
    rewrite_timeout: float = 6.0


@dataclass
class WhisperConfig:
    persona: str = "poltergeist"
    cooldown_seconds: int = 20
    max_per_hour: int = 12
    ambient_probability: float = 0.05


@dataclass
class PossessConfig:
    mode: str = "annotate"  # "annotate" or "replace"
    exclude: list[str] = field(
        default_factory=lambda: ["ssh", "vim", "nvim", "less", "top", "htop", "man"]
    )


@dataclass
class PrivacyConfig:
    redact_patterns: list[str] = field(default_factory=list)
    store_commands: bool = True


@dataclass
class WraithConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    possess: PossessConfig = field(default_factory=PossessConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)

    @classmethod
    def load(cls, config_path: Path | None = None) -> WraithConfig:
        path = config_path or (get_config_dir() / "config.toml")
        if not path.is_file():
            return cls()

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return cls()

        model_data = data.get("model", {})
        whisper_data = data.get("whisper", {})
        possess_data = data.get("possess", {})
        privacy_data = data.get("privacy", {})

        return cls(
            model=ModelConfig(
                backend=model_data.get("backend", "ollama"),
                name=model_data.get("name", "gemma3:1b"),
                base_url=model_data.get("base_url", "http://127.0.0.1:11434"),
                allow_remote=bool(model_data.get("allow_remote", False)),
                whisper_timeout=float(model_data.get("whisper_timeout", 3.0)),
                rewrite_timeout=float(model_data.get("rewrite_timeout", 6.0)),
            ),
            whisper=WhisperConfig(
                persona=whisper_data.get("persona", "poltergeist"),
                cooldown_seconds=int(whisper_data.get("cooldown_seconds", 20)),
                max_per_hour=int(whisper_data.get("max_per_hour", 12)),
                ambient_probability=float(whisper_data.get("ambient_probability", 0.05)),
            ),
            possess=PossessConfig(
                mode=possess_data.get("mode", "annotate"),
                exclude=list(
                    possess_data.get(
                        "exclude", ["ssh", "vim", "nvim", "less", "top", "htop", "man"]
                    )
                ),
            ),
            privacy=PrivacyConfig(
                redact_patterns=list(privacy_data.get("redact_patterns", [])),
                store_commands=bool(privacy_data.get("store_commands", True)),
            ),
        )

    def save(self, config_path: Path | None = None) -> None:
        path = config_path or (get_config_dir() / "config.toml")
        path.parent.mkdir(parents=True, exist_ok=True)
        toml_content = f"""[model]
backend = "{self.model.backend}"
name = "{self.model.name}"
base_url = "{self.model.base_url}"
allow_remote = {str(self.model.allow_remote).lower()}
whisper_timeout = {self.model.whisper_timeout}
rewrite_timeout = {self.model.rewrite_timeout}

[whisper]
persona = "{self.whisper.persona}"
cooldown_seconds = {self.whisper.cooldown_seconds}
max_per_hour = {self.whisper.max_per_hour}
ambient_probability = {self.whisper.ambient_probability}

[possess]
mode = "{self.possess.mode}"
exclude = {self.possess.exclude!r}

[privacy]
redact_patterns = {self.privacy.redact_patterns!r}
store_commands = {str(self.privacy.store_commands).lower()}
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(toml_content)
