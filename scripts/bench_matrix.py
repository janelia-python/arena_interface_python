"""Run a small benchmark matrix across host TCP socket-option variants."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

from arena_interface import ArenaInterface
from arena_interface.arena_interface import SERIAL_BAUDRATE

VARIANTS: dict[str, dict[str, bool]] = {
    "default": {"tcp_nodelay": True, "tcp_quickack": True},
    "no_quickack": {"tcp_nodelay": True, "tcp_quickack": False},
    "no_nodelay": {"tcp_nodelay": False, "tcp_quickack": True},
    "no_latency_tuning": {"tcp_nodelay": False, "tcp_quickack": False},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ArenaController host benchmark suite across multiple TCP socket variants."
    )
    parser.add_argument("--ethernet", default=None, help="Firmware Ethernet IP address")
    parser.add_argument("--serial", default=None, help="Serial port path")
    parser.add_argument("--baudrate", type=int, default=SERIAL_BAUDRATE, help="Serial baudrate")
    parser.add_argument("--debug", action="store_true", help="Enable debug prints")
    parser.add_argument("--label", default=None, help="Base label added to each run")
    parser.add_argument("--json-out", type=Path, default=None, help="Append each result object to this JSONL file")
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=sorted(VARIANTS),
        default=["default", "no_quickack", "no_nodelay", "no_latency_tuning"],
        help="Socket-option variants to execute",
    )
    parser.add_argument("--include-connect", action="store_true", help="Include TCP connect timing in each run")
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
    return parser


def variant_label(base_label: str | None, variant_name: str) -> str:
    return f"{base_label} [{variant_name}]" if base_label else variant_name


def print_summary(variant_name: str, suite: dict) -> None:
    cmd = suite["command_rtt"]
    spf = suite["spf_updates"]
    stream = suite.get("stream_frames")
    meta = suite.get("meta", {})
    quickack = meta.get("tcp_quickack_supported") and meta.get("tcp_quickack_requested")

    line = (
        f"{variant_name:>18} | cmd mean={cmd['mean_ms']:.3f} ms p99={cmd['p99_ms']:.3f} | "
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
    raise SystemExit("No transport selected. Provide --ethernet IP or --serial PORT.")


def main() -> int:
    args = build_parser().parse_args()

    print("variant               | command RTT               | SPF        | socket policy")
    print("----------------------+---------------------------+------------+-------------------------------")

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
            )
            if args.json_out is not None:
                ArenaInterface.write_bench_jsonl(str(args.json_out), suite)
            print_summary(variant_name, suite)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
