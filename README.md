# arena_interface

`arena_interface` is a small Python package and CLI for controlling the Reiser
Lab `ArenaController` firmware over serial or Ethernet and for collecting
host-side benchmark results that can be compared with firmware-side `PERF_*` QS
records.

This repository uses a single `pyproject.toml` as the source of truth for
package metadata, development tooling, and Pixi tasks. The importable package
lives under `src/`, which helps catch packaging mistakes earlier than a flat
layout.

## Repository layout

- `src/arena_interface/`: importable package and CLI
- `scripts/`: developer helper scripts, including benchmark matrix helpers
- `tests/`: lightweight smoke tests that do not require hardware
- `patterns/`: small example pattern files for streaming tests
- `pyproject.toml`: packaging metadata, tool configuration, and Pixi manifest

## Quick start with Pixi

Install Pixi, then from the repository root run:

```sh
pixi install
pixi run help
```

You can also run ad-hoc Python inside the managed environment:

```sh
pixi run python -c "from arena_interface import ArenaInterface; print(ArenaInterface)"
```

If you prefer an interactive shell with the package already available, use:

```sh
pixi shell
python
# or, if you already have IPython available in that environment:
# ipython
```

## Interactive Python / IPython examples

The most convenient way to drive the arena interactively is through the
`ArenaInterface` class.

### Ethernet example

```python
from arena_interface import ArenaInterface

ai = ArenaInterface(debug=True)
ai.set_ethernet_mode("192.168.10.104")

ai.all_on()
ai.all_off()
ai.switch_grayscale(1)
ai.set_refresh_rate(200)

stats = ai.get_perf_stats()
len(stats), stats.hex()[:64]

ai.show_pattern_frame(pattern_id=10, frame_index=0, frame_rate=200)
ai.update_pattern_frame(1)
ai.update_pattern_frame(2)
ai.all_off()
ai.close()
```

### Serial example

```python
from arena_interface import ArenaInterface

with ArenaInterface() as ai:
    ai.set_serial_mode("/dev/ttyACM0")
    ai.all_on()
    ai.all_off()
```

On Windows, use a COM port such as `COM3` instead of `/dev/ttyACM0`.

### Notes on the interactive API

- `set_ethernet_mode("192.168.10.104")` selects Ethernet transport.
- `set_serial_mode("/dev/ttyACM0")` or `set_serial_mode("COM3")` selects serial transport.
- `show_pattern_frame(pattern_id, frame_index, frame_rate=200)` starts
  `SHOW_PATTERN_FRAME` mode and displays the initial frame.
- `update_pattern_frame(frame_index)` updates the currently shown pattern frame.
- `get_perf_stats()` returns the raw binary perf payload from the controller.
- `reset_perf_stats()` clears firmware-side perf counters.
- `play_pattern(...)` and `play_pattern_analog_closed_loop(...)` are available
  for the older play-pattern flows.

## Command-line usage

There are two convenient ways to use the CLI:

1. Use the predefined Pixi tasks for the common operations.
2. Run the module entry point directly with `pixi run python -m arena_interface ...`.

Inside `pixi shell`, the installed console script is also available directly as
`arena-interface`.

### Discover the CLI

```sh
pixi run help
pixi run python -m arena_interface --help
pixi run python -m arena_interface --ethernet 192.168.10.104 --help
```

Click converts Python command names such as `all_on` into CLI commands such as
`all-on`. The main commands are:

- `all-on`
- `all-off`
- `set-refresh-rate`
- `display-reset`
- `switch-grayscale`
- `reset-perf-stats`
- `get-perf-stats`
- `bench`

### Ethernet command-line examples

```sh
pixi run python -m arena_interface --ethernet 192.168.10.104 all-on
pixi run python -m arena_interface --ethernet 192.168.10.104 all-off
pixi run python -m arena_interface --ethernet 192.168.10.104 set-refresh-rate 200
pixi run python -m arena_interface --ethernet 192.168.10.104 switch-grayscale 1
pixi run python -m arena_interface --ethernet 192.168.10.104 get-perf-stats
pixi run python -m arena_interface --ethernet 192.168.10.104 reset-perf-stats
```

### Serial command-line examples

```sh
pixi run python -m arena_interface --serial /dev/ttyACM0 all-on
pixi run python -m arena_interface --serial /dev/ttyACM0 all-off
```

Windows PowerShell example:

```powershell
pixi run python -m arena_interface --serial COM3 all-on
pixi run python -m arena_interface --serial COM3 all-off
```

### Environment-variable based usage

If you set the transport once, the short Pixi tasks become easier to use:

```sh
export ARENA_ETH_IP=192.168.10.104
pixi run all-on
pixi run all-off
pixi run bench
```

PowerShell equivalent:

```powershell
$env:ARENA_ETH_IP = "192.168.10.104"
pixi run all-on
pixi run all-off
pixi run bench
```

## Quick smoke tests

Before running longer benchmarks, use the `all-on` and `all-off` tasks to make
sure the host can talk to the arena and that the display is responding.

For Ethernet:

```sh
export ARENA_ETH_IP=192.168.10.104
pixi run all-on
pixi run all-off
```

For serial:

```sh
export ARENA_SERIAL_PORT=/dev/ttyACM0
pixi run all-on
pixi run all-off
```

On Windows PowerShell, set the transport variable like this before running the
same Pixi tasks:

```powershell
$env:ARENA_ETH_IP = "192.168.10.104"
# or
$env:ARENA_SERIAL_PORT = "COM3"
pixi run all-on
pixi run all-off
```

