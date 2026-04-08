"""PyVISA connection helpers for USB-TMC Hantek DSO2000 scopes."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyvisa.resources


def visa_backend() -> str:
    return os.environ.get("DSO2D15_VISA_BACKEND", "@py")


def default_resource_query() -> str:
    # Matches Hantek DSO2000 USB identifiers used by community tools (see README).
    return os.environ.get("DSO2D15_VISA_QUERY", "USB0::1183::20574:?*")


def default_resource_string() -> str | None:
    v = os.environ.get("DSO2D15_VISA", "").strip()
    return v or None


def get_resource_manager():
    import pyvisa

    return pyvisa.ResourceManager(visa_backend())


def list_usb_candidates() -> list[str]:
    rm = get_resource_manager()
    q = default_resource_query()
    try:
        return list(rm.list_resources(q))
    except ValueError:
        return []


def open_instrument(resource: str | None = None, timeout_ms: int | None = None):
    """
    Open the scope. If resource is None, use DSO2D15_VISA or the single match
    from DSO2D15_VISA_QUERY (must be exactly one device).
    """
    import pyvisa

    rm = get_resource_manager()
    addr = resource or default_resource_string()
    if not addr:
        candidates = list_usb_candidates()
        if len(candidates) != 1:
            raise RuntimeError(
                "Set DSO2D15_VISA to the full VISA resource string, or connect "
                f"exactly one scope matching {default_resource_query()!r}. "
                f"Found: {candidates!r}"
            )
        addr = candidates[0]
    inst: pyvisa.resources.MessageBasedResource = rm.open_resource(addr)
    to = timeout_ms if timeout_ms is not None else int(os.environ.get("DSO2D15_TIMEOUT_MS", "120000"))
    inst.timeout = to
    inst.encoding = "utf-8"
    return inst
