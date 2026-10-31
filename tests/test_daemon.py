"""Tests for Daemon event processing and socket communication (FR-3, FR-4)."""

import pytest

from wraith.config import WraithConfig
from wraith.daemon import WraithDaemon
from wraith.graveyard import Graveyard
from wraith.sender import send_event


@pytest.fixture
def test_daemon(tmp_path):
    cfg = WraithConfig()
    cfg.privacy.store_commands = True
    cfg.whisper.ambient_probability = 1.0  # Force trigger for testing
    daemon = WraithDaemon(config=cfg)
    daemon.graveyard = Graveyard(db_path=tmp_path / "gy.db")
    daemon.sessions_dir = tmp_path / "sessions"
    daemon.sessions_dir.mkdir(parents=True, exist_ok=True)
    return daemon


@pytest.mark.asyncio
async def test_daemon_handle_event_creates_whisper(test_daemon):
    event = {
        "v": 1,
        "type": "event",
        "cmd": "rm -rf build --token secret123",
        "exit": 0,
        "cwd": "/home/user/project",
        "ts": 1760000000,
        "dur_ms": 150,
        "session": "sess_abc",
    }

    await test_daemon.handle_event(event)

    # Verify command was redacted in graveyard
    stats = test_daemon.graveyard.get_stats()
    assert stats["total_haunts"] == 1
    haunt = test_daemon.graveyard.get_recent_haunts(1)[0]
    assert "secret123" not in haunt["cmd_redacted"]
    assert "<redacted>" in haunt["cmd_redacted"]
    assert haunt["danger_flag"] == 1

    # Verify whisper file written
    whisper_file = test_daemon.sessions_dir / "sess_abc.whisper"
    assert whisper_file.is_file()
    content = whisper_file.read_text(encoding="utf-8")
    assert len(content) > 5


@pytest.mark.asyncio
async def test_daemon_handle_possess_rewrite(test_daemon):
    req = {
        "error": "ModuleNotFoundError: No module named 'flask'",
        "cmd": "python app.py",
    }
    rewrite = await test_daemon.handle_possess_rewrite(req)
    assert isinstance(rewrite, str)
    assert "flask" in rewrite or "ModuleNotFoundError" in rewrite


def test_sender_fails_silently_when_daemon_down(tmp_path, monkeypatch):
    # Point socket to non-existent location
    monkeypatch.setattr("wraith.sender.get_socket_path", lambda: tmp_path / "nonexistent.sock")
    # Should not raise any exception
    send_event("ls -la", 0, "/tmp", 1000, 10, "sess1")
