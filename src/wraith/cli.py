"""Command Line Interface for Wraith."""

from __future__ import annotations

import asyncio
import datetime
import json
import socket
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from wraith import __version__
from wraith.bench import run_benchmark
from wraith.config import WraithConfig, get_config_dir, get_graveyard_db_path, get_socket_path
from wraith.graveyard import Graveyard
from wraith.mcp_server import run_mcp_server
from wraith.models import get_model_client
from wraith.ofrenda import render_ofrenda
from wraith.personas import list_personas, load_persona, safe_glyph, scaffold_persona
from wraith.possess import get_last_error, run_possessed_pty

app = typer.Typer(
    name="wraith",
    help="A haunted terminal that whispers eerie commentary using local open-weight language models.",
    no_args_is_help=True,
)
persona_app = typer.Typer(help="Manage ghostly personas.")
app.add_typer(persona_app, name="persona")

console = Console()


def version_callback(value: bool):
    if value:
        g = safe_glyph("👻", "~")
        console.print(
            f"[bold cyan]Wraith[/bold cyan] version [bold green]{__version__}[/bold green] {g}"
        )
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Wraith version.",
        callback=version_callback,
        is_eager=True,
    ),
):
    pass


@app.command()
def init(
    shell: str = typer.Argument(..., help="Target shell: 'zsh' or 'bash'"),
):
    """Print the shell hook to be evaluated in your shell rc file."""
    shell_lower = shell.lower().strip()
    hooks_dir = Path(__file__).parent / "hooks"

    if shell_lower == "zsh":
        hook_path = hooks_dir / "zsh.sh"
    elif shell_lower == "bash":
        hook_path = hooks_dir / "bash.sh"
    else:
        console.print(
            f"[bold red]Unsupported shell:[/bold red] '{shell}'. Wraith supports 'zsh' and 'bash'."
        )
        raise typer.Exit(code=1)

    if not hook_path.is_file():
        console.print(f"[bold red]Hook file not found at:[/bold red] {hook_path}")
        raise typer.Exit(code=1)

    # Print the shell script to stdout
    print(hook_path.read_text(encoding="utf-8"))


@app.command()
def setup():
    """Interactive first-run setup: configures defaults and checks local model runtime."""
    g = safe_glyph("👻", "~")
    console.print(
        Panel(
            f"[bold cyan]Welcome to Wraith: A Haunted Terminal[/bold cyan] {g}\nSetting up your local ghostly companion...",
            border_style="cyan",
        )
    )

    cfg = WraithConfig.load()
    cfg.save()
    console.print(
        f"[green]✓[/green] Configuration saved to [bold]{get_config_dir() / 'config.toml'}[/bold]"
    )

    # Check Ollama
    client = get_model_client(cfg.model)
    is_available = asyncio.run(client.is_available())
    if is_available:
        console.print(
            f"[green]✓[/green] Local model backend reachable at [cyan]{cfg.model.base_url}[/cyan]"
        )
        has_model = asyncio.run(client.is_model_installed())
        if has_model:
            console.print(
                f"[green]✓[/green] Model [bold]{cfg.model.name}[/bold] is installed and ready."
            )
        else:
            console.print(
                f"[yellow]![/yellow] Model [bold]{cfg.model.name}[/bold] is not pulled yet."
            )
            console.print(f"  Run: [bold green]ollama pull {cfg.model.name}[/bold green]")
    else:
        console.print(
            f"[yellow]![/yellow] Could not connect to local model backend at {cfg.model.base_url}"
        )
        console.print("  Make sure Ollama or your local model server is running.")
        console.print(
            "  Wraith will still operate completely offline using hand-crafted whispers from [bold]The Crypt[/bold]!"
        )

    console.print(
        "\n[bold]Next Step:[/bold] Add this line to your [italic]~/.zshrc[/italic] or [italic]~/.bashrc[/italic]:"
    )
    console.print('[bold green]eval "$(wraith init zsh)"[/bold green]  # or bash\n')


