# INVENTORY — stars_web (repo root)

Web-based Stars! 4X game client that reads/writes the same binary save files
as the original Stars! fat client (v2.6/2.7).

## Files

| File | Description |
|------|-------------|
| pyproject.toml | Project metadata, dependencies (Flask, pytest), build config |
| .gitignore | Excludes __pycache__, .pytest_cache, htmlcov, build artifacts |
| .gitattributes | Git LFS tracking rules for image files (png, jpg, etc.) |

## Folders

| Folder | Description | In/Out Scope |
|--------|-------------|--------------|
| src/stars_web/ | Core library — file parsers, game state loader | In scope |
| tests/ | pytest test suite — unit + integration tests | In scope |
| docs/ | Documentation, format tutorials, reference screenshots | In scope |

## Out of Scope

- `htmlcov/` — generated coverage reports (gitignored)
- `__pycache__/`, `.pytest_cache/` — Python/test caches (gitignored)
