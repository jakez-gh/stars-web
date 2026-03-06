# Contributing to stars-web

## First-Time Setup

After cloning, run the setup script once to activate git hooks and install dev
dependencies:

**Windows (PowerShell):**

```powershell
.\scripts\setup-dev.ps1
```

**Linux / macOS / Git Bash:**

```bash
bash scripts/setup-dev.sh
```

This does two things:

1. Runs `git config core.hooksPath .githooks` — tells git to use the hooks
   stored in `.githooks/` instead of `.git/hooks/`.
2. Installs `pre-commit` into your virtualenv so the hook can execute.

The hooks are portable shell scripts committed in `.githooks/` — you do **not**
need to run `pre-commit install` separately. Simply activate your virtualenv
before committing and the hooks will work automatically.

## Git Hooks

All hooks live in `.githooks/` and are committed to the repo:

| Hook | Purpose |
|------|---------|
| `pre-commit` | Runs black, ruff, markdownlint, and pytest (≥ 50% coverage) |
| `pre-push` | git-lfs integrity check |
| `post-commit` | git-lfs post-commit pointer write |
| `post-checkout` | git-lfs checkout smudge |
| `post-merge` | git-lfs post-merge smudge |

The pre-commit hook is configured in `.pre-commit-config.yaml`.

## Running Tests

```powershell
py -3.11 -m pytest                        # full suite with coverage
py -3.11 -m pytest -k "battle"            # keyword filter
py -3.11 -m pytest tests/test_planet.py   # single file
```

## Bypassing Hooks

Use `--no-verify` when a hook invocation is not appropriate (e.g., WIP commits):

```bash
git commit --no-verify -m "wip: ..."
```

## Project Layout

See [INVENTORY.md](INVENTORY.md) for a full directory inventory.
Key directories:

```
src/stars_web/        # library source
  binary/             # standalone block decoders (one module per block type)
tests/                # pytest suite (1137+ tests)
docs/                 # documentation and LLM navigation aids
.githooks/            # committed git hooks (activated by setup-dev script)
scripts/              # developer setup scripts
```
