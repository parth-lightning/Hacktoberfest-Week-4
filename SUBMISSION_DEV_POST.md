*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

# 👻 Wraith: A Haunted Terminal Powered by Local Open-Weight Models & Día de los Muertos Altar

> *"Another graveyard dug. Do the dependencies rest, or merely sleep?"*  
> — `poltergeist`, watching `rm -rf node_modules`

---

## What I Built

**Wraith** is an open-source terminal companion that literally "haunts" your shell (`zsh` or `bash`). It silently observes the commands you run, buries history into a local SQLite **Graveyard**, and whispers short, eerie (or tender) commentary using **small open-weight language models (1B–3B parameters) running 100% locally on your machine**.

When commands fail, Wraith's **Possessed Mode** (`wraith possess`) launches a transparent PTY proxy that rewrites cryptic error traces into ghostly prose beneath the original output—rigorously verifying through a **fact-preservation check** that no file names, line numbers, or error classes are ever obscured.

And because Halloween coincides with **Día de los Muertos**, Wraith doesn't just treat terminal history as a haunting—it treats it as an ancestor remembrance. Running `wraith ofrenda` constructs an ASCII marigold-and-candle altar honoring tools, aliases, and incantations you haven't typed in over 60 days ("Ay, mijo, you used to type `vim` every morning. We still keep a candle lit for it.").

### Key Features
- **Prompt Overhead < 1 ms:** Shell hooks dispatch telemetry asynchronously in background subshells. Your prompt is never blocked waiting for LLM inference.
- **Strict Privacy Redactor:** Every command is stripped of AWS keys, JWTs, passwords, auth headers, and high-entropy secrets in-memory before storage or inference.
- **"The Crypt" Offline Fallback:** Over 60 hand-crafted quips across 3 personas. If your local model is stopped or slow, the ghost degrades gracefully with zero errors.
- **9 Adaptive Triggers:** Reacts to dangerous commands (`rm -rf`, `git push --force`), repetition streaks, consecutive failures, typos (exit code 127), witching hours (00:00–04:00), inactivity returns, and graveyard recalls.
- **3 Built-in Personas:** `poltergeist` (mischievous menace), `victorian-medium` (19th-century séance), and `ancestor` (warm Día de los Muertos elder).

---

## Demo

