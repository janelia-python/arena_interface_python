"""Benchmark helpers for ArenaController host interface.

Preferred API
-------------
Use the instance methods on :class:`arena_interface.ArenaInterface`:

- ``ai.bench_command_rtt(...)``
- ``ai.bench_spf_updates(...)``
- ``ai.bench_stream_frames(...)``
- ``ai.bench_suite(...)``

This module keeps thin wrapper functions for backwards compatibility and for
use from scripts/CLI that prefer functional-style calls.
"""

from __future__ import annotations

from typing import Any

from .arena_interface import ArenaInterface


def bench_connect_time(arena_interface: ArenaInterface, iters: int = 200) -> dict[str, Any]:
    return arena_interface.bench_connect_time(iters=int(iters))


def bench_command_rtt(
        arena_interface: ArenaInterface,
        iters: int = 2000,
        wrap_mode: bool = True,
        connect_mode: str = "persistent",
        warmup: int = 20,
) -> dict[str, Any]:
    return arena_interface.bench_command_rtt(
        iters=int(iters),
        wrap_mode=bool(wrap_mode),
        connect_mode=str(connect_mode),
        warmup=int(warmup),
    )


def bench_spf_updates(
        arena_interface: ArenaInterface,
        rate_hz: float = 200.0,
        seconds: float = 5.0,
        pattern_id: int = 10,
        frame_min: int = 0,
        frame_max: int = 1000,
        pacing: str = "target",
        warmup: int = 0,
) -> dict[str, Any]:
    return arena_interface.bench_spf_updates(
        rate_hz=float(rate_hz),
        seconds=float(seconds),
        pattern_id=int(pattern_id),
        frame_min=int(frame_min),
        frame_max=int(frame_max),
        pacing=str(pacing),
        warmup=int(warmup),
    )


def bench_stream_frames(
        arena_interface: ArenaInterface,
        pattern_path: str,
        frame_rate: float = 200.0,
        seconds: float = 5.0,
        stream_cmd_coalesced: bool = True,
        progress_interval_s: float = 1.0,
        analog_out_waveform: str = "constant",
        analog_update_rate: float = 1.0,
        analog_frequency: float = 0.0,
) -> dict[str, Any]:
    return arena_interface.bench_stream_frames(
        pattern_path=str(pattern_path),
        frame_rate=float(frame_rate),
        seconds=float(seconds),
        stream_cmd_coalesced=bool(stream_cmd_coalesced),
        progress_interval_s=float(progress_interval_s),
        analog_out_waveform=str(analog_out_waveform),
        analog_update_rate=float(analog_update_rate),
        analog_frequency=float(analog_frequency),
    )


def bench_suite(
        arena_interface: ArenaInterface,
        label: str | None = None,
        *,
        include_connect: bool = False,
        connect_iters: int = 200,
        cmd_iters: int = 2000,
        cmd_connect_mode: str = "persistent",
        spf_rate: float = 200.0,
        spf_seconds: float = 5.0,
        spf_pattern_id: int = 10,
        spf_frame_min: int = 0,
        spf_frame_max: int = 1000,
        spf_pacing: str = "target",
        stream_path: str | None = None,
        stream_rate: float = 200.0,
        stream_seconds: float = 5.0,
        stream_coalesced: bool = True,
        progress_interval_s: float = 1.0,
) -> dict[str, Any]:
    return arena_interface.bench_suite(
        label=label,
        include_connect=bool(include_connect),
        connect_iters=int(connect_iters),
        cmd_iters=int(cmd_iters),
        cmd_connect_mode=str(cmd_connect_mode),
        spf_rate=float(spf_rate),
        spf_seconds=float(spf_seconds),
        spf_pattern_id=int(spf_pattern_id),
        spf_frame_min=int(spf_frame_min),
        spf_frame_max=int(spf_frame_max),
        spf_pacing=str(spf_pacing),
        stream_path=str(stream_path) if stream_path else None,
        stream_rate=float(stream_rate),
        stream_seconds=float(stream_seconds),
        stream_coalesced=bool(stream_coalesced),
        progress_interval_s=float(progress_interval_s),
    )


def write_bench_jsonl(path: str, result: dict[str, Any]) -> None:
    ArenaInterface.write_bench_jsonl(path=str(path), result=result)
