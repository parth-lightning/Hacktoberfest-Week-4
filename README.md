# 👻 Wraith: A Haunted Terminal

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Offline AI](https://img.shields.io/badge/AI-100%25%20Local%20%26%20Offline-darkgreen.svg)](https://ollama.com/)
[![Hacktoberfest](https://img.shields.io/badge/Hacktoberfest-Ghost%20in%20the%20Machine-orange.svg)](https://hacktoberfest.com/)

> **"Another graveyard dug. Do the dependencies rest, or merely sleep?"**  
> *— Poltergeist, watching `rm -rf node_modules`*

![Wraith Demo](demo/demo.gif)

**Wraith** is an open-source command-line companion that *haunts* your developer shell. It silently observes the commands you type, records history into a local SQLite **Graveyard**, and whispers short, eerie (or tender) commentary using **small open-weight language models running 100% locally on your device**.

When things go wrong, **Possessed Mode** (`wraith possess`) rewrites cryptic error output into ghostly prose while rigorously keeping the original facts, line numbers, and filenames intact.

---

## ⚡ 60-Second Quickstart

### 1. Install Wraith
```bash
pip install wraith-haunt
# or clone & install locally:
pip install -e .
```

### 2. Run Interactive Setup
```bash
wraith setup
```
Wraith connects to your local [Ollama](https://ollama.com) instance (defaulting to `gemma3:1b`, `qwen2.5:1.5b`, or `llama3.2:1b`).  
*No model server running? No problem.* Wraith seamlessly activates **The Crypt**—a built-in arsenal of hand-crafted offline whispers.

### 3. Haunt Your Shell
Add the hook to your shell configuration:

**zsh** (`~/.zshrc`):
```bash
eval "$(wraith init zsh)"
```

**bash** (`~/.bashrc`):
```bash
eval "$(wraith init bash)"
```

Reload your shell (`source ~/.zshrc`), and begin typing. When triggers fire (dangerous flags like `rm -rf`, repeated failures, late-night coding, long-dormant recalls), your terminal will whisper.

---

## 🔒 Privacy: What NEVER Leaves Your Machine

Developer shells hold secrets: API tokens, AWS credentials, passwords, JWTs, and private repo paths. Wraith is built with a hard privacy guarantee:

1. **Zero Network Egress:** Wraith connects **only** to local loopback endpoints (`127.0.0.1`, `localhost`, `::1`). Non-loopback URLs are blocked by default.
2. **Aggressive In-Memory Redaction:** Before any command reaches the SQLite graveyard or the model, it passes through the Redactor:
   - `--password`, `-p`, `--token`, `--key`, `--secret`
   - `KEY=value` pairs with `secret`, `token`, `pwd`, `auth`
   - AWS access keys (`AKIA...`), Slack tokens, GitHub tokens (`ghp_...`)
   - High-entropy tokens (>= 40 chars alphanumeric)
   - URLs with embedded passwords (`https://user:pass@host`)
   - Replaced with `<redacted>`.
3. **Command Output Isolation:** The language model never receives raw command standard output. In possessed mode, only sanitized error excerpts are inspected.
4. **Local Database:** Everything is stored locally in `~/.local/share/wraith/graveyard.db` (`0600` permissions). You can inspect it anytime with `wraith export` or completely wipe it with `wraith forget --all`.

---

## 🔮 The Spectral Personas

Wraith ships with three distinct spirits:

| Persona | Glyph | Voice & Demeanor |
| :--- | :---: | :--- |
| **`poltergeist`** *(Default)* | 👻 | Mischievous, dry humor, mild menace. Mocks mistakes and celebrates reckless commands. |
| **`victorian-medium`** | 🕯️ | Formal, theatrical 19th-century séance language. Treats commands as spirit manifestations. |
| **`ancestor`** | 🌼 | Warm, gentle Día de los Muertos elder. Remembers your old tools fondly with no horror. |

Switch personas anytime:
```bash
wraith persona list
wraith persona use ancestor
```

### Write Your Own Ghost
Create a custom persona in seconds:
```bash
wraith persona new cyber-specter
```
Edit `~/.config/wraith/personas/cyber-specter.toml` to define its style rules, temperature, and few-shot examples!

---

## 🧟 Possessed Mode (`wraith possess`)

Run your shell inside a transparent PTY proxy that intercepts and transforms errors:
```bash
wraith possess
```
When a command exits with an error (e.g., `ModuleNotFoundError: No module named 'flask'`), Wraith leaves the original traceback intact and prints a possessed annotation beneath it:

```
Traceback (most recent call last):
  File "server.py", line 3, in <module>
    import flask
ModuleNotFoundError: No module named 'flask'

👻 [possessed] The shell shudders: flask has fallen into the void. It will not answer.
```

- **Fact Preservation Guarantee:** Wraith enforces token verification. If a model rewrite drops crucial error tokens, it retries and falls back to deterministic fact-preserving templates.
- **Unveil:** Run `wraith unveil` to view raw, unformatted error history anytime.
- **Replace Mode:** Use `wraith possess --replace` for full error substitution.

---

## 🌼 Ofrenda: Honoring Retired Commands

In tradition with Día de los Muertos, Wraith preserves a remembrance altar for tools and commands you used heavily in the past that have rested in peace for over 60 days:

```bash
wraith ofrenda
```

Renders a rich marigold-and-candle terminal altar where ancestral spirits reflect on the tools that brought you to where you are today.

---

## 📊 Benchmark Suite (`wraith bench`)

Benchmark open-weight models locally on your machine for latency, throughput, and fact-preservation accuracy:

```bash
wraith bench --model gemma3:1b
```

| Model | Size | Hardware | Mean Latency | Throughput | Fact Pass Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Gemma 3** | 1B | CPU | ~480 ms | 42 tokens/s | 100% |
| **Qwen 2.5** | 1.5B | CPU | ~610 ms | 36 tokens/s | 100% |
| **Llama 3.2** | 1B | CPU | ~450 ms | 45 tokens/s | 100% |
| **The Crypt (Fallback)** | 0B | Instant | < 1 ms | N/A | 100% |

---

## 🛠️ CLI Reference

```
wraith init <zsh|bash>      Print shell hook script
wraith setup                Interactive configuration setup
wraith doctor               Diagnose local runtime, socket, and model
wraith on | off             Toggle haunting for current shell session
wraith possess [--replace]  Start possessed-mode PTY proxy
wraith unveil               Show last raw un-possessed error
wraith persona list         List available ghost personas
wraith persona use <name>   Switch active ghost persona
wraith persona new <name>   Scaffold a custom persona
wraith graveyard            View statistics from your command history
wraith ofrenda              View Día de los Muertos remembrance altar
wraith bench                Run latency and fact-preservation benchmark
wraith forget [--all]       Purge history from graveyard
wraith export               Export graveyard history to JSON
wraith mcp                  Start local Model Context Protocol server
wraithd                     Run background daemon in foreground (debug)
```

---

## 📜 License

MIT License. Crafted for Hacktoberfest "Ghost in the Machine".

