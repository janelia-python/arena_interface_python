"""Command line interface for the ArenaController host tools."""

from __future__ import annotations

from pathlib import Path

import click

from .arena_interface import ArenaInterface, SERIAL_BAUDRATE
from .bench import bench_command_rtt, bench_spf_updates, bench_stream_frames


pass_arena_interface = click.make_pass_decorator(ArenaInterface)


@click.group()
@click.option(
    "--ethernet",
    "ethernet_ip",
    envvar="ARENA_ETH_IP",
    default=None,
    help="Firmware Ethernet IP address (e.g. 192.168.1.50)",
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
@click.option("--debug/--no-debug", default=False, show_default=True)
@click.pass_context
def cli(ctx: click.Context, ethernet_ip: str | None, serial_port: str | None, baudrate: int, debug: bool):
    """ArenaController host CLI."""
    ai = ArenaInterface(debug=debug)

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
@click.option("--cmd-iters", default=2000, show_default=True, help="Iterations for command RTT test")
@click.option("--spf-rate", default=200.0, show_default=True, help="Target Hz for update_pattern_frame loop")
@click.option("--spf-seconds", default=5.0, show_default=True, help="Seconds to run update_pattern_frame loop")
@click.option("--spf-pattern-id", default=10, show_default=True)
@click.option("--spf-frame-min", default=0, show_default=True)
@click.option("--spf-frame-max", default=1000, show_default=True)
@click.option(
    "--stream-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional .pattern file to stream",
)
@click.option("--stream-rate", default=200.0, show_default=True, help="Target FPS for stream_frames")
@click.option("--stream-seconds", default=5.0, show_default=True, help="Seconds to run stream_frames")
@click.option("--stream-coalesced/--stream-chunked", default=True, show_default=True)
@click.option("--progress-interval", default=1.0, show_default=True, help="Progress print interval (seconds)")
@pass_arena_interface
def bench(
    arena_interface: ArenaInterface,
    cmd_iters: int,
    spf_rate: float,
    spf_seconds: float,
    spf_pattern_id: int,
    spf_frame_min: int,
    spf_frame_max: int,
    stream_path: Path | None,
    stream_rate: float,
    stream_seconds: float,
    stream_coalesced: bool,
    progress_interval: float,
):
    """Run a small, repeatable host-side benchmark suite.

    Pair this with your QS log capture so the device-side PERF_* records can be
    compared across Ethernet backends.
    """
    click.echo("\n=== ArenaHost bench ===")

    # ------------------------------------------------------------------
    # Command RTT test (small request/response)
    # ------------------------------------------------------------------
    click.echo("\n-- command_rtt (get_perf_stats) --")
    cmd_summary = bench_command_rtt(arena_interface, iters=cmd_iters, wrap_mode=True)
    click.echo(
        "samples={samples}  mean={mean_ms:.3f} ms  min={min_ms:.3f}  p50={p50_ms:.3f}  "
        "p95={p95_ms:.3f}  p99={p99_ms:.3f}  max={max_ms:.3f}".format(**cmd_summary)
    )

    # ------------------------------------------------------------------
    # SPF (Show Pattern Frame) update loop
    # ------------------------------------------------------------------
    click.echo("\n-- spf_update (show_pattern_frame + update_pattern_frame loop) --")
    spf_stats = bench_spf_updates(
        arena_interface,
        rate_hz=spf_rate,
        seconds=spf_seconds,
        pattern_id=spf_pattern_id,
        frame_min=spf_frame_min,
        frame_max=spf_frame_max,
    )
    click.echo(
        "updates={updates}  elapsed_s={elapsed_s:.3f}  achieved={achieved_hz:.1f} Hz".format(**spf_stats)
    )

    # ------------------------------------------------------------------
    # Stream frames (optional)
    # ------------------------------------------------------------------
    if stream_path is not None:
        click.echo("\n-- stream_frames --")
        stats = bench_stream_frames(
            arena_interface,
            pattern_path=str(stream_path),
            frame_rate=float(stream_rate),
            seconds=float(stream_seconds),
            stream_cmd_coalesced=bool(stream_coalesced),
            progress_interval_s=float(progress_interval),
            analog_out_waveform="constant",
            analog_update_rate=1.0,
            analog_frequency=0.0,
        )
        click.echo(f"host_stats: {stats}")

    click.echo("\nBench done. Capture the QS PERF_* lines to compare device-side timings.\n")


if __name__ == "__main__":
    cli()
