# arena-interface

`arena-interface` is a small typed Python package and CLI for controlling the
Reiser Lab `ArenaController` firmware over serial or Ethernet and for collecting
host-side benchmark results that can be compared with firmware-side `PERF_*` QS
records.

The distribution name is `arena-interface` and the import package is
`arena_interface`:

```python
from arena_interface import ArenaInterface
```

## Install

### End users

Create a virtual environment and install from PyPI:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install arena-interface
```

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install arena-interface
```

### Contributors

For local development without Pixi:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
```

If you use Pixi instead, run `pixi install`. Pixi will create or refresh
`pixi.lock` from `pyproject.toml`.

## Quick start

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

## Command-line usage

The console entry point is `arena-interface`.

```sh
arena-interface --ethernet 192.168.10.104 all-on
arena-interface --ethernet 192.168.10.104 all-off
arena-interface --ethernet 192.168.10.104 set-refresh-rate 200
arena-interface --ethernet 192.168.10.104 switch-grayscale 1
arena-interface --ethernet 192.168.10.104 get-perf-stats
arena-interface --ethernet 192.168.10.104 reset-perf-stats
```

Serial examples:

```sh
arena-interface --serial /dev/ttyACM0 all-on
arena-interface --serial /dev/ttyACM0 all-off
```

PowerShell:

```powershell
arena-interface --serial COM3 all-on
arena-interface --serial COM3 all-off
```

### Environment-variable based usage

```sh
export ARENA_ETH_IP=192.168.10.104
arena-interface all-on
arena-interface all-off
arena-interface bench
```

PowerShell equivalent:

```powershell
$env:ARENA_ETH_IP = "192.168.10.104"
arena-interface all-on
arena-interface all-off
arena-interface bench
```

## Repository layout

This repository uses a modern `src/` layout and a single `pyproject.toml` as
its packaging and tooling source of truth.

- `src/arena_interface/`: importable package, version metadata, and CLI
- `tests/`: lightweight tests that do not require hardware
- `scripts/`: developer helper scripts, including benchmark matrix and performance summary helpers
- `tools/`: repository-local helper tools such as the QSPY/QTools wrapper
- `patterns/`: example pattern files for streaming tests
- `.github/workflows/`: CI and PyPI publishing automation
- `pyproject.toml`: package metadata, tool configuration, and Pixi manifest
- `MANIFEST.in`: explicit source-distribution file list for non-package assets

The package version lives in `src/arena_interface/__about__.py`; setuptools
reads that value dynamically so wheel, sdist, import metadata, and repository
metadata stay aligned.

## Development workflow

### Pixi

```sh
pixi install
pixi run help
pixi run check
pixi run release-check
pixi run qtools-install
pixi run qspy -c /dev/ttyACM0 -b 115200
pixi run bench-smoke
pixi run bench-full --json-out bench_results.jsonl
```

Useful benchmark-oriented Pixi tasks:

```sh
pixi run bench
pixi run bench-full
pixi run bench-smoke
pixi run bench-windows-like
pixi run bench-full-windows-like
pixi run bench-socket-matrix
pixi run perf-summary --jsonl bench_results.jsonl
```

Pixi forwards extra arguments after the task name to the underlying command, so
`pixi run bench-full --json-out bench_results.jsonl --label "lab-a"` works
as expected and appends one JSON result object for that run. For this repository
layout, use `pixi run bench-full --ethernet 192.168.10.194 ...` rather than an
extra separator before `--ethernet`.

For the stock transport-agnostic tasks (`all-on`, `all-off`, `bench`,
`bench-smoke`, and `bench-full`), set `ARENA_ETH_IP` or
`ARENA_SERIAL_PORT` in your shell before running the task. This is the
simplest way to choose the transport without rewriting the task command.

Task notes:

- `bench-full` runs the full suite plus a streaming phase using `patterns/pat0004.pat`.
- `bench-windows-like` disables `TCP_QUICKACK` while leaving `TCP_NODELAY` on.
  This is a useful approximation when comparing a Linux host with a Windows-like
  Ethernet socket policy.
- `bench-full-windows-like` is the same comparison but also includes the stream phase.
- `bench-no-latency-tuning` disables both `TCP_NODELAY` and `TCP_QUICKACK`.
- `bench-socket-matrix` runs several socket-policy variants back-to-back and is
  the fastest way to quantify host-side latency tuning effects.

### Plain pip

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
python -m twine check dist/*
```

## Performance characterization workflow

`bench_results.jsonl` stores the host-side benchmark results, while QSPY
captures the raw firmware QS stream so you can compare those host-side
measurements with device-side `PERF_*` records such as `PERF_UPD kind=SPF` and
`PERF_NET`.

