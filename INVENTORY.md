# INVENTORY — stars_web (repo root)

Web-based Stars! 4X game client that reads/writes the same binary save files
as the original Stars! fat client (v2.6/2.7). Project last updated: 2026-03-06.

## Files

| File | Description |
| ---- | ----------- |
| `pyproject.toml` | Project metadata, dependencies (Flask, pytest, hypothesis), build config |
| `.gitignore` | Excludes `__pycache__`, `.pytest_cache`, `htmlcov`, `coverage.xml`, build artifacts |
| `.gitattributes` | Git LFS tracking rules for image files (png, jpg, etc.) |

## Folders

| Folder | Description | In/Out Scope |
| ------ | ----------- | ------------ |
| `src/stars_web/` | Core library — file parsers, game state, Flask web server, binary decoders | In scope |
| `src/stars_web/binary/` | Standalone block decoders (Types 6/12/13/14/16/17/19/20/24/25/28/30/43/45) | In scope |
| `src/stars_web/automation/` | Windows GUI automation for driving the Stars! fat client | In scope |
| `tests/` | pytest suite — 1027 tests, 82.86% coverage | In scope |
| `docs/` | Documentation, format guides, LLM agent artifacts | In scope |

## Out of Scope

- `htmlcov/` — generated coverage reports (gitignored)
- `coverage.xml` — machine-readable coverage report (gitignored)
- `__pycache__/`, `.pytest_cache/` — Python/test caches (gitignored)
- `.hypothesis/` — Hypothesis database (gitignored)

## Key Entry Points

| Command | Purpose |
| ------- | ------- |
| `py -3.11 -m pytest` | Run full test suite with coverage |
| `py -3.11 -m stars_web.run` | Launch Flask development server |
| `gh issue list` | View open GitHub issues |

## MANIFEST

### FILES

- INVENTORY.md
- pyproject.toml
- .gitignore
- .gitattributes

### FOLDERS

- src/
- tests/
- docs/
