# INVENTORY — src/stars_web/automation/

Windows GUI automation layer for driving the Stars! fat client.
Used by the host-runner workflow to advance turns without manual interaction.
All modules depend on Windows-only APIs (`ctypes`, `win32api`) and are excluded from unit test coverage on non-Windows CI.

## Files

| File | Description |
| ---- | ----------- |
| `INVENTORY.md` | This file |
| `__init__.py` | Package marker; re-exports key classes for external callers |
| `commander.py` | Issues high-level commands to Stars! (e.g., load game, advance turn) by composing input sequences |
| `cross_verify.py` | Cross-verifies parsed binary game state against live data visible through the fat client UI |
| `harness.py` | Orchestration harness: coordinates launch → navigate → command → capture loop |
| `host_runner.py` | Runs the Stars! host process (`stars.exe /h`), detects completion, reads output files |
| `input.py` | Low-level keyboard and mouse input simulation via Windows `SendInput` API |
| `launcher.py` | Launches the Stars! fat client process and waits for the main window to appear |
| `matcher.py` | Screenshot template matching using pixel correlation to identify UI state/screens |
| `navigator.py` | State-machine navigator: drives the Stars! UI through menus and dialogs |
| `screen.py` | Screen capture (`BitBlt`) and region-of-interest extraction |
| `window.py` | Window management: find Stars! window by title, resize, bring to foreground |

## Folders

| Folder | Description |
| ------ | ----------- |
| `templates/` | Reference PNG/BMP images used by `matcher.py` for screen recognition |

## Design Notes

- All automation is **read/write** — can both observe state and issue orders
- Designed for headless/automated turn-processing, not interactive play
- Tests in `tests/test_automation.py` (61 tests) mock Windows APIs for CI portability

## MANIFEST

### FILES

- INVENTORY.md
- __init__.py
- commander.py
- cross_verify.py
- harness.py
- host_runner.py
- input.py
- launcher.py
- matcher.py
- navigator.py
- screen.py
- window.py

### FOLDERS

- templates/
