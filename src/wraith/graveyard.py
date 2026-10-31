"""SQLite storage layer for haunts and whispers (The Graveyard)."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wraith.config import get_graveyard_db_path


def hash_command(cmd: str) -> str:
    """Return SHA-256 hex digest of command string."""
    return hashlib.sha256(cmd.strip().encode("utf-8")).hexdigest()


@dataclass
class HauntRecord:
    id: int | None
    ts: int
    session: str | None
    cmd_redacted: str
    cmd_head: str | None
    cmd_hash: str
    exit_code: int | None
    duration_ms: int | None
    cwd_base: str | None
    danger_flag: int = 0


@dataclass
class WhisperRecord:
    id: int | None
    haunt_id: int | None
    ts: int
    trigger: str
    persona: str
    text: str
    source: str  # "model" | "crypt"


class Graveyard:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_graveyard_db_path()
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Set file permissions if on POSIX
        if not self.db_path.exists() and hasattr(os, "chmod") and os.name != "nt":
            self.db_path.touch(mode=0o600)

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS haunts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    session TEXT,
                    cmd_redacted TEXT NOT NULL,
                    cmd_head TEXT,
                    cmd_hash TEXT NOT NULL,
                    exit_code INTEGER,
                    duration_ms INTEGER,
                    cwd_base TEXT,
                    danger_flag INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS whispers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    haunt_id INTEGER REFERENCES haunts(id) ON DELETE CASCADE,
                    ts INTEGER NOT NULL,
                    trigger TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_haunts_hash ON haunts(cmd_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_haunts_ts ON haunts(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_haunts_head ON haunts(cmd_head)")
            conn.commit()

        if hasattr(os, "chmod") and os.name != "nt":
            try:
                os.chmod(self.db_path, 0o600)
            except OSError:
                pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def record_haunt(
        self,
        cmd_redacted: str,
        exit_code: int | None = None,
        duration_ms: int | None = None,
        cwd_base: str | None = None,
        session: str | None = None,
        danger_flag: int = 0,
        ts: int | None = None,
    ) -> int:
        timestamp = ts if ts is not None else int(time.time())
        tokens = cmd_redacted.strip().split()
        cmd_head = tokens[0] if tokens else None
        c_hash = hash_command(cmd_redacted)

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO haunts (ts, session, cmd_redacted, cmd_head, cmd_hash, exit_code, duration_ms, cwd_base, danger_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    session,
                    cmd_redacted,
                    cmd_head,
                    c_hash,
                    exit_code,
                    duration_ms,
                    cwd_base,
                    danger_flag,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def record_whisper(
        self,
        haunt_id: int | None,
        trigger: str,
        persona: str,
        text: str,
        source: str = "model",
        ts: int | None = None,
    ) -> int:
        timestamp = ts if ts is not None else int(time.time())
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO whispers (haunt_id, ts, trigger, persona, text, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (haunt_id, timestamp, trigger, persona, text, source),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_haunt_count(self, cmd_hash: str) -> int:
        """Get total number of times this exact command has been recorded."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM haunts WHERE cmd_hash = ?", (cmd_hash,))
            row = cur.fetchone()
            return row[0] if row else 0

    def get_last_run_timestamp(self, cmd_hash: str, exclude_id: int | None = None) -> int | None:
        """Get the previous run timestamp of this command."""
        with self._connect() as conn:
            cur = conn.cursor()
            if exclude_id is not None:
                cur.execute(
                    "SELECT ts FROM haunts WHERE cmd_hash = ? AND id != ? ORDER BY ts DESC LIMIT 1",
                    (cmd_hash, exclude_id),
                )
            else:
                cur.execute(
                    "SELECT ts FROM haunts WHERE cmd_hash = ? ORDER BY ts DESC LIMIT 1",
                    (cmd_hash,),
                )
            row = cur.fetchone()
            return row[0] if row else None

    def get_recent_session_haunts(self, session: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM haunts WHERE session = ? ORDER BY id DESC LIMIT ?",
                (session, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_last_haunt_timestamp(self, exclude_session: str | None = None) -> int | None:
        """Get timestamp of most recent haunt before current session."""
        with self._connect() as conn:
            cur = conn.cursor()
            if exclude_session:
                cur.execute(
                    "SELECT ts FROM haunts WHERE session != ? ORDER BY ts DESC LIMIT 1",
                    (exclude_session,),
                )
            else:
                cur.execute("SELECT ts FROM haunts ORDER BY ts DESC LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else None

    def get_stats(self) -> dict[str, Any]:
        """Compute graveyard summary statistics."""
        with self._connect() as conn:
            cur = conn.cursor()

            # Total counts
            cur.execute("SELECT COUNT(*) FROM haunts")
            total_haunts = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM whispers")
            total_whispers = cur.fetchone()[0]

            # Top commands
            cur.execute(
                """
                SELECT cmd_redacted, COUNT(*) as cnt
                FROM haunts
                GROUP BY cmd_hash
                ORDER BY cnt DESC
                LIMIT 10
                """
            )
            top_commands = [
                {"command": row["cmd_redacted"], "count": row["cnt"]} for row in cur.fetchall()
            ]

            # Most dangerous commands
            cur.execute(
                """
                SELECT cmd_redacted, COUNT(*) as cnt
                FROM haunts
                WHERE danger_flag = 1
                GROUP BY cmd_hash
                ORDER BY cnt DESC
                LIMIT 5
                """
            )
            dangerous_commands = [
                {"command": row["cmd_redacted"], "count": row["cnt"]} for row in cur.fetchall()
            ]

            # Busiest hours
            cur.execute(
                """
                SELECT strftime('%H', datetime(ts, 'unixepoch', 'localtime')) as hr, COUNT(*) as cnt
                FROM haunts
                GROUP BY hr
                ORDER BY cnt DESC
                LIMIT 5
                """
            )
            busiest_hours = [{"hour": row["hr"], "count": row["cnt"]} for row in cur.fetchall()]

            # Longest silence (max gap between consecutive haunts in seconds)
            cur.execute("SELECT ts FROM haunts ORDER BY ts ASC")
            rows = [r[0] for r in cur.fetchall()]
            longest_silence_s = 0
            if len(rows) > 1:
                for i in range(1, len(rows)):
                    gap = rows[i] - rows[i - 1]
                    longest_silence_s = max(longest_silence_s, gap)

            # Failure streaks (max consecutive non-zero exits in history)
            cur.execute("SELECT exit_code FROM haunts ORDER BY id ASC")
            exit_codes = [r[0] for r in cur.fetchall()]
            max_failure_streak = 0
            current_streak = 0
            for code in exit_codes:
                if code is not None and code != 0:
                    current_streak += 1
                    max_failure_streak = max(max_failure_streak, current_streak)
                else:
                    current_streak = 0

            return {
                "total_haunts": total_haunts,
                "total_whispers": total_whispers,
                "top_commands": top_commands,
                "dangerous_commands": dangerous_commands,
                "busiest_hours": busiest_hours,
                "longest_silence_seconds": longest_silence_s,
                "max_failure_streak": max_failure_streak,
            }

    def get_retired_commands(
        self, days_threshold: int = 60, min_usage: int = 2
    ) -> list[dict[str, Any]]:
        """Find commands heavily used in the past but not run for >= days_threshold days."""
        cutoff_ts = int(time.time()) - (days_threshold * 86400)
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT cmd_redacted, cmd_head, COUNT(*) as cnt, MAX(ts) as last_ts, MIN(ts) as first_ts
                FROM haunts
                GROUP BY cmd_hash
                HAVING cnt >= ? AND last_ts < ?
                ORDER BY cnt DESC, last_ts ASC
                LIMIT 15
                """,
                (min_usage, cutoff_ts),
            )
            results = []
            for row in cur.fetchall():
                results.append(
                    {
                        "command": row["cmd_redacted"],
                        "cmd_head": row["cmd_head"],
                        "count": row["cnt"],
                        "last_ts": row["last_ts"],
                        "first_ts": row["first_ts"],
                        "days_dormant": int((time.time() - row["last_ts"]) / 86400),
                    }
                )
            return results

    def get_recent_haunts(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get latest redacted events for CLI or MCP."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, ts, session, cmd_redacted, cmd_head, exit_code, duration_ms, cwd_base, danger_flag
                FROM haunts
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    def forget(
        self,
        forget_all: bool = False,
        since_ts: int | None = None,
        pattern: str | None = None,
    ) -> int:
        """Immediately delete data matching criteria. Returns number of haunts deleted."""
        with self._connect() as conn:
            cur = conn.cursor()
            if forget_all:
                cur.execute("DELETE FROM whispers")
                cur.execute("DELETE FROM haunts")
                count = cur.rowcount
            elif since_ts is not None:
                cur.execute("DELETE FROM whispers WHERE ts >= ?", (since_ts,))
                cur.execute("DELETE FROM haunts WHERE ts >= ?", (since_ts,))
                count = cur.rowcount
            elif pattern is not None:
                cur.execute("SELECT id, cmd_redacted FROM haunts")
                import re

                rx = re.compile(pattern)
                ids_to_del = [r["id"] for r in cur.fetchall() if rx.search(r["cmd_redacted"])]
                if ids_to_del:
                    placeholders = ",".join("?" for _ in ids_to_del)
                    cur.execute(
                        f"DELETE FROM whispers WHERE haunt_id IN ({placeholders})", ids_to_del
                    )
                    cur.execute(f"DELETE FROM haunts WHERE id IN ({placeholders})", ids_to_del)
                    count = len(ids_to_del)
                else:
                    count = 0
            else:
                count = 0

            conn.commit()
            cur.execute("VACUUM")
            return count

    def export_json(self) -> dict[str, Any]:
        """Export graveyard haunts and whispers to a JSON-serializable dictionary."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM haunts ORDER BY id ASC")
            haunts = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM whispers ORDER BY id ASC")
            whispers = [dict(r) for r in cur.fetchall()]
            return {
                "exported_at": int(time.time()),
                "total_haunts": len(haunts),
                "total_whispers": len(whispers),
                "haunts": haunts,
                "whispers": whispers,
            }
