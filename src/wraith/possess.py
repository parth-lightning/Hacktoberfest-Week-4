"""Possessed Mode: PTY proxy for transparent command execution and error rewriting."""

from __future__ import annotations

import json
import os
import re
import select
import signal
import socket
import sys
from pathlib import Path

from wraith.config import WraithConfig, get_cache_dir, get_socket_path
from wraith.crypt import get_crypt_error_rewrite
from wraith.models import get_model_client
from wraith.personas import load_persona
from wraith.prompts import build_rewrite_messages
from wraith.validate import extract_key_tokens, validate_rewrite

# Alternate screen buffer escape sequences (used by vim, less, top, etc.)
ALT_SCREEN_ENTER = re.compile(r"\x1B\[\?(?:1049|47|1047)h")
ALT_SCREEN_EXIT = re.compile(r"\x1B\[\?(?:1049|47|1047)l")

# Error indicators in stderr / stdout
ERROR_PATTERNS = re.compile(
    r"(?i)\b(error|fatal:|exception|traceback|no such file|permission denied|command not found|modulenotfounderror|syntaxerror|nameerror|typeerror|valueerror|failed|seg(?:mentation)? fault)\b"
)


def get_last_error_file() -> Path:
    return get_cache_dir() / "last_error.txt"


def save_last_error(error_text: str) -> None:
    f = get_last_error_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        f.write_text(error_text, encoding="utf-8")
    except Exception:
        pass


def get_last_error() -> str:
    f = get_last_error_file()
    if f.is_file():
        try:
            return f.read_text(encoding="utf-8")
        except Exception:
            return "No previous error recorded."
    return "No previous error recorded."


async def request_daemon_rewrite(
    error_text: str, cmd: str = "", config: WraithConfig | None = None
) -> str:
    """Request possessed rewrite from the daemon or compute directly via fallback."""
    cfg = config or WraithConfig.load()
    key_tokens = extract_key_tokens(error_text, max_tokens=5)
    persona = load_persona(cfg.whisper.persona)

    # 1. Try daemon socket
    sock_path = get_socket_path()
    try:
        if hasattr(socket, "AF_UNIX") and sock_path.exists():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(cfg.model.rewrite_timeout + 1.0)
            try:
                s.connect(str(sock_path))
                req = (
                    json.dumps({"v": 1, "type": "possess", "error": error_text, "cmd": cmd}) + "\n"
                )
                s.sendall(req.encode("utf-8"))
                resp_line = s.recv(4096).decode("utf-8")
                resp_json = json.loads(resp_line)
                if resp_json.get("status") == "ok" and resp_json.get("rewrite"):
                    return resp_json["rewrite"]
            finally:
                s.close()
    except Exception:
        pass

    # 2. Try direct model query if daemon didn't answer
    try:
        model_client = get_model_client(cfg.model)
        messages = build_rewrite_messages(persona, error_text, key_tokens)
        for _ in range(2):
            raw = await model_client.chat(
                messages,
                max_tokens=120,
                temperature=persona.temperature,
                timeout=cfg.model.rewrite_timeout,
            )
            valid, cleaned = validate_rewrite(raw, key_tokens)
            if valid:
                return cleaned
    except Exception:
        pass

    # 3. Deterministic Crypt rewrite
    return get_crypt_error_rewrite(cfg.whisper.persona, error_text, key_tokens)


def run_possessed_pty(replace: bool = False, config: WraithConfig | None = None) -> None:
    """Run interactive shell inside PTY proxy."""
    if os.name == "nt":
        # Windows native doesn't support unix pty module
        print("Wraith Possessed Mode requires a POSIX environment (Linux, macOS, or WSL).")
        print("Please run inside WSL or on macOS/Linux.")
        return

    try:
        import pty
        import termios
        import tty
    except ImportError:
        print("PTY modules are not available in this environment.")
        return

    cfg = config or WraithConfig.load()
    shell = os.environ.get("SHELL", "/bin/sh")

    pid, master_fd = pty.fork()

    if pid == 0:
        # Child process: run shell
        os.environ["WRAITH_POSSESSED"] = "1"
        os.execlp(shell, shell)
        sys.exit(0)

    # Parent process: transparent proxy
    old_stdin_attr = termios.tcgetattr(sys.stdin)

    # Set up SIGWINCH forwarding
    def handle_sigwinch(signum, frame):
        import fcntl
        import struct
        import termios

        try:
            s = struct.pack("HHHH", 0, 0, 0, 0)
            t = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, t)
        except Exception:
            pass

    signal.signal(signal.SIGWINCH, handle_sigwinch)
    handle_sigwinch(None, None)

    in_alt_screen = False
    output_buffer = []

    try:
        tty.setraw(sys.stdin.fileno())

        while True:
            r, _, _ = select.select([sys.stdin, master_fd], [], [])

            if sys.stdin in r:
                data = os.read(sys.stdin.fileno(), 1024)
                if not data:
                    break
                os.write(master_fd, data)

            if master_fd in r:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break

                text = data.decode("utf-8", errors="replace")

                # Detect alternate screen buffer transitions
                if ALT_SCREEN_ENTER.search(text):
                    in_alt_screen = True
                if ALT_SCREEN_EXIT.search(text):
                    in_alt_screen = False

                # If in alternate screen (vim, htop), forward without processing
                if in_alt_screen:
                    os.write(sys.stdout.fileno(), data)
                    continue

                output_buffer.append(text)
                if len(output_buffer) > 50:
                    output_buffer.pop(0)

                # Check for error patterns if output contains newline
                if "\n" in text and ERROR_PATTERNS.search(text):
                    recent_text = "".join(output_buffer[-30:])
                    error_lines = [
                        line for line in recent_text.splitlines() if ERROR_PATTERNS.search(line)
                    ]
                    if error_lines:
                        full_error = "\n".join(error_lines[-10:])
                        save_last_error(full_error)

                        # Check if rewrite should be displayed
                        glyph = load_persona(cfg.whisper.persona).ghost_glyph
                        import asyncio

                        rewrite = asyncio.run(request_daemon_rewrite(full_error, config=cfg))

                        if replace:
                            # In replace mode, overwrite terminal line with rewrite
                            os.write(sys.stdout.fileno(), b"\r\x1b[K")
                            if os.environ.get("NO_COLOR"):
                                rewrite_banner = f"\n~ [possessed] {rewrite}\n"
                            else:
                                rewrite_banner = f"\n\033[1;35m{glyph} [possessed]\033[0m \033[3;35m{rewrite}\033[0m\n"
                            os.write(sys.stdout.fileno(), rewrite_banner.encode("utf-8"))
                        else:
                            # Annotate mode: original output printed untouched, followed by possessed rewrite
                            os.write(sys.stdout.fileno(), data)
                            if os.environ.get("NO_COLOR"):
                                rewrite_banner = f"\n~ [possessed] {rewrite}\n"
                            else:
                                rewrite_banner = f"\n\033[1;35m{glyph} [possessed]\033[0m \033[3;35m{rewrite}\033[0m\n"
                            os.write(sys.stdout.fileno(), rewrite_banner.encode("utf-8"))
                        continue

                os.write(sys.stdout.fileno(), data)

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_stdin_attr)
        os.close(master_fd)
        try:
            os.waitpid(pid, 0)
        except Exception:
            pass
