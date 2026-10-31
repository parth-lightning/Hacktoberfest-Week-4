"""Rate limiter for ghostly whispers.

Enforces:
- Global cooldown (default 20s) between whispers.
- Hourly cap (default 12 whispers/hour).
- Dangerous command triggers bypass the cooldown, but NOT the hourly cap.
"""

from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    def __init__(self, cooldown_seconds: int = 20, max_per_hour: int = 12) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.max_per_hour = max_per_hour
        self.last_whisper_time: float = 0.0
        self.whisper_timestamps: deque[float] = deque()

    def can_whisper(self, is_dangerous: bool = False, now: float | None = None) -> bool:
        current_time = time.time() if now is None else now

        # Prune timestamps older than 1 hour (3600 seconds)
        cutoff = current_time - 3600
        while self.whisper_timestamps and self.whisper_timestamps[0] < cutoff:
            self.whisper_timestamps.popleft()

        # Check hourly cap
        if len(self.whisper_timestamps) >= self.max_per_hour:
            return False

        # Dangerous commands bypass cooldown
        if is_dangerous:
            return True

        # Check cooldown
        if (current_time - self.last_whisper_time) < self.cooldown_seconds:
            return False

        return True

    def record_whisper(self, now: float | None = None) -> None:
        current_time = time.time() if now is None else now
        self.last_whisper_time = current_time
        self.whisper_timestamps.append(current_time)
