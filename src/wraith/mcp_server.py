"""Wraith Model Context Protocol (MCP) server.

Provides local-only, read-only tools to allow any MCP client (like Antigravity)
to query recent shell haunts, inspect graveyard statistics, summon whispers,
and list installed personas.
"""

from __future__ import annotations

import json

from wraith.config import WraithConfig
from wraith.crypt import get_crypt_whisper
from wraith.graveyard import Graveyard
from wraith.personas import list_personas as get_personas_list
from wraith.personas import load_persona
from wraith.redact import redact
from wraith.triggers import is_dangerous_command


def create_mcp_server():
    """Create and configure the read-only Wraith MCP server."""
    try:
        from mcp.server.mcpserver import MCPServer

        server = MCPServer("wraith")
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP

            server = FastMCP("wraith")
        except ImportError:
            raise RuntimeError(
                "MCP SDK is not installed. Install via pip install 'wraith-haunt[mcp]'"
            )

    graveyard = Graveyard()

    @server.tool()
    def recent_haunts(limit: int = 20) -> str:
        """Return the latest recorded shell haunts with sensitive data redacted."""
        limit = min(max(1, limit), 100)
        haunts = graveyard.get_recent_haunts(limit=limit)
        return json.dumps(haunts, indent=2)

    @server.tool()
    def graveyard_stats() -> str:
        """Return aggregate statistics from the local shell history graveyard."""
        stats = graveyard.get_stats()
        return json.dumps(stats, indent=2)

    @server.tool()
    def summon_whisper(command: str, exit_code: int = 0) -> str:
        """Summon a ghostly whisper for a given shell command."""
        cfg = WraithConfig.load()
        sanitized = redact(command, cfg.privacy.redact_patterns)
        is_danger = is_dangerous_command(sanitized)
        trigger = (
            "dangerous_command"
            if is_danger
            else ("command_not_found" if exit_code == 127 else "ambient")
        )
        whisper = get_crypt_whisper(cfg.whisper.persona, trigger)
        glyph = load_persona(cfg.whisper.persona).ghost_glyph
        return f"{glyph} {whisper}"

    @server.tool()
    def list_personas() -> str:
        """List all installed and bundled ghostly personas."""
        personas = get_personas_list()
        return json.dumps(personas, indent=2)

    return server


def run_mcp_server() -> None:
    """Run the MCP server over stdio transport."""
    server = create_mcp_server()
    if hasattr(server, "run"):
        server.run()


if __name__ == "__main__":
    run_mcp_server()
