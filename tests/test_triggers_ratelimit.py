"""Tests for Trigger Engine and Rate Limiter (FR-7, FR-8)."""

import pytest

from wraith.graveyard import Graveyard, hash_command
from wraith.ratelimit import RateLimiter
from wraith.triggers import TriggerEngine


@pytest.fixture
def temp_graveyard(tmp_path):
    db_file = tmp_path / "test_gy.db"
    return Graveyard(db_path=db_file)


# 1. Dangerous command trigger
def test_trigger_dangerous_command(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    for cmd in [
        "rm -rf /tmp/test",
        "sudo rm -r /var/cache",
        "git push --force origin main",
        "git push -f",
        "git reset --hard HEAD~1",
        "chmod 777 run.sh",
        "chmod -R 777 /app",
        "dd if=/dev/zero of=/dev/sda",
        "kill -9 1234",
        "DROP TABLE users;",
        "mkfs.ext4 /dev/sdb1",
    ]:
        res = engine.evaluate(cmd, exit_code=0, session_id="s1")
        assert res.triggered is True
        assert res.name == "dangerous_command"
        assert res.is_dangerous is True


def test_trigger_dangerous_negative(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    for cmd in ["ls -la", "git status", "rm file.txt", "git push origin main"]:
        res = engine.evaluate(cmd, exit_code=0, session_id="s1")
        assert res.name != "dangerous_command"


# 2. Command not found (127)
def test_trigger_command_not_found(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    res = engine.evaluate("sl", exit_code=127, session_id="s1")
    assert res.triggered is True
    assert res.name == "command_not_found"


# 3. Repeated failure (3 consecutive non-zero exits)
def test_trigger_repeated_failure(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    history = [
        {"cmd_hash": "a", "exit_code": 1},
        {"cmd_hash": "b", "exit_code": 2},
    ]
    res = engine.evaluate("pytest", exit_code=1, session_id="s1", session_recent_commands=history)
    assert res.triggered is True
    assert res.name == "repeated_failure"


def test_trigger_repeated_failure_negative(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    # Only 1 previous failure, not 2
    history = [
        {"cmd_hash": "a", "exit_code": 1},
        {"cmd_hash": "b", "exit_code": 0},
    ]
    res = engine.evaluate("pytest", exit_code=1, session_id="s1", session_recent_commands=history)
    assert res.name != "repeated_failure"


# 4. Repetition (5 in a row or 10 in session)
def test_trigger_repetition_streak(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    cmd = "make test"
    c_hash = hash_command(cmd)
    history = [{"cmd_hash": c_hash, "exit_code": 0} for _ in range(4)]
    res = engine.evaluate(cmd, exit_code=0, session_id="s1", session_recent_commands=history)
    assert res.triggered is True
    assert res.name == "repetition"


# 5. Session end
def test_trigger_session_end(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    for cmd in ["exit", "logout"]:
        res = engine.evaluate(cmd, exit_code=0, session_id="s1")
        assert res.triggered is True
        assert res.name == "session_end"


# 6. Returning (first command after 12+ hours of silence)
def test_trigger_returning(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    now = 1760000000
    temp_graveyard.record_haunt("ls", ts=now - (13 * 3600), session="s0")
    res = engine.evaluate("ls", exit_code=0, session_id="s1", session_recent_commands=[], now=now)
    assert res.triggered is True
    assert res.name == "returning"


# 7. Graveyard recall (command seen after 30+ days)
def test_trigger_graveyard_recall(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    now = 1760000000
    cmd = "docker compose up -d"
    temp_graveyard.record_haunt(cmd, ts=now - (35 * 86400), session="s0")
    res = engine.evaluate(cmd, exit_code=0, session_id="s1", session_recent_commands=[], now=now)
    assert res.triggered is True
    assert res.name == "graveyard_recall"


# 8. Late night (00:00 - 04:00)
def test_trigger_late_night(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=0.0)
    # 02:30 AM local time
    # Construct timestamp with hour 2
    import datetime

    now_dt = datetime.datetime.now().replace(hour=2, minute=30, second=0)
    now_ts = now_dt.timestamp()

    res = engine.evaluate(
        "npm run dev", exit_code=0, session_id="s1", session_recent_commands=[], now=now_ts
    )
    assert res.triggered is True
    assert res.name == "late_night"


# 9. Ambient probability
def test_trigger_ambient(temp_graveyard):
    engine = TriggerEngine(temp_graveyard, ambient_probability=1.0)
    import datetime

    # Use noon so late_night doesn't fire
    now_dt = datetime.datetime.now().replace(hour=12, minute=0, second=0)
    res = engine.evaluate(
        "echo hello",
        exit_code=0,
        session_id="s1",
        session_recent_commands=[],
        now=now_dt.timestamp(),
    )
    assert res.triggered is True
    assert res.name == "ambient"


# Rate Limiter Tests
def test_rate_limiter_cooldown():
    limiter = RateLimiter(cooldown_seconds=20, max_per_hour=12)
    t0 = 1000.0

    assert limiter.can_whisper(is_dangerous=False, now=t0) is True
    limiter.record_whisper(now=t0)

    # 10s later -> blocked by cooldown
    assert limiter.can_whisper(is_dangerous=False, now=t0 + 10) is False

    # 21s later -> allowed
    assert limiter.can_whisper(is_dangerous=False, now=t0 + 21) is True


def test_rate_limiter_dangerous_bypasses_cooldown():
    limiter = RateLimiter(cooldown_seconds=20, max_per_hour=12)
    t0 = 1000.0
    limiter.record_whisper(now=t0)

    # 5s later: normal command blocked, dangerous command allowed
    assert limiter.can_whisper(is_dangerous=False, now=t0 + 5) is False
    assert limiter.can_whisper(is_dangerous=True, now=t0 + 5) is True


def test_rate_limiter_hourly_cap():
    limiter = RateLimiter(cooldown_seconds=1, max_per_hour=3)
    t0 = 1000.0

    for i in range(3):
        t = t0 + (i * 2)
        assert limiter.can_whisper(is_dangerous=False, now=t) is True
        limiter.record_whisper(now=t)

    # 4th whisper within the same hour is blocked, even if dangerous!
    t_blocked = t0 + 10
    assert limiter.can_whisper(is_dangerous=False, now=t_blocked) is False
    assert limiter.can_whisper(is_dangerous=True, now=t_blocked) is False

    # After 1 hour (3601s), cap resets
    t_after = t0 + 3601
    assert limiter.can_whisper(is_dangerous=False, now=t_after) is True
