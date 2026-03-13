from __future__ import annotations

import json
import tomllib
from pathlib import Path

from arena_interface import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_version_metadata_is_consistent() -> None:
    with (ROOT / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)

    codemeta = json.loads((ROOT / "codemeta.json").read_text(encoding="utf-8"))

    assert "version" in pyproject["project"]["dynamic"]
    assert pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"] == (
        "arena_interface.__about__.__version__"
    )
    assert pyproject["tool"]["pixi"]["workspace"]["version"] == __version__
    assert codemeta["version"] == __version__
