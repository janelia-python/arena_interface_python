"""Console entry point for performance summary generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .perf_summary import build_performance_summary, render_text_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize ArenaController benchmark JSONL runs and optional QSPY PERF logs "
            "into a compact host/device performance report."
        )
    )
    parser.add_argument(
        "--jsonl",
        dest="jsonl_paths",
        type=Path,
        nargs="+",
        default=[],
        help="One or more benchmark JSONL files produced by arena-interface bench --json-out",
    )
    parser.add_argument(
        "--qspy-log",
        dest="qspy_log_paths",
        type=Path,
        nargs="+",
        default=[],
        help="One or more saved QSPY text logs containing PERF_* records",
    )
    parser.add_argument(
        "--label-filter",
        default=None,
        help="Only include benchmark runs whose label contains this substring",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Label substring to use as the baseline run for host delta comparisons",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write the machine-readable summary JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_performance_summary(
        jsonl_paths=args.jsonl_paths,
        qspy_log_paths=args.qspy_log_paths,
        label_filter=args.label_filter,
        baseline_label=args.baseline,
    )
    sys.stdout.write(render_text_summary(summary))
    if args.json_out is not None:
        args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