@app.command()
def doctor():
    """Diagnose installation, socket health, model availability, and database."""
    console.print("[bold]Running Wraith Doctor...[/bold]\n")

    cfg = WraithConfig.load()
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Component", width=22)
    table.add_column("Status", width=12)
    table.add_column("Details", width=46)

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        table.add_row("Python Runtime", "[green]OK[/green]", f"Python {py_ver}")
    else:
        table.add_row("Python Runtime", "[red]FAIL[/red]", f"Python {py_ver} (requires >= 3.10)")

    # 2. Config file
    config_file = get_config_dir() / "config.toml"
    if config_file.is_file():
        table.add_row("Configuration", "[green]OK[/green]", str(config_file))
    else:
        table.add_row(
            "Configuration",
            "[yellow]DEFAULTS[/yellow]",
            "Using built-in defaults (run 'wraith setup' to write)",
        )

    # 3. Model Backend
    client = get_model_client(cfg.model)
    backend_up = asyncio.run(client.is_available())
    if backend_up:
        model_ready = asyncio.run(client.is_model_installed())
        if model_ready:
            table.add_row(
                "Model Backend",
                "[green]OK[/green]",
                f"{cfg.model.backend} @ {cfg.model.base_url} ({cfg.model.name})",
            )
        else:
            table.add_row(
                "Model Backend",
                "[yellow]WARN[/yellow]",
                f"{cfg.model.backend} up, but '{cfg.model.name}' not pulled",
            )
    else:
        table.add_row(
            "Model Backend",
            "[yellow]OFFLINE[/yellow]",
            f"Cannot reach {cfg.model.base_url} (The Crypt fallback active)",
        )

    # 4. Socket / Daemon
    sock_path = get_socket_path()
    port_file = sock_path.with_suffix(".port")
    daemon_online = False
    try:
        if hasattr(socket, "AF_UNIX") and sock_path.exists():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.2)
            s.connect(str(sock_path))
            s.sendall(b'{"type":"ping"}\n')
            res = s.recv(1024)
            daemon_online = b"pong" in res
            s.close()
        elif port_file.exists():
            p_str = port_file.read_text(encoding="utf-8").strip()
            if p_str.isdigit():
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.2)
                s.connect(("127.0.0.1", int(p_str)))
                s.sendall(b'{"type":"ping"}\n')
                res = s.recv(1024)
                daemon_online = b"pong" in res
                s.close()
    except Exception:
        daemon_online = False

    if daemon_online:
        table.add_row("Daemon (wraithd)", "[green]RUNNING[/green]", "Socket responding to ping")
    else:
        table.add_row(
            "Daemon (wraithd)",
            "[yellow]STOPPED[/yellow]",
            "Not running (starts automatically with shell hook or 'wraithd')",
        )

    # 5. Graveyard DB
    db_path = get_graveyard_db_path()
    if db_path.is_file():
        gy = Graveyard(db_path)
        stats = gy.get_stats()
        table.add_row(
            "Graveyard DB",
            "[green]OK[/green]",
            f"{stats['total_haunts']} haunts, {stats['total_whispers']} whispers recorded",
        )
    else:
        table.add_row(
            "Graveyard DB", "[cyan]NEW[/cyan]", f"Will be initialized on first command at {db_path}"
        )

    # 6. Active persona
    persona = load_persona(cfg.whisper.persona)
    glyph = safe_glyph(persona.ghost_glyph, "~")
    table.add_row(
        "Active Persona",
        "[green]OK[/green]",
        f"{glyph} {persona.name} ({persona.description})",
    )

    console.print(table)


@app.command("on")
def haunt_on():
    """Enable terminal haunting for this session."""
    print("unset WRAITH_OFF")
    g = safe_glyph("👻", "~")
    console.print(f"[bold green]{g} Wraith is watching once more.[/bold green]")


@app.command("off")
def haunt_off():
    """Disable terminal haunting for this session."""
    print("export WRAITH_OFF=1")
    console.print("[dim]The spirits quiet down for this session.[/dim]")


@app.command()
def possess(
    replace: bool = typer.Option(
        False, "--replace", help="Replace original error instead of annotating beneath it."
    ),
):
    """Start an interactive possessed-mode PTY shell."""
    run_possessed_pty(replace=replace)


@app.command()
def unveil():
    """Show the last raw un-possessed error output."""
    raw = get_last_error()
    console.print(Panel(raw, title="[bold red]Unveiled Raw Error[/bold red]", border_style="red"))


@persona_app.command("list")
def persona_list():
    """List all available ghostly personas."""
    cfg = WraithConfig.load()
    personas = list_personas()
    table = Table(title="Spectral Personas", expand=True)
    table.add_column("Active", width=8, justify="center")
    table.add_column("Glyph", width=6, justify="center")
    table.add_column("Name", width=18, style="bold cyan")
    table.add_column("Origin", width=10)
    table.add_column("Description", width=40)

    for p in personas:
        is_active = "[bold green]OK[/bold green]" if p["name"] == cfg.whisper.persona else ""
        origin = "Custom" if p.get("custom") else "Bundled"
        glyph = safe_glyph(p.get("glyph", "👻"), "~")
        table.add_row(is_active, glyph, p["name"], origin, p.get("description", ""))

    console.print(table)


