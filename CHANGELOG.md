# Changelog

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
