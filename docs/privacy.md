# Wraith Privacy Architecture

> **Hard Privacy Guarantee:** Your shell commands and confidential files MUST never leave your computer.

Wraith was specifically engineered for privacy-conscious developers. Shell environments contain API tokens, private repository names, internal hostnames, passwords, and sensitive file paths. Wraith enforces strict multi-layered data protection.

---

## 1. Network Boundary

Wraith operates under a **Zero Network Egress** policy:

- **Loopback Enforcement:** All requests from the daemon to the local model backend are strictly restricted to loopback addresses (`127.0.0.1`, `localhost`, `::1`).
- **Remote Host Protection:** Any attempt to point Wraith to a remote host (e.g. `http://api.openai.com` or `http://192.168.1.50`) raises a security violation (`ValueError`) and refuses to start, unless the user explicitly opts in with `allow_remote = true` in `config.toml`.
- **No Telemetry:** Wraith includes no telemetry, no tracking, no Google Analytics, and no background update pingers.

---

## 2. In-Memory Redaction Engine

Before any command is written to the SQLite graveyard or sent to a local language model, it passes through `wraith.redact`:

| Category | Patterns Masked | Replacement |
| :--- | :--- | :---: |
| **AWS Credentials** | `AKIA[0-9A-Z]{16}`, `ASIA...`, `ABIA...` | `<redacted>` |
| **JSON Web Tokens** | `eyJ...` (three segment base64url) | `<redacted>` |
| **URLs with Passwords** | `https://user:pass@host/path` | `https://<redacted>@host/path` |
| **Authorization Headers** | `Authorization: Bearer <token>` | `Authorization: <redacted>` |
| **CLI Flags** | `--password`, `-p`, `--token`, `--api-key`, `--secret` | `<flag> <redacted>` |
| **Environment Variables** | `KEY=val` where KEY contains `key`, `token`, `secret`, `pass`, `pwd`, `auth` | `KEY=<redacted>` |
| **GitHub / Slack Tokens** | `ghp_...`, `gho_...`, `xoxb-...`, `xoxp-...` | `<redacted>` |
| **Private Keys** | `-----BEGIN RSA PRIVATE KEY-----...` | `<redacted>` |
| **High-Entropy Tokens** | Standalone alphanumeric strings >= 40 characters with Shannon entropy >= 3.5 | `<redacted>` |
| **Custom Patterns** | Any regex specified in `privacy.redact_patterns` | `<redacted>` |

---

## 3. What the Model Receives

### For Whispers:
The local model receives **only** a structured event metadata block:
- Redacted command (e.g., `rm -rf <redacted>`)
- Numeric exit code (e.g., `0` or `127`)
- Trigger type (e.g., `dangerous_command`, `late_night`)
- Prior occurrence count from local history
- Local time of day (`HH:MM`)
- Directory **basename only** (e.g. `myproject`, NOT full path `/home/username/work/private/myproject`)

**The model never receives:**
- Full filesystem paths
- User environment variables
- Standard output of your commands

### For Possessed Mode:
When a command fails:
- Only the error/traceback block (last 30 lines) is inspected
- Key tokens (line numbers, module names) are extracted
- File paths are reduced to basenames where possible
- The original error is preserved in `~/.cache/wraith/last_error.txt` for `wraith unveil`

---

## 4. Local Storage and Data Rights

- **File Permissions:** Graveyard SQLite databases (`graveyard.db`) and socket files are set to `0600` (readable only by the current OS user).
- **Instant Complete Purge:** Run `wraith forget --all` to permanently drop all recorded haunts and whispers.
- **Selective Deletion:** Run `wraith forget --pattern "secret_project"` or `wraith forget --since 2026-10-01`.
- **Data Export:** Run `wraith export` to audit the entire graveyard in human-readable JSON format.

