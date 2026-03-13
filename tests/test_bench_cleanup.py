from __future__ import annotations

import json

import arena_interface.arena_interface as arena_mod
from arena_interface import ArenaInterface
from arena_interface.perf_summary import build_performance_summary, render_text_summary


def test_safe_all_off_recovers_after_retry(monkeypatch) -> None:
    ai = ArenaInterface()
    ai.set_ethernet_mode("192.0.2.10")

    attempts = {"count": 0}

    def fake_all_off() -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("cleanup timeout")

    monkeypatch.setattr(ai, "all_off", fake_all_off)
    monkeypatch.setattr(
        ai,
        "_collect_linux_net_diagnostics",
        lambda peer_ip: {"peer_ip": str(peer_ip), "route_get": "dev eth0", "neighbor": "reachable"},
    )
    monkeypatch.setattr(arena_mod.time, "sleep", lambda _: None)

    cleanup = ai._safe_all_off(context="unit-test cleanup")

    assert cleanup["status"] == "ok_after_retry"
    assert cleanup["all_off_ok"] is True
    assert cleanup["retry_performed"] is True
    assert cleanup["diagnostics"] == {
        "peer_ip": "192.0.2.10",
        "route_get": "dev eth0",
        "neighbor": "reachable",
    }
    assert len(cleanup["attempts"]) == 2
    assert cleanup["attempts"][0]["ok"] is False
    assert cleanup["attempts"][1]["ok"] is True


def test_bench_suite_keeps_successful_measurements_on_cleanup_warning(monkeypatch) -> None:
    ai = ArenaInterface(tcp_quickack=False)

    monkeypatch.setattr(
        ai,
        "bench_command_rtt",
        lambda **kwargs: {
            "mean_ms": 0.50,
            "p99_ms": 0.80,
            "reconnects": 0,
            "cleanup": {
                "all_off_attempted": True,
                "all_off_ok": False,
                "status": "failed",
                "all_off_error": "TimeoutError: cleanup timeout",
                "retry_performed": True,
                "diagnostics": {"route_get": "dev eth0"},
                "attempts": [
                    {"attempt": 1, "ok": False, "error": "TimeoutError: cleanup timeout"},
                    {"attempt": 2, "ok": False, "error": "TimeoutError: cleanup timeout"},
                ],
            },
        },
    )
    monkeypatch.setattr(
        ai,
        "bench_spf_updates",
        lambda **kwargs: {
            "updates": 100,
            "elapsed_s": 0.5,
            "target_hz": 200.0,
            "achieved_hz": 200.0,
            "update_rtt_ms": {"p99_ms": 0.70},
            "reconnects": 0,
            "cleanup": {
                "all_off_attempted": True,
                "all_off_ok": True,
                "status": "ok",
                "all_off_error": None,
                "retry_performed": False,
                "diagnostics": {},
                "attempts": [{"attempt": 1, "ok": True, "error": None}],
            },
        },
    )

    suite = ai.bench_suite(label="unit-test")

    assert suite["status"] == "ok_cleanup_failed"
    assert suite["failed_phase"] is None
    assert suite["error"] is None
    assert suite["command_rtt"]["mean_ms"] == 0.50
    assert suite["cleanup"]["status"] == "failed"
    assert suite["cleanup"]["all_off_ok"] is False
    assert suite["warnings"][0]["type"] == "cleanup_failed"


def test_performance_summary_reports_host_and_qspy_metrics(tmp_path) -> None:
    bench_path = tmp_path / "bench_results.jsonl"
    qspy_path = tmp_path / "qspy.log"

    run_default = {
        "meta": {
            "label": "linux-default",
            "transport": "ethernet",
            "tcp_nodelay": True,
            "tcp_quickack_requested": True,
            "tcp_quickack_supported": True,
        },
        "status": "ok",
        "cleanup": {"status": "ok", "all_off_error": None},
        "warnings": [],
        "command_rtt": {"mean_ms": 0.45, "p99_ms": 0.70, "reconnects": 0},
        "spf_updates": {"achieved_hz": 200.0, "target_hz": 200.0, "update_rtt_ms": {"p99_ms": 0.80}},
        "stream_frames": {"frames": 1000, "rate_hz": 199.8, "tx_mbps": 22.5, "cmd_rtt_ms": {"p99_ms": 1.1}},
    }
    run_windows_like = {
        "meta": {
            "label": "windows-like",
            "transport": "ethernet",
            "tcp_nodelay": True,
            "tcp_quickack_requested": False,
            "tcp_quickack_supported": True,
        },
        "status": "ok",
        "cleanup": {"status": "ok", "all_off_error": None},
        "warnings": [],
        "command_rtt": {"mean_ms": 0.60, "p99_ms": 0.95, "reconnects": 0},
        "spf_updates": {"achieved_hz": 198.5, "target_hz": 200.0, "update_rtt_ms": {"p99_ms": 0.95}},
        "stream_frames": {"frames": 990, "rate_hz": 197.9, "tx_mbps": 22.0, "cmd_rtt_ms": {"p99_ms": 1.4}},
    }

    bench_path.write_text(
        json.dumps(run_default) + "\n" + json.dumps(run_windows_like) + "\n",
        encoding="utf-8",
    )
    qspy_path.write_text(
        "000000 PERF_UPD kind=SPF frames=1000 rate_hz=199.8 p99_us=450\n"
        "000001 PERF_NET bytes_tx=123456 bytes_rx=123400 drops=0\n",
        encoding="utf-8",
    )

    summary = build_performance_summary(
        jsonl_paths=[bench_path],
        qspy_log_paths=[qspy_path],
        baseline_label="linux-default",
    )
    text = render_text_summary(summary)

    assert summary["host"]["run_count"] == 2
    assert "Host benchmark runs: 2" in text
    assert "Baseline: linux-default" in text
    assert "windows-like" in text
    assert "QSPY PERF records: 2" in text
    assert "PERF_UPD kind=SPF" in text
