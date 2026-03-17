from __future__ import annotations

import json
import shutil
import subprocess
import sys
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



def bump_target(version: str) -> str:
    parts = version.split(".")
    if parts and all(part.isdigit() for part in parts):
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    return version + ".post1"


def test_version_bump_helper_reports_current_version() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/bump_version.py", "--current"],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )

    assert result.stdout.strip() == __version__


def test_version_bump_helper_updates_repo_copy(tmp_path: Path) -> None:
    repo_copy = tmp_path / "repo"
    repo_copy.mkdir()

    for relative in [
        "CHANGELOG.md",
        "codemeta.json",
        "pyproject.toml",
        "src/arena_interface/__about__.py",
    ]:
        source = ROOT / relative
        target = repo_copy / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    new_version = bump_target(__version__)
    release_date = "2026-03-17"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "bump_version.py"),
            "--root",
            str(repo_copy),
            "--date",
            release_date,
            f"v{new_version}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert f"updated version: {__version__} -> {new_version}" in result.stdout

    about_text = (repo_copy / "src/arena_interface/__about__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{new_version}"' in about_text

    with (repo_copy / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)
    assert pyproject["tool"]["pixi"]["workspace"]["version"] == new_version

    codemeta = json.loads((repo_copy / "codemeta.json").read_text(encoding="utf-8"))
    assert codemeta["version"] == new_version
    assert codemeta["dateModified"] == release_date

    changelog_text = (repo_copy / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog_text.startswith(
        "# Changelog\n\n"
        "## Unreleased\n\n"
        "- TBD\n\n"
        f"## {new_version} - {release_date}\n\n"
    )


def test_pixi_version_tasks_are_declared() -> None:
    with (ROOT / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)

    tasks = pyproject["tool"]["pixi"]["tasks"]

    assert tasks["version-show"] == "python scripts/bump_version.py --current"
    assert tasks["version-bump"] == "python scripts/bump_version.py"
