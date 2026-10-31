"""Día de los Muertos Ofrenda: Remembrance altar for retired shell commands."""

from __future__ import annotations

import asyncio
import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from wraith.config import WraithConfig
from wraith.graveyard import Graveyard
from wraith.models import get_model_client
from wraith.personas import load_persona, safe_glyph
from wraith.prompts import build_whisper_messages
from wraith.validate import validate_whisper

CANDLE_ART = """
      ( )           ( )           ( )
       |             |             |
     [~~~]         [~~~]         [~~~]
     |   |         |   |         |   |
     |___|         |___|         |___|
"""

NO_COLOR_CANDLE = """
      ( )           ( )           ( )
       |             |             |
     [---]         [---]         [---]
     |   |         |   |         |   |
     |___|         |___|         |___|
"""


async def get_ancestor_remembrance(cmd: str, days_dormant: int, config: WraithConfig) -> str:
    """Generate a one-line ancestral remembrance for a retired command."""
    persona = load_persona("ancestor")
    event_ctx = {
        "trigger": "graveyard_recall",
        "cmd_redacted": cmd,
        "exit_code": 0,
        "prior_runs": 10,
        "local_time": "12:00",
        "cwd_base": "history",
    }
    messages = build_whisper_messages(persona, event_ctx)

    try:
        model_client = get_model_client(config.model)
        raw = await model_client.chat(
            messages,
            max_tokens=60,
            temperature=persona.temperature,
            timeout=config.model.whisper_timeout,
        )
        valid, cleaned = validate_whisper(raw)
        if valid:
            return cleaned
    except Exception:
        pass

    # Fallback remembrance
    return f"Ay, mijo, you used to type '{cmd}' so often. We keep a golden candle burning for its memory."


def render_ofrenda(graveyard: Graveyard | None = None, config: WraithConfig | None = None) -> None:
    """Render the Día de los Muertos altar to the terminal."""
    gy = graveyard or Graveyard()
    cfg = config or WraithConfig.load()
    is_no_color = bool(os.environ.get("NO_COLOR"))

    console = Console(no_color=is_no_color, width=80)

    retired = gy.get_retired_commands(days_threshold=60, min_usage=2)

    flower = safe_glyph("🌼", "*")
    # Header styling: Marigold orange and candle yellow
    if is_no_color:
        console.print(NO_COLOR_CANDLE)
        console.print("=== OFRENDA DE COMANDOS (DIA DE LOS MUERTOS) ===")
        console.print("Honoring the tools and incantations retired into the shadows.\n")
    else:
        console.print(f"[bold yellow]{CANDLE_ART}[/bold yellow]")
        title = Text(f"{flower} OFRENDA DE COMANDOS {flower}", style="bold #E08119")
        subtitle = Text(
            "Honoring the tools and incantations that brought you here", style="italic #FFD152"
        )
        console.print(Panel(subtitle, title=str(title.plain), border_style="#E08119"))

    if not retired:
        # If no commands are 60+ days dormant yet, show a welcoming altar message
        msg = (
            "The altar is set with fresh marigolds and pan de muerto.\n"
            "None of your commands have rested for 60 days yet.\n"
            "Keep building, mijo; when your old habits retire, their memory will be honored here."
        )
        if is_no_color:
            console.print(msg)
        else:
            console.print(Panel(msg, border_style="#FFD152", style="#FFD152"))
        return

    table = Table(
        show_header=True,
        header_style="bold #FFD152" if not is_no_color else "bold",
        border_style="#E08119" if not is_no_color else None,
        expand=True,
    )
    table.add_column("Command", style="bold white", width=18)
    table.add_column("Dormant", style="italic cyan" if not is_no_color else "", width=10)
    table.add_column("Ancestral Remembrance", style="#FFD152" if not is_no_color else "", width=46)

    # Fetch remembrances
    for item in retired[:5]:
        remembrance = asyncio.run(
            get_ancestor_remembrance(item["command"], item["days_dormant"], cfg)
        )
        table.add_row(
            item["command"],
            f"{item['days_dormant']} days",
            remembrance,
        )

    console.print(table)
    console.print("")
    if not is_no_color:
        console.print("[dim #E08119]~ Descansen en paz los viejos procesos ~[/dim #E08119]\n")
    else:
        console.print("~ Descansen en paz los viejos procesos ~\n")
