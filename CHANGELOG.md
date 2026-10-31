# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-31

### Added
- Initial release for Hacktoberfest "Ghost in the Machine".
- Shell integrations for `zsh` and `bash`.
- Asynchronous Unix domain socket daemon (`wraithd`) with sub-10ms prompt overhead.
- Redaction engine masking passwords, tokens, API keys, JWTs, and credentials.
- 9 event triggers: dangerous commands, repetition, streaks, typos, late night, returning, graveyard recall, session end, and ambient whispers.
- Local model backends: Ollama (`/api/chat`) and OpenAI-compatible endpoints with loopback security enforcement.
- "The Crypt": graceful offline fallback with 60+ hand-crafted persona whispers and error rewrites.
- Possessed mode (`wraith possess`) PTY proxy with semantic error detection and fact-preservation verification.
- Three built-in personas: `poltergeist`, `victorian-medium`, and `ancestor`.
- SQLite Graveyard store with `graveyard`, `ofrenda`, `forget`, and `export` commands.
- Benchmark utility (`wraith bench`) comparing latency, tokens/sec, and fact preservation.
- Read-only local MCP server (`wraith mcp`).

