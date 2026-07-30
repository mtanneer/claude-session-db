# Contributing

## Setup

```
python3 -m venv .venv
.venv/bin/pip install pytest
```

## Tests

```
.venv/bin/python -m pytest session-archiver/scripts/tests/
```

Single test:

```
.venv/bin/python -m pytest session-archiver/scripts/tests/test_archive_session.py -v
```

## Branches

`<type>/<username>/<description>`, types: `feat|fix|chore|test|docs|refactor`.

## Versioning

`session-archiver/.claude-plugin/plugin.json`'s `version` must be valid,
strictly-increasing semver on any PR touching non-doc files. CI's
`version-check` job (`.github/workflows/ci.yml`) enforces this; docs-only
changes (`.md`, `.github/`, `ruff.toml`) are exempt.

## CI

Runs on every PR, in order: `version-check` → `lint` (ruff) →
`secret-scan` (gitleaks) → `unit-tests` (pytest). All must pass before
merge.
