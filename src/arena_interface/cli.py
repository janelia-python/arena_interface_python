"""Command line interface for the ArenaController host tools."""

from __future__ import annotations

from pathlib import Path

import click

from .arena_interface import ArenaInterface, BENCH_IO_TIMEOUT_S, SERIAL_BAUDRATE


pass_arena_interface = click.make_pass_decorator(ArenaInterface)


def _print_phase_history(suite: dict) -> None:
    phases = suite.get("phases") or []
    if not phases:
        return

    click.echo("\n-- phases --")
    for phase in phases:
        line = (
            f"{phase.get('name')}: status={phase.get('status')} "
            f"elapsed_s={float(phase.get('elapsed_s', 0.0)):.3f}"
        )
        if phase.get("cleanup_status"):
            line += f" cleanup={phase.get('cleanup_status')}"
        if phase.get("error"):
            line += f" error={phase.get('error_type')}: {phase.get('error')}"
        click.echo(line)


def _print_suite_summary(
    suite: dict,
    *,
    include_connect: bool,
    stream_requested: bool,
) -> None:
    meta = suite.get("meta", {})
    click.echo(
        f"meta: label={meta.get('label')} host={meta.get('hostname')} "
        f"python={meta.get('python')} transport={meta.get('transport')} eth_ip={meta.get('ethernet_ip')} "
        f"io_timeout={meta.get('bench_io_timeout_s')} status={suite.get('status')}"
    )

    if include_connect and ("connect_time" in suite):
        ct = suite["connect_time"]
        click.echo("\n-- connect_time (TCP connect) --")
        click.echo(
            "iters={iters}  errors={errors}  mean={mean_ms:.3f} ms  min={min_ms:.3f}  p50={p50_ms:.3f}  "
            "p95={p95_ms:.3f}  p99={p99_ms:.3f}  max={max_ms:.3f}".format(**ct)
        )

    if "command_rtt" in suite:
        click.echo("\n-- command_rtt (get_perf_stats) --")
        cmd = suite["command_rtt"]
        click.echo(
            "iters={iters}  mean={mean_ms:.3f} ms  min={min_ms:.3f}  p50={p50_ms:.3f}  "
            "p95={p95_ms:.3f}  p99={p99_ms:.3f}  max={max_ms:.3f}  reconnects={reconnects}".format(
                **cmd
            )
        )

    if "spf_updates" in suite:
        click.echo("\n-- spf_updates (show_pattern_frame + update_pattern_frame) --")
        spf = suite["spf_updates"]
        click.echo(
            "updates={updates}  elapsed_s={elapsed_s:.3f}  target={target_hz:.1f} Hz  achieved={achieved_hz:.1f} Hz  "
            "p99_update_rtt={p99:.3f} ms  reconnects={reconnects}".format(
                updates=spf["updates"],
                elapsed_s=spf["elapsed_s"],
                target_hz=spf["target_hz"],
                achieved_hz=spf["achieved_hz"],
                p99=spf["update_rtt_ms"]["p99_ms"],
                reconnects=spf["reconnects"],
            )
        )

    if stream_requested and ("stream_frames" in suite):
        click.echo("\n-- stream_frames --")
        st = suite["stream_frames"]

        extra = ""
        if isinstance(st.get("cmd_rtt_ms"), dict):
            cmd = st.get("cmd_rtt_ms") or {}
            send = st.get("send_ms") if isinstance(st.get("send_ms"), dict) else {}
            wait = st.get("response_wait_ms") if isinstance(st.get("response_wait_ms"), dict) else {}
            extra = "  rtt_p99={p99:.3f} ms (send_p99={sp99:.3f} ms wait_p99={wp99:.3f} ms)".format(
                p99=float(cmd.get("p99_ms", float("nan"))),
                sp99=float(send.get("p99_ms", float("nan"))),
                wp99=float(wait.get("p99_ms", float("nan"))),
            )

        click.echo(
            "frames={frames}  elapsed_s={elapsed_s:.3f}  rate={rate_hz:.1f} Hz  tx={tx_mbps:.2f} Mb/s  reconnects={reconnects}{extra}".format(
                frames=st.get("frames"),
                elapsed_s=st.get("elapsed_s"),
                rate_hz=st.get("rate_hz"),
                tx_mbps=st.get("tx_mbps"),
                reconnects=st.get("reconnects"),
                extra=extra,
            )
        )

    _print_phase_history(suite)

    warnings = suite.get("warnings") or []
    if warnings:
        click.echo("\n-- warnings --")
        for warning in warnings:
            click.echo(
                "{phase}: {wtype} {message}".format(
                    phase=warning.get("phase"),
                    wtype=warning.get("type"),
                    message=warning.get("message"),
                )
            )

    cleanup = suite.get("cleanup") or {}
    if cleanup.get("all_off_attempted"):
        click.echo(
            "\ncleanup: status={status} all_off_ok={ok} error={err}".format(
                status=cleanup.get("status"),
                ok=cleanup.get("all_off_ok"),
                err=cleanup.get("all_off_error"),
            )
        )


