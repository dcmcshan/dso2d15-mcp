#!/usr/bin/env python3
"""CLI: Vpp/Freq + SVG snapshot (same logic as MCP dso2d15_measure_snapshot)."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dso2d15_mcp.connection import open_instrument
from dso2d15_mcp.measurements import (
    measure_vpp_frequency_scipi,
    try_scpi_screen_bitmap,
    waveform_derived_metrics,
    write_waveform_svg,
)
from dso2d15_mcp.waveform import read_waveform, truncate_waveform


def main() -> int:
    ch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out: dict = {}
    tmpdir = os.environ.get("DSO2D15_SNAPSHOT_DIR") or "/tmp"
    os.makedirs(tmpdir, exist_ok=True)
    inst = open_instrument()
    try:
        out["measure_scpi"] = measure_vpp_frequency_scipi(inst, channel=ch)
        wave = truncate_waveform(read_waveform(inst), 4000)
        out["waveform_derived"] = waveform_derived_metrics(wave, channel=ch)
        svg = os.path.join(tmpdir, f"dso2d15_waveform_{ch}.svg")
        out["waveform_svg_path"] = write_waveform_svg(wave, svg, channel=ch)
        bmp = try_scpi_screen_bitmap(inst)
        if bmp:
            p = os.path.join(tmpdir, f"dso2d15_screen_{ch}.bmp")
            with open(p, "wb") as f:
                f.write(bmp)
            out["screenshot_bmp_path"] = p
        else:
            out["screenshot_bmp_path"] = None
    finally:
        inst.close()
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
