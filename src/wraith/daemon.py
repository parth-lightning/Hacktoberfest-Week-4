"""Wraith background daemon (wraithd).

Asynchronous socket server that receives shell telemetry events,
evaluates triggers and rate limits, queries local models,
falls back gracefully to the crypt, and stores history in the graveyard.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from wraith.config import WraithConfig, get_log_file_path, get_sessions_dir, get_socket_path
from wraith.crypt import get_crypt_error_rewrite, get_crypt_whisper
from wraith.graveyard import Graveyard, hash_command
from wraith.models import get_model_client
from wraith.personas import load_persona
from wraith.prompts import build_rewrite_messages, build_whisper_messages
from wraith.ratelimit import RateLimiter
from wraith.redact import redact
from wraith.triggers import TriggerEngine, is_dangerous_command
from wraith.validate import extract_key_tokens, validate_rewrite, validate_whisper

logger = logging.getLogger("wraith")


def setup_daemon_logging() -> None:
    log_path = get_log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        str(log_path),
        maxBytes=1_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class WhisperCache:
    def __init__(self, ttl_seconds: float = 600.0) -> None:
        self.ttl = ttl_seconds
        self._cache: dict[tuple[str, str, str], tuple[float, str]] = {}

    def get(self, trigger: str, cmd_hash: str, persona: str) -> str | None:
        key = (trigger, cmd_hash, persona)
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < self.ttl:
                return val
            del self._cache[key]
        return None

    def set(self, trigger: str, cmd_hash: str, persona: str, text: str) -> None:
        self._cache[(trigger, cmd_hash, persona)] = (time.time(), text)


class WraithDaemon:
    def __init__(self, config: WraithConfig | None = None) -> None:
        self.config = config or WraithConfig.load()
        self.graveyard = Graveyard()
        self.rate_limiter = RateLimiter(
            cooldown_seconds=self.config.whisper.cooldown_seconds,
            max_per_hour=self.config.whisper.max_per_hour,
        )
        self.trigger_engine = TriggerEngine(
            graveyard=self.graveyard,
            ambient_probability=self.config.whisper.ambient_probability,
        )
        self.cache = WhisperCache(ttl_seconds=600.0)
        self.socket_path = get_socket_path()
        self.sessions_dir = get_sessions_dir()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.server: asyncio.Server | None = None
        self._running = False

    async def handle_event(self, data: dict[str, Any]) -> None:
        """Process incoming shell command event."""
        cmd_raw = data.get("cmd", "")
        exit_code = data.get("exit")
        cwd_raw = data.get("cwd", "")
        session_id = data.get("session") or "default"
        dur_ms = data.get("dur_ms")
        ts = data.get("ts") or int(time.time())

        # 1. Sanitize & redact
        cmd_redacted = redact(cmd_raw, self.config.privacy.redact_patterns)
        cwd_base = Path(cwd_raw).name if cwd_raw else ""
        c_hash = hash_command(cmd_redacted)
        is_danger = 1 if is_dangerous_command(cmd_redacted) else 0

        # 2. Record haunt in graveyard
        haunt_id: int | None = None
        if self.config.privacy.store_commands:
            haunt_id = self.graveyard.record_haunt(
                cmd_redacted=cmd_redacted,
                exit_code=exit_code,
                duration_ms=dur_ms,
                cwd_base=cwd_base,
                session=session_id,
                danger_flag=is_danger,
                ts=ts,
            )

        # 3. Evaluate triggers
        recent_session_haunts = self.graveyard.get_recent_session_haunts(session_id, limit=10)
        trigger_res = self.trigger_engine.evaluate(
            cmd=cmd_redacted,
            exit_code=exit_code,
            session_id=session_id,
            session_recent_commands=recent_session_haunts,
            now=ts,
        )

        if not trigger_res.triggered or not trigger_res.name:
            return

        # 4. Rate limiting check
        if not self.rate_limiter.can_whisper(is_dangerous=trigger_res.is_dangerous, now=ts):
            logger.info("Triggered '%s' but rate limited", trigger_res.name)
            return

        # 5. Whisper generation (cached -> model -> crypt fallback)
        persona_name = self.config.whisper.persona
        persona = load_persona(persona_name)
        cached_whisper = self.cache.get(trigger_res.name, c_hash, persona_name)

        whisper_text: str | None = cached_whisper
        source = "cache"

        if not whisper_text:
            # Query local model
            prior_runs = self.graveyard.get_haunt_count(c_hash)
            event_ctx = {
                "trigger": trigger_res.name,
                "cmd_redacted": cmd_redacted,
                "exit_code": exit_code,
                "prior_runs": prior_runs,
                "local_time": time.strftime("%H:%M", time.localtime(ts)),
                "cwd_base": cwd_base,
            }
            messages = build_whisper_messages(persona, event_ctx)

            try:
                model_client = get_model_client(self.config.model)
                raw_response = await model_client.chat(
                    messages=messages,
                    max_tokens=60,
                    temperature=persona.temperature,
                    timeout=self.config.model.whisper_timeout,
                )
                valid, cleaned = validate_whisper(raw_response)
                if valid:
                    whisper_text = cleaned
                    source = "model"
                else:
                    logger.warning("Model response failed validation: %r", raw_response)
            except Exception as e:
                logger.info("Model unavailable or timed out (%s), using crypt fallback", e)

            # Crypt fallback
            if not whisper_text:
                whisper_text = get_crypt_whisper(persona_name, trigger_res.name)
                source = "crypt"

            # Cache the whisper
            self.cache.set(trigger_res.name, c_hash, persona_name, whisper_text)

        # 6. Record whisper in Graveyard
        if haunt_id is not None:
            self.graveyard.record_whisper(
                haunt_id=haunt_id,
                trigger=trigger_res.name,
                persona=persona_name,
                text=whisper_text,
                source=source,
                ts=ts,
            )

        self.rate_limiter.record_whisper(now=ts)

        # 7. Write formatted whisper to session file for the shell hook prompt
        glyph = persona.ghost_glyph
        # Check NO_COLOR or ASCII fallback
        if os.environ.get("NO_COLOR"):
            formatted_line = f"~ {whisper_text}\n"
        else:
            # Dim & Italic ANSI: \033[2;3m
            formatted_line = f"\033[2;3m{glyph} {whisper_text}\033[0m\n"

        session_file = self.sessions_dir / f"{session_id}.whisper"
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                f.write(formatted_line)
        except Exception as e:
            logger.error("Failed to write whisper file %s: %s", session_file, e)

    async def handle_possess_rewrite(self, data: dict[str, Any]) -> str:
        """Process possessed error rewriting request."""
        raw_error = data.get("error", "")
        persona_name = self.config.whisper.persona
        persona = load_persona(persona_name)

        key_tokens = extract_key_tokens(raw_error, max_tokens=5)

        # Attempt 1: Call Model
        model_client = get_model_client(self.config.model)
        messages = build_rewrite_messages(persona, raw_error, key_tokens)

        for attempt in range(2):  # Try model once, retry once if fact preservation fails
            try:
                raw_response = await model_client.chat(
                    messages=messages,
                    max_tokens=120,
                    temperature=persona.temperature,
                    timeout=self.config.model.rewrite_timeout,
                )
                valid, cleaned = validate_rewrite(raw_response, key_tokens)
                if valid:
                    return cleaned
                logger.warning(
                    "Possessed rewrite attempt %d failed validation: %r", attempt + 1, raw_response
                )
            except Exception as e:
                logger.info("Possessed model query failed (%s)", e)
                break

        # Fallback: Deterministic crypt rewrite template
        return get_crypt_error_rewrite(persona_name, raw_error, key_tokens)

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                raw_text = line.decode("utf-8").strip()
                if not raw_text:
                    continue
                try:
                    msg = json.loads(raw_text)
                except Exception:
                    continue

                msg_type = msg.get("type", "event")
                if msg_type == "event":
                    await self.handle_event(msg)
                elif msg_type == "possess":
                    rewrite = await self.handle_possess_rewrite(msg)
                    resp = json.dumps({"v": 1, "status": "ok", "rewrite": rewrite}) + "\n"
                    writer.write(resp.encode("utf-8"))
                    await writer.drain()
                elif msg_type == "ping":
                    resp = json.dumps({"v": 1, "status": "pong"}) + "\n"
                    writer.write(resp.encode("utf-8"))
                    await writer.drain()
        except Exception as e:
            logger.error("Client handling error: %s", e)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self) -> None:
        setup_daemon_logging()
        self._running = True
        logger.info("Starting wraithd...")

        has_unix = hasattr(socket, "AF_UNIX")
        if has_unix:
            self.socket_path.parent.mkdir(parents=True, exist_ok=True)
            if self.socket_path.exists():
                try:
                    self.socket_path.unlink()
                except OSError:
                    pass

            self.server = await asyncio.start_unix_server(
                self.handle_client, path=str(self.socket_path)
            )
            if hasattr(os, "chmod") and os.name != "nt":
                try:
                    os.chmod(self.socket_path, 0o600)
                except OSError:
                    pass
            logger.info("wraithd listening on Unix domain socket: %s", self.socket_path)
        else:
            # Fallback to loopback TCP server on systems without AF_UNIX
            self.server = await asyncio.start_server(self.handle_client, host="127.0.0.1", port=0)
            port = self.server.sockets[0].getsockname()[1]
            port_file = self.socket_path.with_suffix(".port")
            port_file.parent.mkdir(parents=True, exist_ok=True)
            with open(port_file, "w", encoding="utf-8") as f:
                f.write(str(port))
            logger.info(
                "wraithd listening on loopback TCP port %d (written to %s)", port, port_file
            )

        async with self.server:
            await self.server.serve_forever()

    def stop(self) -> None:
        self._running = False
        if self.server:
            self.server.close()
        if hasattr(socket, "AF_UNIX") and self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass


def main() -> None:
    daemon = WraithDaemon()
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        logger.info("wraithd stopped by user.")


if __name__ == "__main__":
    main()