@click.group()
@click.option(
    "--ethernet",
    "ethernet_ip",
    envvar="ARENA_ETH_IP",
    default=None,
    help="Firmware Ethernet IP address (e.g. 192.168.10.104)",
)
@click.option(
    "--serial",
    "serial_port",
    envvar="ARENA_SERIAL_PORT",
    default=None,
    help="Serial port (e.g. COM3 or /dev/ttyACM0)",
)
@click.option(
    "--baudrate",
    default=SERIAL_BAUDRATE,
    show_default=True,
    help="Serial baudrate (only used with --serial)",
)
@click.option(
    "--tcp-nodelay/--no-tcp-nodelay",
    default=True,
    show_default=True,
    help="Enable TCP_NODELAY on Ethernet sockets.",
)
@click.option(
    "--tcp-quickack/--no-tcp-quickack",
    default=True,
    show_default=True,
    help="Request TCP_QUICKACK on Linux Ethernet sockets when available.",
)
@click.option("--debug/--no-debug", default=False, show_default=True)
@click.pass_context
def cli(
    ctx: click.Context,
    ethernet_ip: str | None,
    serial_port: str | None,
    baudrate: int,
    tcp_nodelay: bool,
    tcp_quickack: bool,
    debug: bool,
):
    """ArenaController host CLI."""
    ai = ArenaInterface(
        debug=debug,
        tcp_nodelay=tcp_nodelay,
        tcp_quickack=tcp_quickack,
    )

    if ethernet_ip and serial_port:
        raise click.UsageError("Choose only one transport: --ethernet or --serial")

    if ethernet_ip:
        ai.set_ethernet_mode(ethernet_ip)
    elif serial_port:
        ai.set_serial_mode(serial_port, baudrate=baudrate)
    else:
        raise click.UsageError(
            "No transport selected. Provide --ethernet IP or --serial PORT "
            "(or set ARENA_ETH_IP / ARENA_SERIAL_PORT)."
        )

    ctx.obj = ai
    ctx.call_on_close(ai.close)


@cli.command()
@pass_arena_interface
def all_off(arena_interface: ArenaInterface):
    """Turn all LEDs off."""
    arena_interface.all_off()


@cli.command()
@pass_arena_interface
def all_on(arena_interface: ArenaInterface):
    """Turn all LEDs on."""
    arena_interface.all_on()


@cli.command()
@click.argument("refresh_rate")
@pass_arena_interface
def set_refresh_rate(arena_interface: ArenaInterface, refresh_rate: str):
    """Set display refresh rate."""
    arena_interface.set_refresh_rate(int(refresh_rate))


@cli.command()
@pass_arena_interface
def display_reset(arena_interface: ArenaInterface):
    """Reset display."""
    arena_interface.display_reset()


@cli.command()
@click.argument("grayscale_index", type=int)
@pass_arena_interface
def switch_grayscale(arena_interface: ArenaInterface, grayscale_index: int):
    """Switch display grayscale mode.

    GRAYSCALE_INDEX:
      0 = binary
      1 = grayscale
    """
    arena_interface.switch_grayscale(int(grayscale_index))


@cli.command()
@pass_arena_interface
def reset_perf_stats(arena_interface: ArenaInterface):
    """Reset performance counters on the device."""
    arena_interface.reset_perf_stats()
    click.echo("OK")


@cli.command()
@pass_arena_interface
def get_perf_stats(arena_interface: ArenaInterface):
    """Fetch raw performance stats snapshot."""
    stats = arena_interface.get_perf_stats()
    # Print as hex so it's easy to copy/paste into analysis scripts.
    click.echo(stats.hex())


