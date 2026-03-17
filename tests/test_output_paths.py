from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from arena_interface import ArenaInterface
from arena_interface.perf_summary_cli import main as perf_summary_main


def _load_bench_matrix_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "bench_matrix.py"
    spec = importlib.util.spec_from_file_location("_bench_matrix", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_bench_jsonl_creates_parent_directory(tmp_path) -> None:
    jsonl_path = tmp_path / "nested" / "bench" / "results.jsonl"

    ArenaInterface.write_bench_jsonl(
        str(jsonl_path),
        {"status": "ok", "meta": {"label": "unit-test"}},
    )

    assert jsonl_path.is_file()
    payload = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
    assert payload["status"] == "ok"
    assert payload["meta"]["label"] == "unit-test"


def test_perf_summary_cli_creates_parent_directory(tmp_path) -> None:
    bench_path = tmp_path / "inputs" / "bench_results.jsonl"
    bench_path.parent.mkdir(parents=True, exist_ok=True)
    bench_path.write_text(
        json.dumps(
            {
                "meta": {
                    "label": "linux-default",
                    "tcp_nodelay": True,
                    "tcp_quickack_requested": True,
                },
                "status": "ok",
                "cleanup": {"status": "ok", "all_off_error": None},
                "command_rtt": {"mean_ms": 0.5, "p99_ms": 0.8, "reconnects": 0},
                "spf_updates": {
                    "achieved_hz": 200.0,
                    "target_hz": 200.0,
                    "update_rtt_ms": {"p99_ms": 0.9},
                },
                "stream_frames": {
                    "frames": 1000,
                    "rate_hz": 199.5,
                    "tx_mbps": 22.0,
                    "cmd_rtt_ms": {"p99_ms": 1.1},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "nested" / "perf" / "summary.json"

    rc = perf_summary_main(["--jsonl", str(bench_path), "--json-out", str(summary_path)])

    assert rc == 0
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["host"]["run_count"] == 1


def test_bench_matrix_parser_uses_environment_transport_defaults(monkeypatch) -> None:
    monkeypatch.setenv("ARENA_ETH_IP", "192.0.2.25")
    module = _load_bench_matrix_module()

    args = module.build_parser().parse_args([])

    assert args.ethernet == "192.0.2.25"
    assert args.serial is None