@persona_app.command("use")
def persona_use(
    name: str = typer.Argument(..., help="Name of persona to activate"),
):
    """Set the active persona for whispers and possessed rewrites."""
    cfg = WraithConfig.load()
    available = [p["name"] for p in list_personas()]
    if name not in available:
        console.print(
            f"[bold red]Unknown persona:[/bold red] '{name}'. Run 'wraith persona list' to see options."
        )
        raise typer.Exit(code=1)

    cfg.whisper.persona = name
    cfg.save()
    p = load_persona(name)
    glyph = safe_glyph(p.ghost_glyph, "~")
    console.print(
        f"[bold green]Switched to persona:[/bold green] {glyph} [bold cyan]{p.name}[/bold cyan] ({p.description})"
    )


@persona_app.command("new")
def persona_new(
    name: str = typer.Argument(..., help="Name of the new persona to scaffold"),
):
    """Scaffold a new custom persona file in your config directory."""
    try:
        path = scaffold_persona(name)
        console.print(f"[bold green]Created new persona template at:[/bold green] {path}")
        console.print(
            "Edit the file to customize system prompts, style rules, and few-shot examples."
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def graveyard():
    """Display statistics and history from the local Graveyard database."""
    gy = Graveyard()
    stats = gy.get_stats()
    c = safe_glyph("⚰️", "+")

    console.print(
        Panel(
            f"[bold red]{c} THE GRAVEYARD STATS {c}[/bold red]\n[dim]Total Haunts: {stats['total_haunts']} | Total Whispers: {stats['total_whispers']}[/dim]",
            border_style="red",
        )
    )

    # Top commands
    if stats["top_commands"]:
        t1 = Table(title="Most Frequent Incantations", expand=True)
        t1.add_column("Command", style="bold white")
        t1.add_column("Occurrences", justify="right", style="cyan")
        for c in stats["top_commands"]:
            t1.add_row(c["command"], str(c["count"]))
        console.print(t1)

    # Dangerous commands
    if stats["dangerous_commands"]:
        t2 = Table(title="Dangerous Invocations Survived", expand=True)
        t2.add_column("Command", style="bold red")
        t2.add_column("Times Run", justify="right", style="yellow")
        for c in stats["dangerous_commands"]:
            t2.add_row(c["command"], str(c["count"]))
        console.print(t2)

    # General trivia
    t3 = Table(title="Spectral Metrics", expand=True)
    t3.add_column("Metric", style="bold")
    t3.add_column("Value", style="italic")

    longest_silence = stats["longest_silence_seconds"]
    silence_str = (
        f"{round(longest_silence / 3600, 1)} hours"
        if longest_silence > 3600
        else f"{longest_silence} seconds"
    )
    t3.add_row("Longest Silence", silence_str)
    t3.add_row("Max Consecutive Failure Streak", f"{stats['max_failure_streak']} failures")

    if stats["busiest_hours"]:
        top_hr = stats["busiest_hours"][0]
        t3.add_row("Busiest Hour", f"{top_hr['hour']}:00 ({top_hr['count']} commands)")

    console.print(t3)


@app.command()
def ofrenda():
    """Display Día de los Muertos remembrance view for retired commands."""
    render_ofrenda()


@app.command()
def bench(
    model: str | None = typer.Option(
        None, "--model", "-m", help="Specific model to benchmark (defaults to configured model)"
    ),
):
    """Benchmark current model latency, tokens/sec, and fact-preservation rate."""
    asyncio.run(run_benchmark(model_name=model))


@app.command()
def forget(
    all_data: bool = typer.Option(
        False, "--all", help="Purge all haunts and whispers immediately."
    ),
    since: str | None = typer.Option(
        None, "--since", help="Delete commands run on or after date (YYYY-MM-DD)."
    ),
    pattern: str | None = typer.Option(
        None, "--pattern", help="Delete commands matching regular expression."
    ),
):
    """Immediately delete sensitive data or all history from the graveyard."""
    gy = Graveyard()

    if not all_data and not since and not pattern:
        console.print(
            "[bold yellow]Please specify --all, --since <YYYY-MM-DD>, or --pattern <regex>.[/bold yellow]"
        )
        raise typer.Exit(code=1)

    since_ts: int | None = None
    if since:
        try:
            dt = datetime.datetime.strptime(since, "%Y-%m-%d")
            since_ts = int(dt.timestamp())
        except ValueError:
            console.print("[bold red]Invalid date format.[/bold red] Use YYYY-MM-DD.")
            raise typer.Exit(code=1)

    count = gy.forget(forget_all=all_data, since_ts=since_ts, pattern=pattern)
    console.print(f"[bold green]Purged {count} haunt records from the graveyard.[/bold green]")


@app.command("export")
def export_data():
    """Export the local graveyard database as JSON."""
    gy = Graveyard()
    data = gy.export_json()
    print(json.dumps(data, indent=2))


@app.command("mcp")
def run_mcp():
    """Run the read-only local Model Context Protocol (MCP) server."""
    run_mcp_server()


if __name__ == "__main__":
    app()
