# INVENTORY — stars_web (repo root)

Web-based Stars! 4X game client that reads/writes the same binary save files
as the original Stars! fat client (v2.6/2.7). Project last updated: 2026-03-07.

## Files

| File | Description |
| ---- | ----------- |
| `pyproject.toml` | Project metadata, dependencies (Flask, pytest, hypothesis), build config |
| `.gitignore` | Excludes `__pycache__`, `.pytest_cache`, `htmlcov`, `coverage.xml`, build artifacts |
| `.gitattributes` | Git LFS tracking rules for image files (png, jpg, etc.) |
| `.markdownlint.json` | markdownlint rule configuration (used by `pre-commit` markdownlint hook) |
| `.pre-commit-config.yaml` | Pre-commit hook definitions: markdownlint, black, ruff, pytest, inventory gate |
| `CONTRIBUTING.md` | Developer setup guide: venv, pre-commit install, `.githooks` activation |
| `INVENTORY.md` | This file — project-level documentation inventory |
| `apply_labels.ps1` | PowerShell script to sync GitHub issue labels from label definitions |
| `start.bat` | Windows batch launcher: activates venv and starts Flask dev server |
| `start.ps1` | PowerShell launcher: activates venv and starts Flask dev server |

## Folders

| Folder | Description |
| ------ | ----------- |
| `src/stars_web/` | Core library — file parsers, game state, Flask web server, binary decoders |
| `tests/` | pytest suite — 1176 tests, 84.42% coverage |
| `docs/` | Documentation, format guides, LLM agent artifacts |
| `.github/` | GitHub CI/CD workflows and Copilot configuration |
| `.githooks/` | Portable git hooks committed to repo; activated with `git config core.hooksPath .githooks` |
| `scripts/` | Developer convenience scripts (setup-dev.ps1, setup-dev.sh) |
| `tools/` | Developer utilities: block-dump tools, inventory quality gate |

## Out of Scope

- `htmlcov/` — generated coverage reports (gitignored)
- `coverage.xml` — machine-readable coverage report (gitignored)
- `__pycache__/`, `.pytest_cache/` — Python/test caches (gitignored)
- `.hypothesis/` — Hypothesis database (gitignored)
- `.ruff_cache/`, `.vscode/` — tool caches and editor config (gitignored or local-only)

## Key Entry Points

| Command | Purpose |
| ------- | ------- |
| `py -3.11 -m pytest` | Run full test suite with coverage |
| `py -3.11 -m stars_web.run` | Launch Flask development server |
| `start.ps1` | PowerShell one-liner: activate venv + start server |
| `start.bat` | Windows batch one-liner: activate venv + start server |
| `gh issue list` | View open GitHub issues |

## MANIFEST

### FILES

- INVENTORY.md
- pyproject.toml
- .gitignore
- .gitattributes
- .markdownlint.json
- .pre-commit-config.yaml
- CONTRIBUTING.md
- apply_labels.ps1
- start.bat
- start.ps1

### FOLDERS

- src/
- tests/
- docs/
- .github/
- .githooks/
- scripts/
- tools/
