"""Model client factory for Wraith."""

from __future__ import annotations

from wraith.config import ModelConfig
from wraith.models.base import BaseModelClient
from wraith.models.ollama import OllamaClient
from wraith.models.openai_compat import OpenAICompatClient


def get_model_client(config: ModelConfig) -> BaseModelClient:
    """Return an initialized model client based on configuration."""
    if config.backend == "openai-compatible":
        return OpenAICompatClient(
            base_url=config.base_url,
            model_name=config.name,
            allow_remote=config.allow_remote,
        )
    return OllamaClient(
        base_url=config.base_url,
        model_name=config.name,
        allow_remote=config.allow_remote,
    )
