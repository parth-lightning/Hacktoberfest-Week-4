"""Tests for SQLite Graveyard layer (FR-22, FR-23, FR-24, FR-25, AC-8)."""

import time

import pytest

from wraith.graveyard import Graveyard, hash_command


@pytest.fixture
def graveyard(tmp_path):
    db_file = tmp_path / "graveyard.db"
    return Graveyard(db_path=db_file)


def test_record_haunt_and_counts(graveyard):
    cmd = "git status"
    c_hash = hash_command(cmd)

    assert graveyard.get_haunt_count(c_hash) == 0

    hid1 = graveyard.record_haunt(cmd_redacted=cmd, exit_code=0, session="s1", ts=1000)
    assert hid1 > 0
    assert graveyard.get_haunt_count(c_hash) == 1

    hid2 = graveyard.record_haunt(cmd_redacted=cmd, exit_code=0, session="s1", ts=2000)
    assert hid2 > hid1
    assert graveyard.get_haunt_count(c_hash) == 2


def test_record_whisper_and_stats(graveyard):
    hid = graveyard.record_haunt(
        cmd_redacted="rm -rf build",
        exit_code=0,
        session="s1",
        danger_flag=1,
        ts=1000,
    )
    wid = graveyard.record_whisper(
        haunt_id=hid,
        trigger="dangerous_command",
        persona="poltergeist",
        text="Another graveyard dug.",
        source="model",
        ts=1000,
    )
    assert wid > 0

    stats = graveyard.get_stats()
    assert stats["total_haunts"] == 1
    assert stats["total_whispers"] == 1
    assert len(stats["dangerous_commands"]) == 1
    assert stats["dangerous_commands"][0]["command"] == "rm -rf build"


def test_failure_streak_stats(graveyard):
    # 3 failures in a row
    graveyard.record_haunt("cmd1", exit_code=1, ts=100)
    graveyard.record_haunt("cmd2", exit_code=2, ts=200)
    graveyard.record_haunt("cmd3", exit_code=1, ts=300)
    graveyard.record_haunt("cmd4", exit_code=0, ts=400)

    stats = graveyard.get_stats()
    assert stats["max_failure_streak"] == 3


def test_retired_commands_ofrenda(graveyard):
    now = int(time.time())
    old_ts = now - (70 * 86400)  # 70 days ago

    # Old retired command used 3 times
    graveyard.record_haunt("vim old_notes.txt", ts=old_ts - 200)
    graveyard.record_haunt("vim old_notes.txt", ts=old_ts - 100)
    graveyard.record_haunt("vim old_notes.txt", ts=old_ts)

    # Recent command
    graveyard.record_haunt("nvim new_notes.txt", ts=now - 1000)

    retired = graveyard.get_retired_commands(days_threshold=60, min_usage=2)
    assert len(retired) == 1
    assert retired[0]["command"] == "vim old_notes.txt"
    assert retired[0]["days_dormant"] >= 69


def test_forget_all(graveyard):
    hid = graveyard.record_haunt("echo test", ts=1000)
    graveyard.record_whisper(hid, "ambient", "poltergeist", "hello", ts=1000)

    stats = graveyard.get_stats()
    assert stats["total_haunts"] == 1

    deleted = graveyard.forget(forget_all=True)
    assert deleted >= 1

    stats_after = graveyard.get_stats()
    assert stats_after["total_haunts"] == 0
    assert stats_after["total_whispers"] == 0


def test_forget_pattern(graveyard):
    graveyard.record_haunt("aws s3 ls", ts=1000)
    graveyard.record_haunt("git status", ts=2000)

    deleted = graveyard.forget(pattern=r"aws\s+s3")
    assert deleted == 1

    stats = graveyard.get_stats()
    assert stats["total_haunts"] == 1
    assert stats["top_commands"][0]["command"] == "git status"


def test_export_json(graveyard):
    graveyard.record_haunt("cargo build", ts=1000)
    data = graveyard.export_json()
    assert "haunts" in data
    assert "whispers" in data
    assert len(data["haunts"]) == 1
    assert data["haunts"][0]["cmd_redacted"] == "cargo build"
