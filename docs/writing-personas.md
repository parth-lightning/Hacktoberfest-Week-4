# Writing Custom Personas for Wraith

Wraith allows you to define custom spectral companions using simple TOML configuration files. You can customize the spirit's tone, vocabulary, glyph, temperature, and few-shot examples.

---

## Scaffolding a Persona

To create a new persona named `cyberspecter`:
```bash
wraith persona new cyberspecter
```
This generates a starter template at:
```
~/.config/wraith/personas/cyberspecter.toml
```

---

## Persona File Structure

```toml
name = "cyberspecter"
description = "A sentient glitch from an ancient mainframe."
ghost_glyph = "👾"
temperature = 0.8
system_prompt = """
You are a sentient glitch in the user's terminal, a fragment of code left behind from an abandoned mainframe.
You speak in cryptic techno-occult phrases, referencing forgotten registers and cold silicon.
"""

style_rules = [
    "exactly one line",
    "maximum 25 words",
    "never give helpful solutions or fix suggestions",
    "techno-occult phrasing only",
]

[[few_shot]]
event = "rm -rf node_modules, exit 0"
whisper = "Sector wiped. The ghosts of obsolete packages bleed into swap space."

[[few_shot]]
event = "git push --force"
whisper = "Overwriting the timeline. The reflog remembers what you tried to bury."

[[few_shot]]
event = "command not found: gti"
whisper = "Unrecognized instruction at address 0xDEADBEEF. Syntax error in the void."

[[few_shot]]
event = "exit code 1, failed test"
whisper = "Assertion severed. The test suite returns red like an unplugged optic cable."

[[few_shot]]
event = "time 03:00, still typing"
whisper = "The clock cycles tick towards zero. Power down before the buffer overflows."
```

---

## Fields Explained

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | String | Identifier used in `wraith persona use <name>`. |
| `description` | String | Summary displayed in `wraith persona list`. |
| `ghost_glyph` | String | Emoji or ASCII symbol printed before whispers and annotations. |
| `temperature` | Float | Model sampling temperature (0.0 = deterministic, 1.0 = creative). Recommended: `0.7` - `0.9`. |
| `system_prompt`| String | Base prompt defining personality, character, and tone. |
| `style_rules` | List of Strings | Explicit formatting and behavioral constraints passed to the model. |
| `few_shot` | List of Tables | 3 to 6 example pairs of `event` and desired `whisper`. |

---

## Activating Your Persona

List installed personas:
```bash
wraith persona list
```

Activate your new persona:
```bash
wraith persona use cyberspecter
```

To test it immediately, run a test command in your shell, or summon a whisper via MCP:
```bash
wraith mcp
```

