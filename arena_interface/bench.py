"""Benchmark helpers for ArenaController host interface.

These functions are intended to be callable from both the CLI and IPython.
They return structured results (dicts) instead of printing.
"""

from __future__ import annotations

import statistics
import time
from typing import Any, Sequence

from .arena_interface import ArenaInterface, RUNTIME_DURATION_PER_SECOND


def percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile on a *sorted* list."""
    if not sorted_values:
        return float("nan")
    if pct <= 0:
        return float(sorted_values[0])
    if pct >= 100:
        return float(sorted_values[-1])
    idx = int((pct / 100.0) * (len(sorted_values) - 1))
    return float(sorted_values[idx])


def summarize_rtts_ms(rtts_ms: Sequence[float]) -> dict[str, Any]:
    """Summarize RTT samples in milliseconds."""
    rtts_ms_sorted = sorted(float(x) for x in rtts_ms)
    if not rtts_ms_sorted:
        return {
            "samples": 0,
            "mean_ms": float("nan"),
            "min_ms": float("nan"),
            "p50_ms": float("nan"),
            "p95_ms": float("nan"),
            "p99_ms": float("nan"),
            "max_ms": float("nan"),
        }
    return {
        "samples": len(rtts_ms_sorted),
        "mean_ms": float(statistics.mean(rtts_ms_sorted)),
        "min_ms": float(rtts_ms_sorted[0]),
        "p50_ms": percentile(rtts_ms_sorted, 50),
        "p95_ms": percentile(rtts_ms_sorted, 95),
        "p99_ms": percentile(rtts_ms_sorted, 99),
        "max_ms": float(rtts_ms_sorted[-1]),
    }


def bench_command_rtt(
        arena_interface: ArenaInterface,
        iters: int = 2000,
        wrap_mode: bool = True,
) -> dict[str, Any]:
    """Measure host-side RTT for a small request/response command.

    This runs repeated `get_perf_stats()` calls and measures the host round-trip
    time. If `wrap_mode` is True, the test is bounded by ALL_ON/ALL_OFF to
    ensure firmware-side perf probes are active and a PERF_* report is emitted
    at mode end.
    """
    if wrap_mode:
        arena_interface.all_on()

    arena_interface.reset_perf_stats()

    rtts_ms: list[float] = []
    for _ in range(int(iters)):
        t0 = time.perf_counter_ns()
        arena_interface.get_perf_stats()
        t1 = time.perf_counter_ns()
        rtts_ms.append((t1 - t0) / 1e6)

    summary = summarize_rtts_ms(rtts_ms)

    if wrap_mode:
        arena_interface.all_off()

    return summary


def bench_spf_updates(
        arena_interface: ArenaInterface,
        rate_hz: float = 200.0,
        seconds: float = 5.0,
        pattern_id: int = 10,
        frame_min: int = 0,
        frame_max: int = 1000,
) -> dict[str, Any]:
    """Run a SHOW_PATTERN_FRAME + SET_FRAME_POSITION update loop.

    The mode window is bounded by SHOW_PATTERN_FRAME start and ALL_OFF end.
    Pair this with QS capture to compare device-side PERF_UPD kind=SPF and
    PERF_NET across firmware/network backends.
    """
    arena_interface.reset_perf_stats()

    # Some firmware builds use TRIAL_PARAMS.frame_rate as target_hz.
    arena_interface.show_pattern_frame(pattern_id, frame_min, frame_rate=int(rate_hz))

    start_ns = time.perf_counter_ns()
    end_ns = start_ns + int(float(seconds) * 1e9)
    period_ns = int(1e9 / float(rate_hz)) if rate_hz and rate_hz > 0 else 0

    deadline_ns = start_ns
    frame = int(frame_min)
    updates = 0

    while time.perf_counter_ns() < end_ns:
        arena_interface.update_pattern_frame(frame)
        updates += 1
        frame += 1
        if frame > int(frame_max):
            frame = int(frame_min)

        if period_ns:
            deadline_ns += period_ns
            while time.perf_counter_ns() < deadline_ns:
                pass

    arena_interface.all_off()

    elapsed_s = (time.perf_counter_ns() - start_ns) / 1e9
    achieved_hz = updates / elapsed_s if elapsed_s > 0 else 0.0
    return {
        "updates": updates,
        "elapsed_s": float(elapsed_s),
        "target_hz": float(rate_hz),
        "achieved_hz": float(achieved_hz),
    }


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
    """Run a STREAM_FRAME loop using `ArenaInterface.stream_frames`.

    `seconds` is converted into the library's 100ms runtime_duration ticks.
    """
    arena_interface.reset_perf_stats()

    runtime_duration = int(round(float(seconds) * float(RUNTIME_DURATION_PER_SECOND)))
    return arena_interface.stream_frames(
        str(pattern_path),
        float(frame_rate),
        runtime_duration,
        str(analog_out_waveform),
        float(analog_update_rate),
        float(analog_frequency),
        stream_cmd_coalesced=bool(stream_cmd_coalesced),
        progress_interval_s=float(progress_interval_s),
    )
