"""Run a small benchmark matrix across host TCP socket-option variants."""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

from arena_interface import ArenaInterface
from arena_interface.arena_interface import BENCH_IO_TIMEOUT_S, SERIAL_BAUDRATE

VARIANTS: dict[str, dict[str, bool]] = {
    "default": {"tcp_nodelay": True, "tcp_quickack": True},
    "windows_like": {"tcp_nodelay": True, "tcp_quickack": False},
    "no_quickack": {"tcp_nodelay": True, "tcp_quickack": False},
    "no_nodelay": {"tcp_nodelay": False, "tcp_quickack": True},
    "no_latency_tuning": {"tcp_nodelay": False, "tcp_quickack": False},
}

COMPARISON_METRICS: tuple[tuple[str, str, str], ...] = (
    ("stream_rate_hz", "stream rate", "Hz"),
    ("stream_tx_mbps", "stream TX", "Mb/s"),
    ("spf_achieved_hz", "SPF achieved", "Hz"),
    ("cmd_mean_ms", "command RTT mean", "ms"),
    ("cmd_p99_ms", "command RTT p99", "ms"),
)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the ArenaController host benchmark suite across multiple "
            "TCP socket variants."
        )
    )
    parser.add_argument(
        "--ethernet",
        default=os.environ.get("ARENA_ETH_IP"),
        help="Firmware Ethernet IP address (defaults to ARENA_ETH_IP)",
    )
    parser.add_argument(
        "--serial",
        default=os.environ.get("ARENA_SERIAL_PORT"),
        help="Serial port path (defaults to ARENA_SERIAL_PORT)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=_env_int("ARENA_SERIAL_BAUDRATE", SERIAL_BAUDRATE),
        help="Serial baudrate (defaults to ARENA_SERIAL_BAUDRATE or 115200)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug prints")
    parser.add_argument("--label", default=None, help="Base label added to each run")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Append each result object to this JSONL file",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=sorted(VARIANTS),
        default=["default", "windows_like", "no_nodelay", "no_latency_tuning"],
        help="Socket-option variants to execute",
    )
    parser.add_argument(
        "--include-connect",
        action="store_true",
        help="Include TCP connect timing in each run",
    )
    parser.add_argument("--connect-iters", type=int, default=200)
    parser.add_argument("--cmd-iters", type=int, default=2000)
    parser.add_argument(
        "--cmd-connect-mode",
        choices=["persistent", "new_connection"],
        default="persistent",
    )
    parser.add_argument("--spf-rate", type=float, default=200.0)
    parser.add_argument("--spf-seconds", type=float, default=5.0)
    parser.add_argument("--spf-pattern-id", type=int, default=10)
    parser.add_argument("--spf-frame-min", type=int, default=0)
    parser.add_argument("--spf-frame-max", type=int, default=1000)
    parser.add_argument("--spf-pacing", choices=["target", "max"], default="target")
    parser.add_argument("--stream-path", type=Path, default=None)
    parser.add_argument("--stream-rate", type=float, default=200.0)
    parser.add_argument("--stream-seconds", type=float, default=5.0)
    parser.add_argument("--stream-coalesced", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--progress-interval", type=float, default=1.0)
    parser.add_argument(
        "--io-timeout",
        type=float,
        default=BENCH_IO_TIMEOUT_S,
        help="Temporary per-read/connect timeout for each suite run in seconds. Use 0 to disable.",
    )
    return parser


def _display_variant_name(variant_name: str) -> str:
    return variant_name.replace("_", "-")


def variant_label(base_label: str | None, variant_name: str) -> str:
    pretty_name = _display_variant_name(variant_name)
    return f"{base_label} [{pretty_name}]" if base_label else pretty_name


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _suite_metric(suite: dict, metric_name: str) -> float | None:
    if metric_name == "cmd_mean_ms":
        value = (suite.get("command_rtt") or {}).get("mean_ms")
    elif metric_name == "cmd_p99_ms":
        value = (suite.get("command_rtt") or {}).get("p99_ms")
    elif metric_name == "spf_achieved_hz":
        value = (suite.get("spf_updates") or {}).get("achieved_hz")
    elif metric_name == "stream_rate_hz":
        value = (suite.get("stream_frames") or {}).get("rate_hz")
    elif metric_name == "stream_tx_mbps":
        value = (suite.get("stream_frames") or {}).get("tx_mbps")
    else:  # pragma: no cover - defensive guard
        raise KeyError(metric_name)
    if not _is_finite_number(value):
        return None
    return float(value)


def _format_metric_delta(delta: float, pct: float | None, unit: str) -> str:
    magnitude = f"{delta:+.3f} {unit}"
    if unit == "Hz":
        magnitude = f"{delta:+.1f} {unit}"
    elif unit == "Mb/s":
        magnitude = f"{delta:+.2f} {unit}"
    if pct is None:
        return magnitude
    return f"{magnitude} ({pct:+.1f}%)"


def print_delta_summary(successful_suites: list[tuple[str, dict]]) -> None:
    if len(successful_suites) < 2:
        return

    baseline_name, baseline_suite = next(
        ((name, suite) for name, suite in successful_suites if name == "default"),
        successful_suites[0],
    )

    print("")
    print(f"relative to baseline: {_display_variant_name(baseline_name)}")
    for variant_name, suite in successful_suites:
        if variant_name == baseline_name:
            continue
        bits: list[str] = []
        for metric_name, label, unit in COMPARISON_METRICS:
            baseline_value = _suite_metric(baseline_suite, metric_name)
            current_value = _suite_metric(suite, metric_name)
            if baseline_value is None or current_value is None:
                continue
            delta = current_value - baseline_value
            pct = None if baseline_value == 0 else (delta / baseline_value) * 100.0
            bits.append(f"{label} {_format_metric_delta(delta, pct, unit)}")
        if bits:
            print(f"- {_display_variant_name(variant_name)}: " + "; ".join(bits))


def print_summary(variant_name: str, suite: dict) -> None:
    meta = suite.get("meta", {})
    quickack = meta.get("tcp_quickack_supported") and meta.get("tcp_quickack_requested")
    status = suite.get("status", "unknown")
    variant_display = _display_variant_name(variant_name)

    if status == "error":
        error = suite.get("error") or {}
        print(
            f"{variant_display:>18} | FAILED {error.get('phase')} "
            f"{error.get('type')}: {error.get('message')}"
        )
        return

    cmd = suite["command_rtt"]
    spf = suite["spf_updates"]
    stream = suite.get("stream_frames")

    line = (
        f"{variant_display:>18} | status={status} cmd mean={cmd['mean_ms']:.3f} ms "
        f"p99={cmd['p99_ms']:.3f} | "
        f"spf={spf['achieved_hz']:.1f} Hz | nodelay={meta.get('tcp_nodelay')} quickack={quickack}"
    )
    if isinstance(stream, dict):
        line += f" | stream={stream.get('rate_hz', float('nan')):.1f} Hz"
    print(line)


def configure_transport(ai: ArenaInterface, args: argparse.Namespace) -> None:
    if args.ethernet and args.serial:
        raise SystemExit("Choose only one transport: --ethernet or --serial")
    if args.ethernet:
        ai.set_ethernet_mode(args.ethernet)
        return
    if args.serial:
        ai.set_serial_mode(args.serial, baudrate=args.baudrate)
        return
    raise SystemExit(
        "No transport selected. Provide --ethernet IP or --serial PORT, "
        "or set ARENA_ETH_IP / ARENA_SERIAL_PORT."
    )


def main() -> int:
    args = build_parser().parse_args()
    exit_code = 0
    successful_suites: list[tuple[str, dict]] = []

    print("variant               | command RTT               | SPF        | socket policy")
    print(
        "----------------------+---------------------------+------------+"
        "-------------------------------"
    )

    for variant_name in args.variants:
        variant = VARIANTS[variant_name]
        with ArenaInterface(
            debug=args.debug,
            tcp_nodelay=variant["tcp_nodelay"],
            tcp_quickack=variant["tcp_quickack"],
        ) as ai:
            configure_transport(ai, args)
            suite = ai.bench_suite(
                label=variant_label(args.label, variant_name),
                include_connect=bool(args.include_connect),
                connect_iters=int(args.connect_iters),
                cmd_iters=int(args.cmd_iters),
                cmd_connect_mode=str(args.cmd_connect_mode),
                spf_rate=float(args.spf_rate),
                spf_seconds=float(args.spf_seconds),
                spf_pattern_id=int(args.spf_pattern_id),
                spf_frame_min=int(args.spf_frame_min),
                spf_frame_max=int(args.spf_frame_max),
                spf_pacing=str(args.spf_pacing),
                stream_path=str(args.stream_path) if args.stream_path else None,
                stream_rate=float(args.stream_rate),
                stream_seconds=float(args.stream_seconds),
                stream_coalesced=bool(args.stream_coalesced),
                progress_interval_s=float(args.progress_interval),
                bench_io_timeout_s=float(args.io_timeout),
                status_callback=print,
            )
            if args.json_out is not None:
                ArenaInterface.write_bench_jsonl(str(args.json_out), suite)
            print_summary(variant_name, suite)
            if suite.get("status") == "error":
                exit_code = 1
            else:
                successful_suites.append((variant_name, suite))

    print_delta_summary(successful_suites)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
