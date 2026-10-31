# Wraith Architecture & Technical Design

Wraith combines lightweight asynchronous shell hooks, an isolated local background daemon (`wraithd`), an in-memory redactor, a local SQLite store ("The Graveyard"), and local open-weight language models served through Ollama or OpenAI-compatible backends.

---

## High-Level Architecture Diagram

```
+-------------------------------------------------------------+
|                       DEVELOPER SHELL                       |
|  (zsh / bash)                                               |
|                                                             |
|   Prompt Hook (precmd / PROMPT_COMMAND)                     |
|     |-- Reads pending ~/.cache/wraith/sessions/<id>.whisper |
|     '-- Fires background event asynchronously               |
+-------------------------------------------------------------+
                               |
                   JSON over Domain Socket
                     (sub-10ms overhead)
                               v
+-------------------------------------------------------------+
|                       wraithd (Daemon)                      |
|                                                             |
|   1. Redaction Engine (masks credentials, keys, tokens)     |
|   2. Graveyard SQLite Layer (stores haunt event)            |
|   3. Trigger Engine (9 trigger rules)                       |
|   4. Rate Limiter (cooldown + hourly cap)                   |
|   5. Whisper Cache (10 min TTL)                             |
|   6. Prompt Builder & Persona Loader                        |
|   7. Local Model Client (Ollama / OpenAI-compatible)        |
|   8. Output Validator & Fact Preservation Checker           |
|   9. The Crypt (Offline fallback whispers & templates)      |
|  10. Writes formatted whisper to session file               |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                     POSSESSED MODE (PTY)                    |
|  wraith possess                                             |
|                                                             |
|   1. Spawns $SHELL under Python PTY proxy                   |
|   2. Intercepts terminal output stream                      |
|   3. Bypasses full-screen interactive apps (vim, htop)      |
|   4. Detects error blocks & tracebacks                      |
|   5. Preserves key facts (files, error classes, lines)      |
|   6. Annotates beneath original error (or --replace)        |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                        CLI & TOOLS                          |
|                                                             |
|   • wraith init / setup / doctor / on / off                 |
|   • wraith persona list / use / new                         |
|   • wraith graveyard / ofrenda / bench                      |
|   • wraith forget / export / mcp                            |
+-------------------------------------------------------------+
```

---

## Core Components

### 1. Shell Hooks (`zsh.sh` & `bash.sh`)
- **Fire-and-forget:** Hooks send command telemetry (`cmd`, `exit_code`, `cwd`, `ts`, `dur_ms`, `session_id`) in a detached subshell. The prompt is never blocked waiting for socket replies or model inference.
- **Pending Whisper Buffer:** Before each prompt, the hook checks if a `.whisper` file exists for the session, prints it formatted with ANSI styling (or ASCII fallback if `NO_COLOR` is active), and clears the file. Added latency is `< 1 ms`.

### 2. The Daemon (`wraithd`)
- Runs in the background listening on `$XDG_RUNTIME_DIR/wraith.sock` (or local loopback TCP fallback).
- Evaluates triggers:
  1. `dangerous_command`
  2. `repetition`
  3. `repeated_failure`
  4. `command_not_found`
  5. `late_night`
  6. `returning`
  7. `graveyard_recall`
  8. `session_end`
  9. `ambient`
- Rate-limiting rules:
  - Default cooldown: 20 seconds.
  - Hourly cap: 12 whispers/hour.
  - Dangerous commands bypass cooldown, but remain bounded by the hourly cap.

### 3. Model Backends & Loopback Validator
- Connects to Ollama `/api/chat` or OpenAI-compatible endpoints (`llama-server`, LM Studio).
- Uses small open-weight models (`gemma3:1b`, `qwen2.5:1.5b`, `llama3.2:1b`).
- Bounded token generation: `num_predict` capped at 60 for whispers, 120 for rewrites.
- Strict request timeout: 3s for whispers, 6s for rewrites.

### 4. The Crypt
- Contains over 60 hand-crafted ghostly quips across the three personas.
- Whenever the model backend is down, slow, or times out, Wraith degrades gracefully to The Crypt. The developer never sees an error.

### 5. Graveyard (SQLite)
- Stores redacted haunts and generated whispers.
- Computes streak metrics, busiest hours, top commands, and longest silence periods.
- Supplies data for `wraith ofrenda` (retired commands with no activity for 60+ days).

