"""VPP / frequency via SCPI MEASure; optional waveform-derived estimates; SVG snapshot."""

from __future__ import annotations

import os
import re
from typing import Any


def _parse_item_value(response: str) -> float | None:
    """Parse reply like 'VPP 3.600e-01' or 'FREQuency 1.000e+03'."""
    s = response.strip()
    if not s:
        return None
    parts = s.split()
    try:
        return float(parts[-1])
    except (ValueError, IndexError):
        m = re.search(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?", s)
        return float(m.group(0)) if m else None


def measure_vpp_frequency_scipi(inst, channel: int = 1) -> dict[str, Any]:
    """Use :MEASure:CHANnel<n>:ITEM? VPP and FREQuency (DSO2000 manual)."""
    ch = int(channel)
    if ch not in (1, 2, 3, 4):
        raise ValueError("channel must be 1–4")
    inst.write(":MEASure:ENABle ON")
    inst.write(f":MEASure:SOURce CHANnel{ch}")
    inst.write(":MEASure:ADISplay ON")
    vpp_raw = inst.query(f":MEASure:CHANnel{ch}:ITEM? VPP").strip()
    freq_raw = inst.query(f":MEASure:CHANnel{ch}:ITEM? FREQuency").strip()
    return {
        "channel": ch,
        "vpp_raw": vpp_raw,
        "frequency_hz_raw": freq_raw,
        "vpp_V": _parse_item_value(vpp_raw),
        "frequency_Hz": _parse_item_value(freq_raw),
    }


def estimate_freq_from_voltage(v: list[float], sample_rate_hz: float) -> float | None:
    """Rough dominant period via threshold crossings at the waveform mean."""
    n = len(v)
    if n < 16 or sample_rate_hz <= 0:
        return None
    mean = sum(v) / n
    # Rising edges through mean
    crossings: list[int] = []
    for i in range(1, n):
        if v[i - 1] < mean <= v[i] or v[i - 1] > mean >= v[i]:
            crossings.append(i)
    if len(crossings) < 3:
        return None
    # Full periods ≈ distance between every other crossing for sine
    periods = [crossings[i + 2] - crossings[i] for i in range(0, len(crossings) - 2, 1)]
    if not periods:
        return None
    periods.sort()
    med = periods[len(periods) // 2]
    if med <= 0:
        return None
    return sample_rate_hz / med


def waveform_derived_metrics(wave: dict[str, Any], channel: int = 1) -> dict[str, Any]:
    """Vpp and estimated freq from read_waveform() JSON-like dict."""
    sr = float(wave.get("sampling_rate") or 0)
    for ch in wave.get("channels") or []:
        if ch.get("channel") != channel:
            continue
        if not ch.get("enable"):
            return {"channel": channel, "error": "channel disabled"}
        volt = ch.get("voltage") or []
        if not volt:
            return {"channel": channel, "error": "no voltage array"}
        vmin, vmax = min(volt), max(volt)
        vpp = vmax - vmin
        fest = estimate_freq_from_voltage(volt, sr)
        return {
            "channel": channel,
            "vpp_from_waveform_V": vpp,
            "frequency_from_waveform_Hz": fest,
            "samples_used": len(volt),
            "sampling_rate_Hz": sr,
        }
    return {"channel": channel, "error": "channel not found"}


def try_scpi_screen_bitmap(inst, timeout_ms: int = 8000) -> bytes | None:
    """
    Best-effort raw reads (not in DSO2000 public manual). Returns bytes if BMP-like.
    """
    old = inst.timeout
    inst.timeout = timeout_ms
    candidates = (
        ":DISPlay:DATA?",
        ":HCOPy:SDUMp:DATA?",
        ":SAVE:IMAGe:DATA?",
    )
    try:
        for cmd in candidates:
            try:
                inst.write(cmd if cmd.endswith("\n") else cmd + "\n")
                raw = inst.read_raw()
                if len(raw) > 100 and raw[:2] == b"BM":
                    return raw
            except Exception:
                continue
        return None
    finally:
        inst.timeout = old


def write_waveform_svg(
    wave: dict[str, Any],
    path: str,
    channel: int = 1,
    width: int = 800,
    height: int = 480,
) -> str | None:
    """Write a simple SVG of one channel's voltage vs time (screen substitute)."""
    sr = float(wave.get("sampling_rate") or 1.0)
    tt = float(wave.get("trigger_time") or 0.0)
    for ch in wave.get("channels") or []:
        if ch.get("channel") != channel or not ch.get("enable"):
            continue
        volt = ch.get("voltage") or []
        if len(volt) < 2:
            return None
        n = len(volt)
        t0 = -tt
        times = [t0 + i / sr for i in range(n)]
        vmin, vmax = min(volt), max(volt)
        pad = 0.05 * (vmax - vmin or 1.0)
        y0, y1 = vmin - pad, vmax + pad
        x0, x1 = times[0], times[-1]

        def sx(tx: float) -> float:
            return (tx - x0) / (x1 - x0 or 1e-9) * (width - 40) + 20

        def sy(vy: float) -> float:
            return height - 20 - (vy - y0) / (y1 - y0 or 1e-9) * (height - 40)

        pts = " ".join(f"{sx(t):.2f},{sy(v):.2f}" for t, v in zip(times, volt))
        svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#1a1a1a"/>
  <polyline fill="none" stroke="#00e676" stroke-width="1.5" points="{pts}"/>
  <text x="20" y="24" fill="#aaa" font-size="14" font-family="system-ui">CH{channel} (DSO2D15 waveform)</text>
</svg>
"""
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        return path
    return None
