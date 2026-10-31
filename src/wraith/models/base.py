"""Base class and loopback security validator for model clients."""

from __future__ import annotations

import ipaddress
import logging
from abc import ABC, abstractmethod
from urllib.parse import urlparse

logger = logging.getLogger("wraith")


def validate_loopback_url(url: str, allow_remote: bool = False) -> None:
    """Validate that the given URL points to a loopback address.

    Raises ValueError if the URL points to a remote host and allow_remote is False.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError(f"Invalid URL without hostname: '{url}'")

    if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
        return

    # Check if IP address is loopback
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback:
            return
    except ValueError:
        pass

    if not allow_remote:
        raise ValueError(
            f"Security violation: Model URL '{url}' is not a local loopback address. "
            "To allow remote inference, set allow_remote = true in config.toml."
        )

    logger.warning("LOUD WARNING: allow_remote is enabled! Commands/errors may leave this machine.")


class BaseModelClient(ABC):
    def __init__(self, base_url: str, model_name: str, allow_remote: bool = False) -> None:
        validate_loopback_url(base_url, allow_remote=allow_remote)
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.allow_remote = allow_remote

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 60,
        temperature: float = 0.8,
        timeout: float = 3.0,
    ) -> str:
        """Send chat messages to the model and return the generated text response."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if backend is reachable."""

    @abstractmethod
    async def is_model_installed(self) -> bool:
        """Check if configured model is installed/pulled."""