@cli.command()
@click.option(
    "--label",
    default=None,
    help="Optional label for this run (e.g. 'lab-switch-A / laptop-1'). Stored in JSON results.",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Append the full benchmark result object to this JSONL file.",
)
@click.option(
    "--include-connect/--no-include-connect",
    default=False,
    show_default=True,
    help="Include a TCP connect() timing test (Ethernet only).",
)
@click.option("--connect-iters", default=200, show_default=True, help="Iterations for connect() timing test")
@click.option("--cmd-iters", default=2000, show_default=True, help="Iterations for command RTT test")
@click.option(
    "--cmd-connect-mode",
    type=click.Choice(["persistent", "new_connection"], case_sensitive=False),
    default="persistent",
    show_default=True,
    help="Use a persistent socket or open/close a new TCP connection per command.",
)
@click.option("--spf-rate", default=200.0, show_default=True, help="Target Hz for update_pattern_frame loop")
@click.option("--spf-seconds", default=5.0, show_default=True, help="Seconds to run update_pattern_frame loop")
@click.option("--spf-pattern-id", default=10, show_default=True)
@click.option("--spf-frame-min", default=0, show_default=True)
@click.option("--spf-frame-max", default=1000, show_default=True)
@click.option(
    "--spf-pacing",
    type=click.Choice(["target", "max"], case_sensitive=False),
    default="target",
    show_default=True,
    help="'target' paces to --spf-rate, 'max' sends updates as fast as possible.",
)
@click.option(
    "--stream-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional .pattern or .pat file to stream",
)
@click.option("--stream-rate", default=200.0, show_default=True, help="Target FPS for stream_frames")
@click.option("--stream-seconds", default=5.0, show_default=True, help="Seconds to run stream_frames")
@click.option("--stream-coalesced/--stream-chunked", default=True, show_default=True)
@click.option("--progress-interval", default=1.0, show_default=True, help="Progress print interval (seconds)")
@click.option(
    "--io-timeout",
    default=BENCH_IO_TIMEOUT_S,
    show_default=True,
    help="Temporary per-read/connect timeout for the benchmark suite in seconds. Use 0 to disable.",
)
@pass_arena_interface
def bench(
    arena_interface: ArenaInterface,
    label: str | None,
    json_out: Path | None,
    include_connect: bool,
    connect_iters: int,
    cmd_iters: int,
    cmd_connect_mode: str,
    spf_rate: float,
    spf_seconds: float,
    spf_pattern_id: int,
    spf_frame_min: int,
    spf_frame_max: int,
    spf_pacing: str,
    stream_path: Path | None,
    stream_rate: float,
    stream_seconds: float,
    stream_coalesced: bool,
    progress_interval: float,
    io_timeout: float,
):
    """Run a small, repeatable host-side benchmark suite.

    Pair this with QS log capture so the device-side PERF_* records can be
    compared across firmware/network backends.
    """
    click.echo("\n=== ArenaInterface bench ===")

    suite = arena_interface.bench_suite(
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
        stream_path=str(stream_path) if stream_path is not None else None,
        stream_rate=float(stream_rate),
        stream_seconds=float(stream_seconds),
        stream_coalesced=bool(stream_coalesced),
        progress_interval_s=float(progress_interval),
        bench_io_timeout_s=float(io_timeout),
        status_callback=click.echo,
    )

    _print_suite_summary(
        suite,
        include_connect=bool(include_connect),
        stream_requested=stream_path is not None,
    )

    if json_out is not None:
        ArenaInterface.write_bench_jsonl(str(json_out), suite)
        click.echo(f"\nappended JSONL: {json_out}")

    if suite.get("status") == "error":
        error = suite.get("error") or {}
        raise click.ClickException(
            "benchmark failed in {phase}: {etype}: {message}".format(
                phase=error.get("phase"),
                etype=error.get("type"),
                message=error.get("message"),
            )
        )

    if suite.get("status") == "ok_cleanup_failed":
        click.echo(
            "\nBench done with a cleanup warning. Measured results were kept; review the cleanup diagnostics and keep the QSPY log.\n"
        )
        return

    click.echo("\nBench done. Capture the QS PERF_* lines to compare device-side timings.\n")


if __name__ == "__main__":
    cli()