A few key metrics are usually enough to compare runs:

- command RTT mean and p99 (`command_rtt`)
- SPF achieved rate and p99 update RTT (`spf_updates`)
- stream frame rate and transmit throughput (`stream_frames`)
- reconnect count plus cleanup status

A convenient workflow is to keep both artifacts under a single timestamped
directory and then generate a compact summary from them.

### Terminal A: start QSPY and capture the raw QS log

```sh
mkdir -p bench_artifacts/2026-03-13-eth
pixi run qtools-install
pixi run qspy -c /dev/ttyACM0 -b 115200 2>&1 | tee bench_artifacts/2026-03-13-eth/qspy.log
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force bench_artifacts\2026-03-13-eth | Out-Null
pixi run qtools-install
pixi run qspy -c COM3 -b 115200 2>&1 | Tee-Object -FilePath bench_artifacts\2026-03-13-eth\qspy.log
```

Leave QSPY running while the benchmark executes in a second terminal. Stop it
after the benchmark completes so the log contains the full run.

### Terminal B: run the host benchmark and append JSONL results

Linux default socket policy:

```sh
pixi run bench-full --ethernet 192.168.10.194 \
  --label linux-default \
  --json-out bench_artifacts/2026-03-13-eth/bench_results.jsonl
```

Windows-like comparison with `TCP_QUICKACK` disabled:

```sh
pixi run bench-full-windows-like --ethernet 192.168.10.194 \
  --label windows-like \
  --json-out bench_artifacts/2026-03-13-eth/bench_results.jsonl
```

PowerShell:

```powershell
pixi run bench-full --ethernet 192.168.10.194 --label "windows-host" --json-out bench_artifacts\2026-03-13-eth\bench_results.jsonl
```

For a one-command socket comparison matrix, use:

```sh
pixi run bench-socket-matrix --ethernet 192.168.10.194 \
  --stream-path patterns/pat0004.pat \
  --label host-matrix \
  --json-out bench_artifacts/2026-03-13-eth/bench_results.jsonl
```

### Generate a compact performance summary

After the run, keep at least:

- `bench_results.jsonl` for host-side timings and metadata
- `qspy.log` for the raw QS stream
- a filtered `qspy_perf.log` for quick comparison (optional)

On POSIX you can extract just the performance lines with:

```sh
grep 'PERF_' bench_artifacts/2026-03-13-eth/qspy.log > bench_artifacts/2026-03-13-eth/qspy_perf.log
```

PowerShell:

```powershell
Select-String -Path bench_artifacts\2026-03-13-eth\qspy.log -Pattern 'PERF_' | ForEach-Object { $_.Line } | Set-Content bench_artifacts\2026-03-13-eth\qspy_perf.log
```

Generate a compact text summary and optionally save a machine-readable JSON
summary:

```sh
pixi run perf-summary --jsonl bench_artifacts/2026-03-13-eth/bench_results.jsonl \
  --qspy-log bench_artifacts/2026-03-13-eth/qspy.log \
  --baseline linux-default \
  --json-out bench_artifacts/2026-03-13-eth/perf_summary.json
```

The summary tool groups host-side runs by label and reports the latest QSPY
`PERF_*` records so you can answer questions like: how much slower is the
Windows-like socket policy than the Linux default, did SPF hold 200 Hz, and did
streaming throughput change.

### Interpreting cleanup warnings

Post-run `ALL_OFF` cleanup is intentionally treated as a warning when the
measurement phase has already completed. If the host reports
`status=ok_cleanup_failed`, the measured host-side statistics are still valid
and are preserved in the JSONL output. In that case:

- keep the QSPY log running and save it
- review the saved cleanup diagnostics (`ip route get ...` and `ip neigh show ...` on Linux)
- compare whether QSPY shows a fresh boot/link sequence or just a host/network path hiccup

For reproducible comparisons, keep the artifact directory together with the
firmware commit or tag, host computer, transport, switch/LAN notes, and the
benchmark label you used.

## Releasing

The repository includes GitHub Actions workflows for CI and PyPI Trusted
Publishing.

Recommended release flow:

1. Update `CHANGELOG.md`.
2. Run `pixi run release-check` or the equivalent pip commands above.
3. Commit the release changes and create a release tag such as `7.0.0` or
   `v7.0.0`.
4. Push the tag to GitHub.
5. The `publish.yml` workflow builds the wheel and sdist, then publishes them
   to PyPI using Trusted Publishing.

For conda-forge guidance, see `RELEASING.md`.
