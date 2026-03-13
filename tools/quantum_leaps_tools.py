#!/usr/bin/env python3
"""
quantum_leaps_tools.py

Install and run the Quantum Leaps QTools host utilities pinned for the
ArenaController firmware used with this Python repository:

- QTools / QSPY  6.9.3

The tools are installed locally into:
  <repo>/.tools/quantum-leaps/

Typical usage via pixi tasks:

  pixi run qtools-install
  pixi run qspy -c /dev/ttyACM0 -b 115200
  pixi run qspy -- -h

Notes:
  * This wrapper is intentionally stdlib-only.
  * QSPY arguments like -c, -b, -u, -t are forwarded directly.
  * On Linux/macOS, QSPY is built from source using `make` if needed.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable, Optional

QTOOLS_VERSION = "6.9.3"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _tools_base_dir() -> Path:
    override = os.environ.get("QL_TOOLS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return _repo_root() / ".tools" / "quantum-leaps"


def _cache_dir() -> Path:
    return _tools_base_dir() / "_cache"


def _sys_id() -> tuple[str, str]:
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    return sysname, machine


def _print(msg: str) -> None:
    print(msg, flush=True)


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _is_probably_html(path: Path) -> bool:
    try:
        head = path.read_bytes()[:512].lstrip()
    except Exception:
        return False
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or head.startswith(b"<HTML")


def _download(urls: Iterable[str], dest: Path, *, force: bool = False, validate_zip: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        return dest

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    last_err: Optional[BaseException] = None

    for url in urls:
        try:
            _print(f"Downloading: {url}")
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "arena_interface_python/quantum_leaps_tools.py (+https://github.com/janelia-python/arena_interface_python)",
                },
            )
            with urllib.request.urlopen(req) as response, open(tmp, "wb") as f:
                shutil.copyfileobj(response, f)

            if validate_zip:
                if not zipfile.is_zipfile(tmp) or _is_probably_html(tmp):
                    raise RuntimeError(
                        "downloaded file is not a valid zip archive (maybe an HTML redirect page)"
                    )

            tmp.replace(dest)
            return dest

        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, OSError) as exc:
            last_err = exc
            _eprint(f"  failed: {exc}")
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            continue

    raise SystemExit(f"ERROR: Unable to download {dest.name}. Last error: {last_err}")


def _extract_zip_move_top(
    archive: Path,
    dest_dir: Path,
    *,
    expected_top_dir_name: Optional[str] = None,
    force: bool = False,
) -> Path:
    if dest_dir.exists() and any(dest_dir.iterdir()) and not force:
        return dest_dir

    if dest_dir.exists() and force:
        shutil.rmtree(dest_dir)

    dest_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ql_zip_") as tmpdir:
        tmp_root = Path(tmpdir)
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(tmp_root)

        src_dir: Optional[Path] = None

        if expected_top_dir_name:
            for path in tmp_root.iterdir():
                if path.is_dir() and path.name.lower() == expected_top_dir_name.lower():
                    src_dir = path
                    break

        if src_dir is None:
            dirs = [path for path in tmp_root.iterdir() if path.is_dir()]
            files = [path for path in tmp_root.iterdir() if path.is_file()]
            if len(dirs) == 1 and not files:
                src_dir = dirs[0]

        if src_dir is None:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for item in tmp_root.iterdir():
                dst = dest_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)
            return dest_dir

        shutil.move(str(src_dir), str(dest_dir))

    return dest_dir


def _qtools_candidate_urls(sysname: str) -> list[str]:
    tag = f"v{QTOOLS_VERSION}"
    gh_base = f"https://github.com/QuantumLeaps/qtools/releases/download/{tag}/"

    if sysname == "windows":
        fname = f"qtools-windows_{QTOOLS_VERSION}.zip"
    else:
        fname = f"qtools-posix_{QTOOLS_VERSION}.zip"

    return [
        gh_base + fname,
        f"https://sourceforge.net/projects/qtools/files/v{QTOOLS_VERSION}/{fname}/download",
    ]


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _find_qspy_binary(qtools_dir: Path) -> Optional[Path]:
    sysname, _ = _sys_id()
    if sysname == "windows":
        candidates = [
            qtools_dir / "bin" / "qspy.exe",
            qtools_dir / "qspy" / "bin" / "qspy.exe",
            qtools_dir / "qspy.exe",
        ]
        name = "qspy.exe"
    else:
        candidates = [
            qtools_dir / "bin" / "qspy",
            qtools_dir / "qspy" / "posix" / "qspy",
            qtools_dir / "qspy" / "bin" / "qspy",
        ]
        name = "qspy"

    for path in candidates:
        if _is_file(path):
            return path

    matches = [path for path in qtools_dir.rglob(name) if _is_file(path)]
    return matches[0] if matches else None


def _ensure_executable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except OSError:
        pass


def _build_qspy_posix(qtools_dir: Path) -> None:
    posix_dir = qtools_dir / "qspy" / "posix"
    if not posix_dir.exists():
        _eprint(f"WARNING: expected directory not found: {posix_dir}")
        return

    _print("Building qspy from source (make) ...")
    try:
        subprocess.run(["make"], cwd=str(posix_dir), check=True)
    except FileNotFoundError:
        _eprint("ERROR: 'make' not found. Ensure your pixi environment includes build tools and try again.")
        return
    except subprocess.CalledProcessError as exc:
        _eprint(f"ERROR: qspy build failed: {exc}")
        return

    qspy_bin = qtools_dir / "bin" / "qspy"
    if _is_file(qspy_bin):
        _ensure_executable(qspy_bin)
        return

    built_candidates = [
        posix_dir / "qspy",
        posix_dir / "bin" / "qspy",
        posix_dir / "../bin/qspy",
    ]
    for candidate in built_candidates:
        cand_path = candidate.resolve()
        if _is_file(cand_path):
            (qtools_dir / "bin").mkdir(parents=True, exist_ok=True)
            shutil.copy2(cand_path, qspy_bin)
            _ensure_executable(qspy_bin)
            return

    matches = [path for path in posix_dir.rglob("qspy") if _is_file(path)]
    if matches:
        (qtools_dir / "bin").mkdir(parents=True, exist_ok=True)
        shutil.copy2(matches[0], qspy_bin)
        _ensure_executable(qspy_bin)


def install_qtools(*, force: bool = False, build_qspy: bool = True) -> Path:
    sysname, _ = _sys_id()
    base = _tools_base_dir()
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)

    if sysname == "windows":
        fname = f"qtools-windows_{QTOOLS_VERSION}.zip"
    else:
        fname = f"qtools-posix_{QTOOLS_VERSION}.zip"

    zip_path = cache / fname
    install_dir = base / f"qtools-{QTOOLS_VERSION}"

    _download(_qtools_candidate_urls(sysname), zip_path, force=force, validate_zip=True)
    _extract_zip_move_top(zip_path, install_dir, expected_top_dir_name="qtools", force=force)

    if sysname != "windows" and build_qspy and _find_qspy_binary(install_dir) is None:
        _build_qspy_posix(install_dir)

    return install_dir


def _augment_runtime_env(env: dict[str, str], qtools_dir: Path) -> dict[str, str]:
    sysname, _ = _sys_id()
    bin_dir = qtools_dir / "bin"
    if not bin_dir.exists():
        return env

    old_path = env.get("PATH", "")
    env["PATH"] = str(bin_dir) + (os.pathsep + old_path if old_path else "")

    if sysname == "linux":
        old = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = str(bin_dir) + (os.pathsep + old if old else "")
    elif sysname == "darwin":
        old = env.get("DYLD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = str(bin_dir) + (os.pathsep + old if old else "")

    return env


def run_qspy(qspy_args: list[str]) -> int:
    sysname, _ = _sys_id()
    qtools_dir = install_qtools(force=False, build_qspy=True)
    qspy = _find_qspy_binary(qtools_dir)

    if qspy is None:
        raise SystemExit(
            "ERROR: qspy binary was not found after installing QTools.\n\n"
            "On Linux/macOS you may need build tools (make + a C compiler).\n"
            "Try:\n"
            "  pixi install\n"
            "  pixi run qtools-install\n"
        )

    if sysname != "windows":
        _ensure_executable(qspy)

    env = os.environ.copy()
    env.setdefault("QTOOLS", str(qtools_dir))
    env.setdefault("QTOOLS_HOME", str(qtools_dir))
    env = _augment_runtime_env(env, qtools_dir)

    cmd = [str(qspy)] + qspy_args
    _print("Running: " + " ".join(cmd))
    proc = subprocess.run(cmd, env=env, check=False)
    return proc.returncode


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quantum_leaps_tools.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            f"""\
            Install and run Quantum Leaps QTools pinned for this repository:

              QTools / QSPY  {QTOOLS_VERSION}

            Tools are installed locally into:
              {str(_tools_base_dir())}

            Examples:
              python tools/quantum_leaps_tools.py qtools-install
              python tools/quantum_leaps_tools.py qspy -c /dev/ttyACM0 -b 115200
              python tools/quantum_leaps_tools.py qspy -- -h
            """
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_qtools = sub.add_parser(
        "qtools-install", help="Install QTools (and build qspy on POSIX if needed)"
    )
    p_qtools.add_argument("--force", action="store_true", help="Re-download and reinstall QTools")

    p_qspy = sub.add_parser("qspy", help="Run QSPY (installs QTools first if needed)")
    p_qspy.add_argument("--force", action="store_true", help="Re-download and reinstall QTools")

    args, remainder = parser.parse_known_args(argv)

    if args.command == "qtools-install":
        if remainder:
            parser.error("unrecognized arguments: " + " ".join(remainder))
        install_qtools(force=args.force, build_qspy=True)
        return 0

    if args.command == "qspy":
        qspy_args = remainder
        if qspy_args and qspy_args[0] == "--":
            qspy_args = qspy_args[1:]
        if args.force:
            install_qtools(force=True, build_qspy=True)
        return run_qspy(qspy_args)

    raise SystemExit("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
