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
