# Releasing ankora

Publishing to [PyPI](https://pypi.org/) is automated via GitHub Actions and PyPI
**Trusted Publishing** (OIDC). There are **no API tokens** stored in this
repository — PyPI trusts a specific GitHub workflow directly.

## One-time setup (manual, on pypi.org)

Do this once, before the first release:

1. Sign in to <https://pypi.org>.
2. Reserve the project name by creating a **pending publisher** (this also
   registers the `ankora` name): go to your account →
   **Publishing** → **Add a new pending publisher**, and fill in:
   - **PyPI Project Name:** `ankora`
   - **Owner:** your GitHub org/user (the owner of this repo)
   - **Repository name:** `ankora` (this repo's name)
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. Save. PyPI will now accept uploads that come from
   `.github/workflows/publish.yml` running in the `pypi` environment of this
   repo — and only those.

> The four values above must exactly match this repo, the workflow filename, and
> the `environment: pypi` in [`.github/workflows/publish.yml`](.github/workflows/publish.yml).
> If you rename the repo or move it to a different owner, update the Trusted
> Publisher on PyPI to match.

(Optional) In the GitHub repo settings, create an **Environment** named `pypi`
and add required reviewers if you want a manual approval gate before each
publish.

## Cutting a release

1. Bump `version` in `pyproject.toml` (single source of truth — the CLI reads it
   via `importlib.metadata`).
2. Commit and merge to `main`.
3. On GitHub, **Releases → Draft a new release**, create a tag like `v0.1.0`,
   and **Publish release**.
4. The `publish` workflow builds the sdist + wheel with `uv build` and uploads
   them to PyPI via Trusted Publishing. No tokens, no manual upload.

## Verifying locally before a release

```bash
uv build              # produces dist/ankora-<version>.tar.gz and .whl
uv run pytest
uv run ruff check && uv run ruff format --check
bash examples/run_demo.sh   # keyless end-to-end (green gate + red gate)
```
