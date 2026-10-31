"""OpenAI-compatible local model client (llama.cpp, LM Studio)."""

from __future__ import annotations

import httpx

from wraith.models.base import BaseModelClient


class OpenAICompatClient(BaseModelClient):
    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 60,
        temperature: float = 0.8,
        timeout: float = 3.0,
    ) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            msg = choices[0].get("message", {})
            return msg.get("content", "").strip()

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self.base_url}/v1/models")
                return resp.status_code == 200
        except Exception:
            return False

    async def is_model_installed(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models")
                if resp.status_code != 200:
                    return False
                data = resp.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                return any(self.model_name in m for m in models) or len(models) > 0
        except Exception:
            return False
