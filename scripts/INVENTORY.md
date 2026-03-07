# INVENTORY — scripts/

Developer convenience scripts for first-time project setup.
Run these once after cloning on a new machine to configure the local development environment.

## Files

| File | Description |
| ---- | ----------- |
| `INVENTORY.md` | This file |
| `setup-dev.ps1` | PowerShell: creates venv, installs dev dependencies, activates `.githooks/` via `git config core.hooksPath` |
| `setup-dev.sh` | Bash equivalent of `setup-dev.ps1` for macOS/Linux contributors |

## Usage

```powershell
# Windows
.\scripts\setup-dev.ps1

# macOS/Linux
bash scripts/setup-dev.sh
```

Both scripts:

1. Create `.venv` from Python 3.11
2. Install `pip install -e .[dev]`
3. Run `pre-commit install`
4. Run `git config core.hooksPath .githooks`

## MANIFEST

### FILES

- INVENTORY.md
- setup-dev.ps1
- setup-dev.sh

### FOLDERS

(none)
