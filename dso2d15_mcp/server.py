"""MCP server: Hantek DSO2D15 (DSO2000) USB SCPI via PyVISA."""

from __future__ import annotations

import json
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from dso2d15_mcp.connection import (
    default_resource_query,
    get_resource_manager,
    list_usb_candidates,
    open_instrument,
)
from dso2d15_mcp.waveform import read_waveform, truncate_waveform

mcp = FastMCP(
    "DSO2D15",
    instructions="Hantek DSO2D15 / DSO2000 oscilloscope over USB (SCPI via PyVISA).",
)


def _err(e: Exception) -> str:
    return f"DSO2D15 error: {type(e).__name__}: {e}"


@mcp.tool()
def dso2d15_list_visa_resources(query: str = "?*") -> str:
    """
    List VISA resource strings visible to PyVISA. Default query is all resources (?*).
    For Hantek-only filtering, try query USB0::1183::20574:?* or set env DSO2D15_VISA_QUERY.
    """
    try:
        rm = get_resource_manager()
        r = list(rm.list_resources(query))
        return "\n".join(r) if r else "(no resources matched)"
    except ValueError as e:
        return f"No resources for query {query!r}: {e}"
    except Exception as e:
        return _err(e)


@mcp.tool()
def dso2d15_list_hantek_candidates() -> str:
    """List USB resources matching the default Hantek DSO2000 pattern (env DSO2D15_VISA_QUERY)."""
    try:
        c = list_usb_candidates()
        q = default_resource_query()
        if not c:
            return f"No devices matched {q!r}. Check USB, driver, and try dso2d15_list_visa_resources."
        return "Query: " + q + "\n" + "\n".join(c)
    except Exception as e:
        return _err(e)


@mcp.tool()
def dso2d15_identify(resource: str | None = None) -> str:
    """Send *IDN? to the scope. Optionally pass a full VISA resource string; else use DSO2D15_VISA or auto-detect."""
    try:
        inst = open_instrument(resource)
        with inst:
            return inst.query("*IDN?").strip()
    except Exception as e:
        return _err(e)


@mcp.tool()
def dso2d15_scpi_write(command: str, resource: str | None = None) -> str:
    """
    Write a SCPI command (no response expected). Do not include a trailing newline.
    Example: :CHANnel1:SCALe 1.0
    """
    try:
        inst = open_instrument(resource)
        with inst:
            inst.write(command.strip())
            return "OK"
    except Exception as e:
        return _err(e)


@mcp.tool()
def dso2d15_scpi_query(command: str, resource: str | None = None) -> str:
    """
    Query the scope (command should end with ?). Returns stripped ASCII response.
    For binary/block data use dso2d15_scpi_query_binary instead.
    """
    try:
        inst = open_instrument(resource)
        with inst:
            return inst.query(command.strip()).strip()
    except Exception as e:
        return _err(e)


@mcp.tool()
def dso2d15_scpi_query_binary(
    command: str,
    resource: str | None = None,
    max_preview_bytes: int = 256,
) -> str:
    """
    Write a command that returns a binary block (e.g. waveform). Returns JSON with:
    byte_length, sha256_hex (if hashlib available), and base64_preview (first max_preview_bytes).
    """
    import base64
    import hashlib

    try:
        inst = open_instrument(resource)
        with inst:
            c = command.strip()
            if not c.endswith("\n"):
                c = c + "\n"
            inst.write(c)
            raw: bytes = inst.read_raw()
        prev = raw[: max(0, max_preview_bytes)]
        out: dict[str, Any] = {
            "byte_length": len(raw),
            "base64_preview": base64.b64encode(prev).decode("ascii"),
        }
        try:
            out["sha256"] = hashlib.sha256(raw).hexdigest()
        except Exception:
            pass
        return json.dumps(out, indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def dso2d15_fetch_waveform(
    resource: str | None = None,
    max_points_per_channel: int = 4000,
    block_len: int = 2000,
) -> str:
    """
    Acquire waveform data using PRIVate:WAVeform:DATA:ALL? (DSO2000 family).
    Returns JSON with per-channel voltage arrays (truncated to max_points_per_channel to keep MCP payloads reasonable).
    Large memory depths can take tens of seconds — timeout defaults to 120s (env DSO2D15_TIMEOUT_MS).
    """
    try:
        inst = open_instrument(resource)
        with inst:
            wave = read_waveform(inst, block_len=block_len)
        wave = truncate_waveform(wave, max_points_per_channel)
        return json.dumps(wave, indent=2)
    except Exception as e:
        return _err(e)


def main() -> int:
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
