"""Fast, silent event dispatcher for shell hooks.

Connects to the daemon socket (or port file) and writes the event JSON line.
Fails completely silently if the daemon is not running.
"""

from __future__ import annotations

import json
import socket
import sys

from wraith.config import get_socket_path


def send_event(
    cmd: str,
    exit_code: int | None,
    cwd: str,
    ts: int,
    dur_ms: int,
    session: str,
) -> None:
    socket_path = get_socket_path()
    payload = (
        json.dumps(
            {
                "v": 1,
                "type": "event",
                "cmd": cmd,
                "exit": exit_code,
                "cwd": cwd,
                "ts": ts,
                "dur_ms": dur_ms,
                "session": session,
            }
        )
        + "\n"
    )

    try:
        if hasattr(socket, "AF_UNIX") and socket_path.exists():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.1)  # fast 100ms timeout
            try:
                s.connect(str(socket_path))
                s.sendall(payload.encode("utf-8"))
            finally:
                s.close()
        else:
            # Check port file for loopback TCP fallback
            port_file = socket_path.with_suffix(".port")
            if port_file.exists():
                port_str = port_file.read_text(encoding="utf-8").strip()
                if port_str.isdigit():
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.1)
                    try:
                        s.connect(("127.0.0.1", int(port_str)))
                        s.sendall(payload.encode("utf-8"))
                    finally:
                        s.close()
    except Exception:
        # Must fail silently
        pass


def main() -> None:
    if len(sys.argv) < 7:
        sys.exit(0)

    cmd = sys.argv[1]
    try:
        exit_code = int(sys.argv[2])
    except ValueError:
        exit_code = 0
    cwd = sys.argv[3]
    try:
        ts = int(sys.argv[4])
    except ValueError:
        ts = 0
    try:
        dur_ms = int(sys.argv[5])
    except ValueError:
        dur_ms = 0
    session = sys.argv[6]

    send_event(cmd, exit_code, cwd, ts, dur_ms, session)


if __name__ == "__main__":
    main()
