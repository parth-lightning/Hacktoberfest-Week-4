"""Ollama local model client."""

from __future__ import annotations

import httpx

from wraith.models.base import BaseModelClient


class OllamaClient(BaseModelClient):
    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 60,
        temperature: float = 0.8,
        timeout: float = 3.0,
    ) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {})
            return message.get("content", "").strip()

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def is_model_installed(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                # Match e.g. "gemma3:1b" or "gemma3:1b-latest"
                for m in models:
                    if m == self.model_name or m.startswith(f"{self.model_name}:"):
                        return True
                    if self.model_name.endswith(":latest") and m == self.model_name[:-7]:
                        return True
                return False
        except Exception:
            return False
