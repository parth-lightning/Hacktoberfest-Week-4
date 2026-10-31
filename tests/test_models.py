"""Tests for model backends and loopback security validator (FR-28, NFR-4)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from wraith.models.base import validate_loopback_url
from wraith.models.ollama import OllamaClient
from wraith.models.openai_compat import OpenAICompatClient


def test_loopback_url_allowed():
    # Should not raise
    validate_loopback_url("http://127.0.0.1:11434")
    validate_loopback_url("http://localhost:11434")
    validate_loopback_url("http://[::1]:8080")


def test_loopback_url_rejected_by_default():
    remote_urls = [
        "https://api.openai.com",
        "http://192.168.1.100:11434",
        "http://my-remote-server.com:11434",
        "http://10.0.0.5:8000",
    ]
    for url in remote_urls:
        with pytest.raises(ValueError, match="Security violation: Model URL"):
            validate_loopback_url(url, allow_remote=False)


def test_loopback_url_allowed_with_explicit_flag():
    # Should not raise when allow_remote is True
    validate_loopback_url("http://192.168.1.100:11434", allow_remote=True)


@pytest.mark.asyncio
async def test_ollama_client_chat():
    client = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model_name="gemma3:1b",
    )
    mock_response = httpx.Response(
        status_code=200,
        json={"message": {"role": "assistant", "content": "The shadows whisper back."}},
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        reply = await client.chat([{"role": "user", "content": "hi"}])
        assert reply == "The shadows whisper back."


@pytest.mark.asyncio
async def test_openai_compat_client_chat():
    client = OpenAICompatClient(
        base_url="http://127.0.0.1:8000",
        model_name="qwen2.5:1.5b",
    )
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "A séance in the terminal."}}]
        },
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        reply = await client.chat([{"role": "user", "content": "hi"}])
        assert reply == "A séance in the terminal."
