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

One-time setup on PyPI:

1. Create the `arena-interface` project on PyPI if it does not already exist.
2. In the PyPI project settings, add a Trusted Publisher for this GitHub
   repository and workflow.
3. Push a tag such as `v7.0.0`.

After the tag is pushed, GitHub Actions will build `dist/*` and publish to
PyPI without storing a long-lived API token in GitHub secrets.

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
