# Changelog

## Unreleased

- TBD

## 7.0.1 - 2026-03-17

- added a Pixi version helper task and script so package metadata and release
  notes can be bumped consistently before the next tag

## 7.0.0 - 2026-03-13

- moved package versioning to a single source of truth in
  `src/arena_interface/__about__.py`
- modernized `pyproject.toml` for current PyPI metadata practices, including
  SPDX licensing metadata and explicit typed-package data
- added an explicit `MANIFEST.in` so sdists include repository assets that are
  useful to downstream builders and maintainers
- made the top-level package import resilient when `pyserial` is unavailable,
  while still requiring it for serial transport usage
- added CI and PyPI Trusted Publishing GitHub Actions workflows
- documented a reproducible release process for PyPI and conda-forge
- expanded the README with Pixi benchmark usage, JSONL capture, and QSPY log
  collection guidance for performance characterization
- relaxed the publish workflow so release tags can be either `7.0.0` or
  `v7.0.0`
- added a performance summary tool for benchmark JSONL files and QSPY PERF logs
- added Windows-like benchmark task aliases and matrix entries for socket-tuning comparisons
- downgraded post-run ALL_OFF cleanup failures to recorded benchmark warnings so completed measurements are preserved
- added stream-enabled Pixi tasks and matrix helpers for comparing Linux-default, Windows-like, and no-tuning host socket policies
- made benchmark JSONL and performance summary commands create parent output directories automatically
- updated GitHub Actions artifact steps to current major versions to avoid the Node.js 20 deprecation warnings on GitHub-hosted runners
