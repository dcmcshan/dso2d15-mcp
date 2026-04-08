"""
Fetch and decode waveforms from DSO2000-family scopes via PRIVate:WAVeform:DATA:ALL?

Logic adapted from the community tool:
https://github.com/phmarek/hantek-dso2000 (MIT) — thank you, Petr Marek.
"""

from __future__ import annotations

import struct
from typing import Any


def _read_waveform_packets(inst) -> tuple[bytes, bytes, int]:
    """Return (meta_99_bytes, samples_buffer, points_from_acquire)."""
    points = int(inst.query("ACQuire:POINts?").strip())

    samples_data = bytes()
    samples_total = -1
    samples_got = 0
    meta = bytes()

    def read_packet() -> bool:
        nonlocal samples_total, samples_data, samples_got, meta
        inst.write("PRIVate:WAVeform:DATA:ALL?\n")
        inp = inst.read_raw()
        if not inp or chr(inp[0]) != "#" or chr(inp[1]) != "9":
            raise RuntimeError(
                f"Unexpected waveform packet header: first bytes={inp[:16]!r} "
                "(expected binary block starting with #9…)"
            )

        this_len = int(inp[2:11].decode())
        if this_len == 0:
            return False

        total_smpls = int(inp[11:20].decode())
        cur_pos = int(inp[20:29].decode())

        start = 29
        end_of_meta = 128

        if samples_total == -1:
            samples_total = total_smpls
            samples_data = bytearray(samples_total)
            meta = inp[start:end_of_meta]
        else:
            if samples_total != total_smpls:
                raise RuntimeError("Inconsistent total sample count across packets")

        cur_len = len(inp) - end_of_meta
        for i in range(0, cur_len):
            samples_data[cur_pos + i] = inp[end_of_meta + i]
        samples_got += cur_len
        return samples_got >= samples_total

    while not read_packet():
        pass

    return meta, bytes(samples_data), points


def _channel_samples(chan: int, data: bytes, block_len: int, channel_count: int) -> list[int]:
    samples: list[int] = []
    for i in range((chan - 1) * block_len, len(data), block_len * channel_count):
        chunk = data[i : i + block_len]
        if len(chunk) < block_len:
            break
        samples.extend(struct.unpack("%db" % block_len, chunk))
    return samples


def _absolute_voltages(inst, channel: dict[str, Any], grid_y: float = 25.0) -> list[float]:
    ch = channel["channel"]
    off = float(inst.query(f":CHANnel{ch}:OFFSet?").strip())
    probe = float(inst.query(f":CHANnel{ch}:PROBe?").strip())
    scale = float(inst.query(f":CHANnel{ch}:SCALe?").strip())
    channel["offset"] = off
    channel["probe"] = probe
    channel["scale"] = scale
    return [v / grid_y * scale - off for v in channel["samples"]]


def _channel_meta(
    inst,
    chan: int,
    volt: bytes,
    en: bytes,
    samples_data: bytes,
    points: int,
    channel_count: int,
    block_len: int,
) -> dict[str, Any]:
    res: dict[str, Any] = {
        "channel": chan,
        "enable": en == b"1",
        "voltage_nominal": float(volt),
    }
    if res["enable"]:
        res["samples"] = _channel_samples(chan, samples_data, block_len, channel_count)
        res["voltage"] = _absolute_voltages(inst, res)
    return res


def read_waveform(inst, block_len: int = 2000) -> dict[str, Any]:
    """
    Read full waveform snapshot (all enabled channels). Returns a JSON-serializable dict.
    """
    meta, samples_data, points = _read_waveform_packets(inst)

    res = struct.unpack("cc 16x 7s7s7s7s cccc 9s 6s 9x 9s 6s 10x", meta)
    (
        running,
        trigger,
        v1,
        v2,
        v3,
        v4,
        c1e,
        c2e,
        c3e,
        c4e,
        sampling_rate,
        sampling_multiple,
        trigger_time,
        acq_start,
    ) = res

    channel_count = int(c1e) + int(c2e) + int(c3e) + int(c4e)
    channels = [
        _channel_meta(inst, 1, v1, c1e, samples_data, points, channel_count, block_len),
        _channel_meta(inst, 2, v2, c2e, samples_data, points, channel_count, block_len),
        _channel_meta(inst, 3, v3, c3e, samples_data, points, channel_count, block_len),
        _channel_meta(inst, 4, v4, c4e, samples_data, points, channel_count, block_len),
    ]

    return {
        "running": running == b"1",
        "trigger": trigger == b"1",
        "channels": channels,
        "samples": points,
        "sampling_rate": float(sampling_rate),
        "sampling_multiple": float(sampling_multiple),
        "trigger_time": float(trigger_time),
        "acq_start": float(acq_start),
    }


def truncate_waveform(wave: dict[str, Any], max_points: int) -> dict[str, Any]:
    """Return a copy with per-channel voltage/sample arrays truncated to max_points."""
    import copy

    out = copy.deepcopy(wave)
    for ch in out.get("channels", []):
        if not ch.get("enable"):
            continue
        truncated = False
        for key in ("voltage", "samples"):
            arr = ch.get(key)
            if isinstance(arr, list) and len(arr) > max_points:
                ch[key] = arr[:max_points]
                truncated = True
        if truncated:
            ch["truncated"] = True
    return out