![Wraith Demo GIF](https://raw.githubusercontent.com/parth/wraith/main/demo/demo.gif)

### 1. Whispers in Action
```bash
$ gti status
zsh: command not found: gti
👻 Even the dead can read, mortal. 'gti' is not a word of power.

$ rm -rf build node_modules
👻 Another graveyard dug. Do the dependencies rest, or merely sleep?
```

### 2. Possessed Mode (`wraith possess`)
```bash
$ python -c "import nonexistentpkg"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'nonexistentpkg'

👻 [possessed] The shell shudders: nonexistentpkg has fallen into the void. It will not answer.
```

### 3. Día de los Muertos Remembrance Altar (`wraith ofrenda`)
```
      ( )           ( )           ( )
       |             |             |
     [~~~]         [~~~]         [~~~]
     |   |         |   |         |   |
     |___|         |___|         |___|

🌼 OFRENDA DE COMANDOS 🌼
Honoring the tools and incantations that brought you here

Command             Dormant     Ancestral Remembrance
──────────────────  ──────────  ──────────────────────────────────────────────
vim old_notes.txt   72 days     Ay, mijo, you used to type 'vim' so often. 
                                We keep a golden candle burning for its memory.
```

---

## Code

The complete source code, test suite, and persona templates are open source under the MIT License:

- **Repository:** [https://github.com/parth/wraith](https://github.com/parth/wraith)
- **License:** MIT

### Repo Architecture:
- `src/wraith/daemon.py`: Asynchronous domain socket daemon handling rate-limiting and whisper generation.
- `src/wraith/redact.py`: High-entropy regex redactor stripping credentials before inference.
- `src/wraith/triggers.py`: 9-trigger rule evaluation engine.
- `src/wraith/validate.py`: Word-capping, ANSI-cleansing, and fact-preservation verification.
- `src/wraith/possess.py`: Transparent PTY proxy intercepting errors while preserving interactive programs (`vim`, `less`, `htop`).
- `src/wraith/ofrenda.py`: Rich terminal altar with ASCII candles and ancestral reflections.
- `src/wraith/crypt.py`: 60+ hand-written offline fallback quips.
- `tests/`: 77 unit & integration tests with 100% pass rate.

---

## How I Built It

Wraith was built around **small, local open-weight models** using Python 3.12, Typer, Rich, and Ollama:

1. **Local Open-Weight Models:**  
   Wraith is optimized for 1B–3B parameter models such as **Gemma 3 1B**, **Qwen 2.5 1.5B**, and **Llama 3.2 1B**. These models generate a 20-word whisper in ~400 ms on standard laptop CPUs without needing discrete GPUs.
2. **Loopback-Only Client Architecture:**  
   The model client (`src/wraith/models/`) queries Ollama `/api/chat` or any local OpenAI-compatible endpoint (`llama-server`, LM Studio). It enforces a strict security guard that refuses to connect to any non-loopback IP unless `allow_remote = true` is explicitly opted into.
3. **Fact-Preservation Algorithm:**  
   To ensure possessed mode never hides root causes, `src/wraith/validate.py` regex-extracts error classes (`ModuleNotFoundError`, `SyntaxError`), filenames, and line numbers. The model's rewrite is checked against these tokens; if any essential facts were dropped, Wraith retries once and falls back to a deterministic template.
4. **Asynchronous Shell Hooks:**  
   Using `precmd` (zsh) and `PROMPT_COMMAND` (bash), events are fired to `$XDG_RUNTIME_DIR/wraith.sock` in detached background subshells. Incoming whispers are staged in a per-session file and rendered on the subsequent prompt.

---

## Why Does Open Innovation Matter?

Developer shells are intimate workspaces. Every single day, engineers type:
- Production database connection strings
- Temporary API keys and auth bearer tokens
- Internal hostnames and private project directory paths

**You cannot simply pipe every keystroke and stderr traceback to a closed, commercial cloud API.** 

Open-weight models and local inference engines (like Ollama and llama.cpp) fundamentally alter what is possible:
- **Absolute Data Sovereignty:** Telemetry never leaves the machine (`127.0.0.1`). There is zero external network egress.
- **Works Offline in the Cabin:** Whether coding on an airplane or during an autumn storm with no power or Wi-Fi, the ghost still speaks.
- **Zero Ingestion Cost:** No per-token pricing, no vendor rate limits, and no subscriptions.
- **Hackable Personas:** Rather than being locked behind rigid safety alignment or vendor-mandated voices, anyone can drop a new `.toml` file into `~/.config/wraith/personas/` to craft their own cyber-specter.

---

## My Agent Session

This entire system—from the initial Software Requirements Specification (SRS) through the daemon, PTY proxy, SQLite graveyard, redactor, ofrenda, and 77 passing unit tests—was designed, implemented, and verified using **Antigravity**, an agentic AI coding environment.

You can view the full agent interaction transcript documenting the architecture decisions, test failures, and bug resolutions:
<!-- If publishing via DevRelay, embed your session tag here: -->
<!-- {% agent_session session_id %} -->

---

## The Spirit of It

There is an eerie melancholy to terminal history. 

We spend hundreds of hours using a tool—running `vagrant up`, `svn checkout`, or `python2 server.py`—and then one day, we upgrade or switch stacks, and we simply never type that command again. Those commands don't disappear; they just lie silent in `.bash_history` like unvisited graves.

When `wraith ofrenda` renders its candles in the terminal and speaks in the `ancestor` persona:
> *"Ay, mijo, you used to type 'vim' every morning. We still keep a candle lit for it."*

...it reminds us that the machine isn't just cold silicon and exit codes. It holds the muscle memory and ghost of every project we ever built.

---

## Prize Categories

- **Ghost in the Machine (Grand Prize)**
- **Best Use of Open-Weight Models (Local Inference / Ollama)**
- **Best Developer Experience Tool**

