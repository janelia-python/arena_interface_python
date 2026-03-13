# Releasing arena-interface

## Local validation

Using pip:

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
python -m twine check dist/*
```

Using Pixi:

```sh
pixi install
pixi run release-check
```

If you use Pixi and `pyproject.toml` changed, regenerate `pixi.lock` with
`pixi install` and commit the updated lock file.

## PyPI Trusted Publishing

The repository includes `.github/workflows/publish.yml`, which is intended for
GitHub Actions Trusted Publishing.

One-time setup on GitHub:

1. In the repository settings, create a GitHub Actions environment named
   `pypi`.
2. Optionally add protection rules or required reviewers if you want a manual
   approval gate before publishing.

One-time setup on PyPI:

1. Create the `arena-interface` project on PyPI if it does not already exist.
2. In the PyPI project settings, add a Trusted Publisher for this GitHub
   repository.
3. Use workflow filename `publish.yml` and environment name `pypi`.

Release trigger:

1. Push a release tag such as `7.0.0` or `v7.0.0`.
2. GitHub Actions will build `dist/*` and publish to PyPI without storing a
   long-lived API token in GitHub secrets.
3. `workflow_dispatch` is kept as a manual build/debug entry point; the actual
   PyPI publish step only runs for tag pushes.

The normal release path is to let GitHub Actions publish via Trusted
Publishing. Local `twine upload` is only needed if you intentionally want to
bypass that workflow.

## Conda-forge

Conda-forge packages are maintained in a separate feedstock repository, so the
upstream project does not need to vendor the feedstock into this repository.

Recommended flow after a PyPI release:

1. Wait for the `7.0.0` sdist to be available on PyPI.
2. Generate or update a conda-forge v1 recipe:

   ```sh
   grayskull pypi --use-v1-format --strict-conda-forge arena-interface==7.0.0
   ```

3. Submit the generated `recipe.yaml` to `conda-forge/staged-recipes` for the
   first release, or open a PR against the existing feedstock for updates.
4. Verify the recipe uses the PyPI sdist URL and SHA256, `noarch: python`, and
   `pip install . --no-deps --no-build-isolation` in the build script.
