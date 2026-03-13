"""Helpers for summarizing benchmark JSONL runs and QSPY PERF logs."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable

_QSPY_RECORD_RE = re.compile(r"\b(?P<record>PERF_[A-Z0-9_]+)\b(?P<rest>.*)$")
_QSPY_KV_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_\-/]*)=(?P<value>[^\s]+)")
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")

_HOST_DELTA_METRICS: tuple[tuple[str, str, str], ...] = (
    ("cmd_mean_ms", "command RTT mean", "ms"),
    ("cmd_p99_ms", "command RTT p99", "ms"),
    ("spf_achieved_hz", "SPF achieved", "Hz"),
    ("stream_rate_hz", "stream rate", "Hz"),
    ("stream_tx_mbps", "stream TX", "Mb/s"),
)


def _coerce_qspy_value(raw: str) -> object:
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    if raw.lower().startswith("0x"):
        try:
            return int(raw, 16)
        except ValueError:
            return raw
    if _INT_RE.match(raw):
        try:
            return int(raw)
        except ValueError:
            return raw
    if _FLOAT_RE.match(raw):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def load_bench_results(paths: Iterable[Path], *, label_filter: str | None = None) -> list[dict]:
    """Load benchmark result objects from one or more JSONL files."""
    results: list[dict] = []
    needle = label_filter.lower() if label_filter else None

    for path in paths:
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                text = raw.strip()
                if not text:
                    continue
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    continue
                label = str((payload.get("meta") or {}).get("label") or "")
                if needle and needle not in label.lower():
                    continue
                payload.setdefault("_source_jsonl", str(path))
                payload.setdefault("_source_line", int(line_number))
                results.append(payload)
    return results


def parse_qspy_perf_records(lines: Iterable[str]) -> list[dict]:
    """Parse PERF_* records from a QSPY text log."""
    records: list[dict] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        match = _QSPY_RECORD_RE.search(line)
        if match is None:
            continue

        fields: dict[str, object] = {
            "record": match.group("record"),
            "line_no": int(line_number),
            "raw": line,
        }
        rest = match.group("rest") or ""
        for kv_match in _QSPY_KV_RE.finditer(rest):
            key = kv_match.group("key")
            value = _coerce_qspy_value(kv_match.group("value"))
            fields[key] = value
        records.append(fields)
    return records


def load_qspy_perf_records(paths: Iterable[Path]) -> list[dict]:
    """Load PERF_* records from one or more QSPY log files."""
    records: list[dict] = []
    for path in paths:
        with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
            file_records = parse_qspy_perf_records(handle)
        for record in file_records:
            record.setdefault("source_log", str(path))
        records.extend(file_records)
    return records


def extract_host_run_metrics(run: dict, *, default_label: str) -> dict[str, object]:
    """Extract the main user-facing performance metrics from one benchmark run."""
    meta = run.get("meta") or {}
    cleanup = run.get("cleanup") or {}
    command_rtt = run.get("command_rtt") or {}
    spf_updates = run.get("spf_updates") or {}
    stream_frames = run.get("stream_frames") or {}

    quickack_supported = bool(meta.get("tcp_quickack_supported"))
    quickack_requested = bool(meta.get("tcp_quickack_requested"))
    quickack_active = quickack_supported and quickack_requested

    return {
        "label": meta.get("label") or default_label,
        "status": run.get("status") or "unknown",
        "cleanup_status": cleanup.get("status") or "not_attempted",
        "cleanup_error": cleanup.get("all_off_error"),
        "warnings": run.get("warnings") or [],
        "transport": meta.get("transport"),
        "tcp_nodelay": meta.get("tcp_nodelay"),
        "tcp_quickack_supported": quickack_supported,
        "tcp_quickack_requested": quickack_requested,
        "tcp_quickack_active": quickack_active,
        "source_jsonl": run.get("_source_jsonl"),
        "source_line": run.get("_source_line"),
        "cmd_mean_ms": command_rtt.get("mean_ms"),
        "cmd_p99_ms": command_rtt.get("p99_ms"),
        "cmd_reconnects": command_rtt.get("reconnects"),
        "spf_target_hz": spf_updates.get("target_hz"),
        "spf_achieved_hz": spf_updates.get("achieved_hz"),
        "spf_p99_update_ms": (spf_updates.get("update_rtt_ms") or {}).get("p99_ms"),
        "stream_frames": stream_frames.get("frames"),
        "stream_rate_hz": stream_frames.get("rate_hz"),
        "stream_tx_mbps": stream_frames.get("tx_mbps"),
        "stream_cmd_p99_ms": (stream_frames.get("cmd_rtt_ms") or {}).get("p99_ms"),
    }


def summarize_host_runs(runs: list[dict], *, baseline_label: str | None = None) -> dict[str, object]:
    """Summarize benchmark JSONL runs into a compact comparison structure."""
    metrics = [
        extract_host_run_metrics(run, default_label=f"run_{index}")
        for index, run in enumerate(runs, start=1)
    ]

    counts: dict[str, int] = {}
    for metric in metrics:
        status = str(metric.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    baseline = None
    if metrics:
        if baseline_label:
            needle = baseline_label.lower()
            for metric in metrics:
                label = str(metric.get("label") or "")
                if needle in label.lower():
                    baseline = metric
                    break
        if baseline is None:
            baseline = metrics[0]

    comparisons: list[dict[str, object]] = []
    if baseline is not None:
        baseline_label_value = str(baseline.get("label"))
        for metric in metrics:
            if metric is baseline:
                continue
            metric_deltas: list[dict[str, object]] = []
            for key, description, unit in _HOST_DELTA_METRICS:
                base_value = baseline.get(key)
                current_value = metric.get(key)
                if not (_is_finite_number(base_value) and _is_finite_number(current_value)):
                    continue
                base = float(base_value)
                current = float(current_value)
                delta = current - base
                pct = None
                if base != 0:
                    pct = (delta / base) * 100.0
                metric_deltas.append(
                    {
                        "metric": key,
                        "description": description,
                        "unit": unit,
                        "baseline": base,
                        "current": current,
                        "delta": delta,
                        "pct": pct,
                    }
                )
            comparisons.append(
                {
                    "baseline_label": baseline_label_value,
                    "label": metric.get("label"),
                    "deltas": metric_deltas,
                }
            )

    return {
        "run_count": len(metrics),
        "status_counts": counts,
        "runs": metrics,
        "baseline": baseline,
        "comparisons": comparisons,
    }


def summarize_qspy_records(records: list[dict]) -> dict[str, object]:
    """Group PERF_* records into a compact latest-record summary."""
    grouped: dict[str, dict[str, object]] = {}
    for record in records:
        kind = record.get("kind")
        group_name = f"{record['record']} kind={kind}" if kind else str(record["record"])
        info = grouped.setdefault(group_name, {"count": 0, "latest": None, "numeric_fields": {}})
        info["count"] = int(info.get("count", 0)) + 1
        info["latest"] = record

        numeric_fields = info.setdefault("numeric_fields", {})
        assert isinstance(numeric_fields, dict)
        for key, value in record.items():
            if key in {"record", "kind", "raw", "line_no", "source_log"}:
                continue
            if _is_finite_number(value):
                bucket = numeric_fields.setdefault(key, [])
                assert isinstance(bucket, list)
                bucket.append(float(value))

    groups: list[dict[str, object]] = []
    for name, info in grouped.items():
        latest = info.get("latest") or {}
        numeric_summary: dict[str, dict[str, float]] = {}
        for key, values in (info.get("numeric_fields") or {}).items():
            if not values:
                continue
            numeric_summary[key] = {
                "min": min(values),
                "max": max(values),
                "last": values[-1],
            }
        groups.append(
            {
                "group": name,
                "count": int(info.get("count", 0)),
                "latest": latest,
                "numeric_summary": numeric_summary,
            }
        )

    groups.sort(key=lambda item: str(item.get("group")))
    return {"record_count": len(records), "groups": groups}


def build_performance_summary(
    *,
    jsonl_paths: Iterable[Path] = (),
    qspy_log_paths: Iterable[Path] = (),
    label_filter: str | None = None,
    baseline_label: str | None = None,
) -> dict[str, object]:
    """Load artifacts and build one combined performance summary."""
    jsonl_path_list = [Path(path) for path in jsonl_paths]
    qspy_path_list = [Path(path) for path in qspy_log_paths]
    runs = load_bench_results(jsonl_path_list, label_filter=label_filter)
    qspy_records = load_qspy_perf_records(qspy_path_list)
    return {
        "inputs": {
            "jsonl": [str(path) for path in jsonl_path_list],
            "qspy_logs": [str(path) for path in qspy_path_list],
            "label_filter": label_filter,
            "baseline_label": baseline_label,
        },
        "host": summarize_host_runs(runs, baseline_label=baseline_label),
        "qspy": summarize_qspy_records(qspy_records),
    }


def _format_number(value: object, unit: str | None = None) -> str:
    if not _is_finite_number(value):
        return "n/a"
    number = float(value)
    if unit == "Hz":
        text = f"{number:.1f}"
    elif unit == "Mb/s":
        text = f"{number:.2f}"
    else:
        text = f"{number:.3f}"
    return f"{text} {unit}" if unit else text


def _format_compact_fields(record: dict[str, object], *, limit: int = 6) -> str:
    preferred: list[tuple[str, object]] = []
    fallback: list[tuple[str, object]] = []
    priority_terms = (
        "kind",
        "mode",
        "phase",
        "frames",
        "updates",
        "rate",
        "hz",
        "fps",
        "mean",
        "avg",
        "p50",
        "p95",
        "p99",
        "max",
        "min",
        "bytes",
        "drop",
        "err",
    )

    for key, value in record.items():
        if key in {"record", "raw", "line_no", "source_log"}:
            continue
        pair = (str(key), value)
        if any(term in str(key).lower() for term in priority_terms):
            preferred.append(pair)
        else:
            fallback.append(pair)

    selected = preferred[:limit]
    if len(selected) < limit:
        selected.extend(fallback[: max(0, limit - len(selected))])
    return ", ".join(f"{key}={value}" for key, value in selected)


def render_text_summary(summary: dict[str, object]) -> str:
    """Render a human-readable performance summary."""
    lines: list[str] = []

    host = summary.get("host") or {}
    runs = host.get("runs") or []
    if runs:
        status_counts = host.get("status_counts") or {}
        counts_text = ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items()))
        lines.append(f"Host benchmark runs: {host.get('run_count', 0)} ({counts_text})")
        lines.append("label | status | cmd mean / p99 | SPF achieved | stream rate / tx | socket policy")
        for run in runs:
            policy = (
                f"nodelay={run.get('tcp_nodelay')} "
                f"quickack={run.get('tcp_quickack_active')}"
            )
            line = (
                f"{run.get('label')} | {run.get('status')}"
                f" | {_format_number(run.get('cmd_mean_ms'), 'ms')} / {_format_number(run.get('cmd_p99_ms'), 'ms')}"
                f" | {_format_number(run.get('spf_achieved_hz'), 'Hz')}"
                f" | {_format_number(run.get('stream_rate_hz'), 'Hz')} / {_format_number(run.get('stream_tx_mbps'), 'Mb/s')}"
                f" | {policy}"
            )
            cleanup_status = run.get("cleanup_status")
            if cleanup_status not in {None, "not_attempted", "ok"}:
                line += f" | cleanup={cleanup_status}"
            lines.append(line)

        baseline = host.get("baseline")
        comparisons = host.get("comparisons") or []
        if baseline and comparisons:
            lines.append("")
            lines.append(f"Baseline: {baseline.get('label')}")
            for comparison in comparisons:
                delta_bits: list[str] = []
                for delta in comparison.get("deltas") or []:
                    pct = delta.get("pct")
                    pct_text = f" ({float(pct):+.1f}%)" if _is_finite_number(pct) else ""
                    delta_bits.append(
                        f"{delta.get('description')} {float(delta.get('delta')):+.3f} {delta.get('unit')}{pct_text}"
                    )
                if delta_bits:
                    lines.append(f"- {comparison.get('label')}: " + "; ".join(delta_bits))
    else:
        lines.append("Host benchmark runs: none")

    qspy = summary.get("qspy") or {}
    groups = qspy.get("groups") or []
    lines.append("")
    lines.append(f"QSPY PERF records: {qspy.get('record_count', 0)}")
    if groups:
        for group in groups:
            latest = group.get("latest") or {}
            compact = _format_compact_fields(latest)
            lines.append(
                f"- {group.get('group')}: count={group.get('count')} latest(line {latest.get('line_no')}): {compact}"
            )
    else:
        lines.append("- none")

    return "\n".join(lines).strip() + "\n"