These tasks are a quick sanity check for:

- transport configuration
- basic command/response communication
- visible LED output

If `pixi run all-on` succeeds but a benchmark later fails, that usually means
the basic connection is fine and the problem is in benchmark configuration,
streaming, or timing rather than simple connectivity.

## Benchmark workflow

The CLI still supports direct invocation, but the normal developer workflow is
now through `pixi run` tasks.

Set the transport once via environment variables or pass the flags explicitly.
For Ethernet benchmarks, the simplest setup is:

```sh
export ARENA_ETH_IP=192.168.10.104
pixi run bench-full -- --json-out bench_results.jsonl
```

Useful pre-defined tasks:

- `pixi run all-on`: turn all LEDs on as a communication sanity check
- `pixi run all-off`: turn all LEDs off as a communication sanity check
- `pixi run bench`: default host-side suite (`command_rtt` + `spf_updates`)
- `pixi run bench-full`: default host-side suite plus `stream_frames` using `patterns/pat0004.pat`
- `pixi run bench-smoke`: shorter full run for quick confidence checks
- `pixi run bench-persistent`: force persistent TCP sockets for small-command RTT
- `pixi run bench-new-connection`: open a new TCP connection per command
- `pixi run bench-no-quickack`: disable Linux `TCP_QUICKACK` but keep `TCP_NODELAY`
- `pixi run bench-no-nodelay`: disable `TCP_NODELAY` but keep `TCP_QUICKACK` requested
- `pixi run bench-no-latency-tuning`: disable both socket latency knobs
- `pixi run bench-socket-matrix -- --json-out bench_matrix.jsonl`: run a small comparison matrix across socket-option variants

Extra arguments after the task are forwarded to the CLI or script, so you can
still customize labels, durations, rates, and pattern paths.

Examples:

```sh
pixi run bench -- --json-out host_only.jsonl
pixi run bench-full -- --json-out host_plus_stream.jsonl
pixi run bench-full -- --stream-rate 250 --stream-seconds 8 --json-out stream_250hz.jsonl
pixi run python -m arena_interface --ethernet 192.168.10.104 bench --cmd-iters 500 --spf-rate 250
```

## Benchmark progress, timeouts, and failure reporting

The benchmark command now prints phase start and finish lines as it runs, along
with throttled in-phase progress for the long loops. That makes it much easier
to tell whether a run is healthy, slow, or stuck.

By default, the benchmark suite applies a temporary per-operation I/O timeout of
`5.0` seconds. This avoids the old behavior where a missing reply could block a
run forever.

You can override that timeout from the CLI:

```sh
pixi run bench -- --io-timeout 10
pixi run bench-full -- --io-timeout 0
```

Use `--io-timeout 0` to disable the temporary benchmark timeout and fall back to
blocking I/O.

If a phase fails, the suite now:

- records `status=error`
- records the failed phase name and exception in the JSON result
- attempts a best-effort `ALL_OFF` cleanup before returning
- exits the CLI with a nonzero status

This makes it much easier to automate benchmarks in CI-like shell scripts or
lab orchestration scripts.

## Host-only benchmarks versus QS logs

The Python benchmark suite is enough to compare host-visible and end-to-end
behavior across:

- operating systems
- host machines
- NICs, switches, and cables
- socket-option policies such as `TCP_NODELAY` and `TCP_QUICKACK`

The JSON output is therefore a good default artifact for broad comparisons
across rigs.

QS logs are still important when you need firmware-internal detail, including:

- `PERF_NET` poll cadence and command processing cost
- `PERF_UPD` receive / process / commit / applied / coalesced counts
- display-transfer and SPI bottlenecks
- confirmation that the rig applied what the host sent

A practical workflow is:

1. Run Python-only benchmarks everywhere for broad comparison.
2. Capture QS logs on representative runs or anomalous runs.
3. Use the QS logs to explain why two host-visible results differ.

## Cross-platform notes

The project configuration targets Linux, macOS, and Windows through Pixi, and
the basic host functionality is designed to work across those operating
systems.

What is portable:

- serial control through `pyserial`
- Ethernet control through standard Python sockets
- the Click-based CLI
- the JSON benchmark output
- the `all-on`, `all-off`, and `bench` workflows

What is Linux-specific or Linux-enhanced:

- `TCP_QUICKACK` support
- route and interface metadata captured from `ip route get`
- extra NIC details captured from `/sys/class/net/...`

So the short answer is: yes, the code is intended to work on Linux, macOS, and
Windows, but the Linux runs expose the most low-level socket tuning and network
metadata.

For cross-OS comparisons, the safest approach is:

1. Treat `TCP_NODELAY` as the portable latency knob.
2. Treat `TCP_QUICKACK` as Linux-specific and compare it separately.
3. Use the same benchmark JSON schema everywhere.
4. Use QS logs when you need to explain firmware-side differences.

## Socket latency tuning

The host code exposes both `TCP_NODELAY` and `TCP_QUICKACK` as explicit options.
That makes it easy to compare:

- Linux Python with both knobs enabled
- Linux Python with only one enabled
- platforms where `TCP_QUICKACK` is unavailable or ignored

The benchmark metadata records which socket settings were requested and whether
`TCP_QUICKACK` was supported on the current host, so later analysis can compare
runs fairly.

## Development tasks

```sh
pixi run format
pixi run lint
pixi run test
pixi run check
pixi run build
pixi run archive
```
