"""Generate a compact performance summary from benchmark JSONL and QSPY logs."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

from arena_interface.perf_summary_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
