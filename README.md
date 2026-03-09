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
pixi run bench -- --stream-path patterns/pat0004.pat --json-out bench_results.jsonl
```

Useful pre-defined tasks:

- `pixi run all-on`: turn all LEDs on as a communication sanity check
- `pixi run all-off`: turn all LEDs off as a communication sanity check
- `pixi run bench`: default host benchmark suite
- `pixi run bench-persistent`: force persistent TCP sockets for small-command RTT
- `pixi run bench-new-connection`: open a new TCP connection per command
- `pixi run bench-no-quickack`: disable Linux `TCP_QUICKACK` but keep `TCP_NODELAY`
- `pixi run bench-no-nodelay`: disable `TCP_NODELAY` but keep `TCP_QUICKACK` requested
- `pixi run bench-no-latency-tuning`: disable both socket latency knobs
- `pixi run bench-socket-matrix -- --json-out bench_matrix.jsonl`: run a small comparison matrix across socket-option variants

Extra arguments after the task are forwarded to the CLI or script, so you can
still customize labels, durations, rates, and pattern paths.

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
