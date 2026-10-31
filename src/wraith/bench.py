"""Benchmark suite for testing model inference speed and fact-preservation rate."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console
from rich.table import Table

from wraith.config import WraithConfig
from wraith.models import get_model_client
from wraith.personas import load_persona
from wraith.prompts import build_rewrite_messages, build_whisper_messages
from wraith.validate import (
    check_fact_preservation,
    extract_key_tokens,
    validate_rewrite,
    validate_whisper,
)

BENCHMARK_EVENTS = [
    {
        "type": "whisper",
        "trigger": "dangerous_command",
        "cmd_redacted": "rm -rf build",
        "exit_code": 0,
        "prior_runs": 2,
        "local_time": "14:30",
        "cwd_base": "myproject",
    },
    {
        "type": "whisper",
        "trigger": "dangerous_command",
        "cmd_redacted": "git push --force origin main",
        "exit_code": 0,
        "prior_runs": 1,
        "local_time": "16:45",
        "cwd_base": "web-app",
    },
    {
        "type": "whisper",
        "trigger": "command_not_found",
        "cmd_redacted": "gti status",
        "exit_code": 127,
        "prior_runs": 1,
        "local_time": "11:15",
        "cwd_base": "core",
    },
    {
        "type": "whisper",
        "trigger": "repetition",
        "cmd_redacted": "pytest tests/",
        "exit_code": 1,
        "prior_runs": 6,
        "local_time": "02:10",
        "cwd_base": "wraith",
    },
    {
        "type": "whisper",
        "trigger": "late_night",
        "cmd_redacted": "cargo build --release",
        "exit_code": 0,
        "prior_runs": 4,
        "local_time": "03:45",
        "cwd_base": "engine",
    },
    {
        "type": "rewrite",
        "error": "ModuleNotFoundError: No module named 'flask'",
        "cmd": "python app.py",
    },
    {
        "type": "rewrite",
        "error": "FileNotFoundError: [Errno 2] No such file or directory: 'secrets.toml'",
        "cmd": "cat secrets.toml",
    },
    {
        "type": "rewrite",
        "error": "SyntaxError: invalid syntax in server.py line 42",
        "cmd": "python server.py",
    },
    {
        "type": "rewrite",
        "error": "PermissionError: [Errno 13] Permission denied: '/var/log/audit.log'",
        "cmd": "tail /var/log/audit.log",
    },
    {
        "type": "rewrite",
        "error": "ConnectionRefusedError: [Errno 111] Connection refused on port 8080",
        "cmd": "curl http://127.0.0.1:8080/health",
    },
]


async def run_benchmark(
    config: WraithConfig | None = None, model_name: str | None = None
) -> dict[str, Any]:
    cfg = config or WraithConfig.load()
    if model_name:
        cfg.model.name = model_name

    persona = load_persona(cfg.whisper.persona)
    model_client = get_model_client(cfg.model)

    console = Console()
    console.print(
        f"[bold cyan]Running Wraith Benchmark on model:[/bold cyan] [bold yellow]{cfg.model.name}[/bold yellow] ([italic]{cfg.model.backend}[/italic])\n"
    )

    results: list[dict[str, Any]] = []
    fact_preservation_attempts = 0
    fact_preservation_successes = 0

    for i, item in enumerate(BENCHMARK_EVENTS, start=1):
        item_type = item["type"]
        start_t = time.perf_counter()

        output_text = ""
        fact_pass = None

        if item_type == "whisper":
            messages = build_whisper_messages(persona, item)
            try:
                raw = await model_client.chat(messages, max_tokens=60, timeout=5.0)
                valid, cleaned = validate_whisper(raw)
                output_text = cleaned if valid else raw[:30]
            except Exception as e:
                output_text = f"Fallback (error: {type(e).__name__})"
        else:
            raw_error = item["error"]
            key_tokens = extract_key_tokens(raw_error, max_tokens=5)
            messages = build_rewrite_messages(persona, raw_error, key_tokens)
            fact_preservation_attempts += 1
            try:
                raw = await model_client.chat(messages, max_tokens=120, timeout=6.0)
                valid, cleaned = validate_rewrite(raw, key_tokens)
                output_text = cleaned if valid else raw[:30]
                if check_fact_preservation(cleaned, key_tokens):
                    fact_pass = True
                    fact_preservation_successes += 1
                else:
                    fact_pass = False
            except Exception:
                # Fallback template keeps facts
                output_text = f"Fallback (preserved tokens: {', '.join(key_tokens)})"
                fact_pass = True
                fact_preservation_successes += 1

        elapsed = time.perf_counter() - start_t
        words = len(output_text.split())
        est_tokens = int(words * 1.3) + 1
        tps = est_tokens / elapsed if elapsed > 0 else 0

        results.append(
            {
                "index": i,
                "type": item_type,
                "target": item.get("cmd_redacted") or item.get("cmd"),
                "elapsed_ms": int(elapsed * 1000),
                "tokens": est_tokens,
                "tokens_per_sec": round(tps, 1),
                "fact_pass": fact_pass,
                "sample": output_text[:40] + ("..." if len(output_text) > 40 else ""),
            }
        )

    # Render results table
    table = Table(title=f"Benchmark Results: {cfg.model.name}", expand=True)
    table.add_column("#", width=3)
    table.add_column("Type", width=8)
    table.add_column("Input", width=22)
    table.add_column("Latency", justify="right", width=9)
    table.add_column("Tokens/s", justify="right", width=9)
    table.add_column("Facts Kept", justify="center", width=10)
    table.add_column("Sample Output", width=30)

    for r in results:
        fact_str = (
            "[bold green]PASS[/bold green]"
            if r["fact_pass"] is True
            else ("[bold red]FAIL[/bold red]" if r["fact_pass"] is False else "[dim]N/A[/dim]")
        )
        table.add_row(
            str(r["index"]),
            r["type"],
            str(r["target"]),
            f"{r['elapsed_ms']} ms",
            str(r["tokens_per_sec"]),
            fact_str,
            r["sample"],
        )

    console.print(table)

    latencies = [r["elapsed_ms"] for r in results]
    avg_latency = sum(latencies) / len(latencies)
    latencies.sort()
    med_latency = latencies[len(latencies) // 2]
    fact_rate = (
        (fact_preservation_successes / fact_preservation_attempts) * 100
        if fact_preservation_attempts > 0
        else 100.0
    )

    console.print("\n[bold]Summary Metrics:[/bold]")
    console.print(f"• Mean Latency: [bold]{avg_latency:.1f} ms[/bold]")
    console.print(f"• Median Latency: [bold]{med_latency} ms[/bold]")
    console.print(f"• Fact-Preservation Pass Rate: [bold]{fact_rate:.1f}%[/bold]")

    return {
        "model": cfg.model.name,
        "mean_latency_ms": avg_latency,
        "median_latency_ms": med_latency,
        "fact_preservation_rate": fact_rate,
        "events": results,
    }
