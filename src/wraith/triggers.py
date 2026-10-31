"""Event trigger detection engine for Wraith whispers."""

from __future__ import annotations

import datetime
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from wraith.graveyard import Graveyard, hash_command

DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b"),  # rm -rf, rm -fr, rm -r -f
    re.compile(r"\bsudo\s+rm\b"),
    re.compile(r"\bgit\s+push\s+.*(--force|-f)\b"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\bchmod\s+(-[a-zA-Z]*R[a-zA-Z]*\s+)?777\b"),
    re.compile(r"\bdd\s+if="),
    re.compile(r"\bkill\s+-9\b"),
    re.compile(r"(?i)\bDROP\s+TABLE\b"),
    re.compile(r"\bmkfs\b"),
]


@dataclass
class TriggerResult:
    triggered: bool
    name: str | None = None
    is_dangerous: bool = False
    context: dict[str, Any] | None = None


def is_dangerous_command(cmd: str) -> bool:
    """Check if command matches known high-risk/dangerous patterns."""
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(cmd):
            return True
    return False


class TriggerEngine:
    def __init__(self, graveyard: Graveyard, ambient_probability: float = 0.05) -> None:
        self.graveyard = graveyard
        self.ambient_probability = ambient_probability

    def evaluate(
        self,
        cmd: str,
        exit_code: int | None,
        session_id: str | None,
        session_recent_commands: Sequence[dict[str, Any]] | None = None,
        now: float | None = None,
    ) -> TriggerResult:
        dt = datetime.datetime.now() if now is None else datetime.datetime.fromtimestamp(now)
        current_ts = dt.timestamp()
        cmd_clean = cmd.strip()
        c_hash = hash_command(cmd_clean)

        # 1. Dangerous commands
        if is_dangerous_command(cmd_clean):
            return TriggerResult(
                triggered=True,
                name="dangerous_command",
                is_dangerous=True,
                context={"reason": "high-risk command detected"},
            )

        # 2. Command not found (exit code 127 in bash/zsh)
        if exit_code == 127:
            return TriggerResult(
                triggered=True,
                name="command_not_found",
                is_dangerous=False,
                context={"exit_code": 127},
            )

        # 3. Repeated failure: 3 consecutive non-zero exits in current session
        if session_recent_commands and exit_code is not None and exit_code != 0:
            # Check previous 2 exits
            prev_failures = 0
            for prev in session_recent_commands[:2]:
                if prev.get("exit_code") is not None and prev["exit_code"] != 0:
                    prev_failures += 1
                else:
                    break
            if prev_failures >= 2:
                return TriggerResult(
                    triggered=True,
                    name="repeated_failure",
                    is_dangerous=False,
                    context={"consecutive_failures": prev_failures + 1},
                )

        # 4. Repetition: same command run 5+ times in a row, or 10+ times in session
        if session_recent_commands:
            # Consecutive streak
            streak = 1
            for prev in session_recent_commands:
                if prev.get("cmd_hash") == c_hash:
                    streak += 1
                else:
                    break
            if streak >= 5:
                return TriggerResult(
                    triggered=True,
                    name="repetition",
                    is_dangerous=False,
                    context={"streak": streak},
                )

            # Session frequency
            session_count = (
                sum(1 for p in session_recent_commands if p.get("cmd_hash") == c_hash) + 1
            )
            if session_count >= 10:
                return TriggerResult(
                    triggered=True,
                    name="repetition",
                    is_dangerous=False,
                    context={"session_count": session_count},
                )

        # 5. Session end
        if cmd_clean in ("exit", "logout"):
            return TriggerResult(
                triggered=True,
                name="session_end",
                is_dangerous=False,
                context={"command": cmd_clean},
            )

        # 6. Graveyard recall: command seen before, but last seen >= 30 days ago
        prev_run_ts = self.graveyard.get_last_run_timestamp(c_hash)
        if prev_run_ts is not None:
            days_ago = (current_ts - prev_run_ts) / 86400
            if days_ago >= 30:
                return TriggerResult(
                    triggered=True,
                    name="graveyard_recall",
                    is_dangerous=False,
                    context={"days_dormant": int(days_ago)},
                )

        # 7. Returning: first command after 12+ hours of inactivity
        last_global_ts = self.graveyard.get_last_haunt_timestamp(exclude_session=session_id)
        if (
            (not session_recent_commands or len(session_recent_commands) == 0)
            and last_global_ts is not None
            and (current_ts - last_global_ts) >= (12 * 3600)
        ):
            return TriggerResult(
                triggered=True,
                name="returning",
                is_dangerous=False,
                context={"hours_away": round((current_ts - last_global_ts) / 3600, 1)},
            )

        # 8. Late night: 00:00 to 04:00 local time
        if 0 <= dt.hour < 4:
            return TriggerResult(
                triggered=True,
                name="late_night",
                is_dangerous=False,
                context={"hour": dt.hour, "minute": dt.minute},
            )

        # 9. Ambient low-probability whisper
        if random.random() < self.ambient_probability:
            return TriggerResult(
                triggered=True,
                name="ambient",
                is_dangerous=False,
                context={},
            )

        return TriggerResult(triggered=False)
