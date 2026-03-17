from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ABOUT_RE = re.compile(r'(?m)^__version__\s*=\s*"([^"]+)"\s*$')
PIXI_WORKSPACE_VERSION_RE = re.compile(
    r'(?ms)(^\[tool\.pixi\.workspace\]\n.*?^version = ")([^"]+)(")'
)
CODEMETA_VERSION_RE = re.compile(r'(?m)^(\s*"version"\s*:\s*")([^"]+)(",?\s*)$')
CODEMETA_DATE_MODIFIED_RE = re.compile(
    r'(?m)^(\s*"dateModified"\s*:\s*")([^"]+)(",?\s*)$'
)
UNRELEASED_RE = re.compile(r'(?ms)^## Unreleased\s*\n(.*?)(?=^## |\Z)')


@dataclass(frozen=True)
class RepoPaths:
    root: Path
    about: Path
    pyproject: Path
    codemeta: Path
    changelog: Path

    @classmethod
    def from_root(cls, root: Path) -> "RepoPaths":
        return cls(
            root=root,
            about=root / "src" / "arena_interface" / "__about__.py",
            pyproject=root / "pyproject.toml",
            codemeta=root / "codemeta.json",
            changelog=root / "CHANGELOG.md",
        )


@dataclass(frozen=True)
class UpdatedFile:
    path: Path
    changed: bool


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def normalize_version(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not normalized or any(char.isspace() for char in normalized):
        raise ValueError("version must be a non-empty string without whitespace")
    return normalized


def require_substitution(path: Path, text: str, pattern: re.Pattern[str], replacement: str) -> str:
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement in {path}")
    return updated


def current_version(paths: RepoPaths) -> str:
    match = ABOUT_RE.search(read_text(paths.about))
    if match is None:
        raise RuntimeError(f"could not find __version__ assignment in {paths.about}")
    return match.group(1)


def update_about(paths: RepoPaths, new_version: str) -> UpdatedFile:
    original = read_text(paths.about)
    updated = require_substitution(
        paths.about,
        original,
        ABOUT_RE,
        rf'__version__ = "{new_version}"',
    )
    if updated != original:
        write_text(paths.about, updated)
        return UpdatedFile(paths.about, True)
    return UpdatedFile(paths.about, False)


def update_pyproject(paths: RepoPaths, new_version: str) -> UpdatedFile:
    original = read_text(paths.pyproject)
    updated = require_substitution(
        paths.pyproject,
        original,
        PIXI_WORKSPACE_VERSION_RE,
        rf'\g<1>{new_version}\g<3>',
    )
    if updated != original:
        write_text(paths.pyproject, updated)
        return UpdatedFile(paths.pyproject, True)
    return UpdatedFile(paths.pyproject, False)


def update_codemeta(paths: RepoPaths, new_version: str, release_date: str) -> UpdatedFile:
    original = read_text(paths.codemeta)
    updated = require_substitution(
        paths.codemeta,
        original,
        CODEMETA_VERSION_RE,
        rf'\g<1>{new_version}\g<3>',
    )
    updated = require_substitution(
        paths.codemeta,
        updated,
        CODEMETA_DATE_MODIFIED_RE,
        rf'\g<1>{release_date}\g<3>',
    )
    if updated != original:
        parsed = json.loads(updated)
        if parsed["version"] != new_version:
            raise RuntimeError("codemeta version update verification failed")
        if parsed["dateModified"] != release_date:
            raise RuntimeError("codemeta dateModified update verification failed")
        write_text(paths.codemeta, updated)
        return UpdatedFile(paths.codemeta, True)
    return UpdatedFile(paths.codemeta, False)


def ensure_unreleased(text: str) -> str:
    if re.search(r'(?m)^## Unreleased\s*$', text):
        return text

    heading = "# Changelog\n\n"
    if heading not in text:
        raise RuntimeError("CHANGELOG.md must start with '# Changelog'")

    return text.replace(heading, heading + "## Unreleased\n\n- TBD\n\n", 1)


def update_changelog(paths: RepoPaths, new_version: str, release_date: str) -> UpdatedFile:
    original = read_text(paths.changelog)

    if re.search(
        rf'(?m)^## {re.escape(new_version)}\s*-\s*\d{{4}}-\d{{2}}-\d{{2}}\s*$',
        original,
    ):
        raise RuntimeError(f"CHANGELOG.md already contains a section for {new_version}")

    text = ensure_unreleased(original)
    match = UNRELEASED_RE.search(text)
    if match is None:
        raise RuntimeError("could not find an '## Unreleased' section in CHANGELOG.md")

    unreleased_body = match.group(1).strip() or "- TBD"
    replacement = (
        "## Unreleased\n\n"
        "- TBD\n\n"
        f"## {new_version} - {release_date}\n\n"
        f"{unreleased_body}\n\n"
    )
    updated = text[: match.start()] + replacement + text[match.end() :].lstrip("\n")
    if updated != original:
        write_text(paths.changelog, updated)
        return UpdatedFile(paths.changelog, True)
    return UpdatedFile(paths.changelog, False)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update the repository version in package metadata and roll "
            "CHANGELOG.md from 'Unreleased' into a dated release section."
        )
    )
    parser.add_argument(
        "new_version",
        nargs="?",
        help="new package version such as 7.0.1",
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="print the current package version and exit",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="release date to record in CHANGELOG.md (default: today)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    paths = RepoPaths.from_root(args.root.resolve())

    if args.current:
        print(current_version(paths))
        return 0

    if not args.new_version:
        print("error: NEW_VERSION is required unless --current is used", file=sys.stderr)
        return 2

    try:
        new_version = normalize_version(args.new_version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    old_version = current_version(paths)
    if new_version == old_version:
        print(f"version is already {new_version}")
        return 0

    changed = [
        update_about(paths, new_version),
        update_pyproject(paths, new_version),
        update_codemeta(paths, new_version, args.date),
        update_changelog(paths, new_version, args.date),
    ]

    updated_paths = [item.path.relative_to(paths.root).as_posix() for item in changed if item.changed]
    print(f"updated version: {old_version} -> {new_version}")
    for relative_path in updated_paths:
        print(f"  - {relative_path}")
    print("next: run 'pixi install' to refresh pixi.lock, then review and commit the changes")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
