# Stars! Web — Session Onboarding

Context notes for LLM agents working on this project.
Read this at the start of every session.

## What Is This Project?

A web-based version of Stars! (1995 4X game) that reads/writes the same binary
save files as the original fat client. Built in Python + Flask with TDD.

## Repository Layout

```text
stars_web/                     # Git repo root (jakez-gh/stars-web)
  src/stars_web/               # Core library
    stars_random.py            # L'Ecuyer PRNG (encryption)
    decryptor.py               # XOR decryption of block data
    file_header.py             # 16-byte file header parser
    block_reader.py            # Block envelope parser
    planet_names.py            # 999-entry name lookup table
    game_state.py              # High-level GameState loader
    app.py                     # Flask app factory
    run.py                     # Dev server entry point
    templates/star_map.html    # Canvas-based star map UI
    static/css/star_map.css    # Dark space theme
    static/js/star_map.js      # Canvas renderer (pan/zoom/click/tooltips)
  tests/                       # pytest suite — 130 tests
  docs/                        # Documentation
    file-format-discovery.md   # Tutorial: how we reverse-engineered the format
    llm/                       # LLM agent artifacts (this folder)
  start.bat                    # Launch dev server + open browser
```

## Workspace Context

The git repo lives inside a larger workspace:

```text
c:\Users\jake\Documents\stars\
  stars_web/      ← this repo
  autoplay/       ← sister project with test data at autoplay/tests/data/Game.*
  starswine4/     ← user's active game (turn 18), Stars! exe at stars/stars.exe
  parse_file/     ← scratch/utility
```

## GitHub CLI (gh)

`gh` is installed (v2.83.2) and authenticated as `jakez-gh`.

### Project Board

View at: <https://github.com/users/jakez-gh/projects/1>

```powershell
# List project items with status
gh project item-list 1 --owner jakez-gh

# Move an item to "In Progress" or "Done"
gh project item-edit --project-id <ID> --field-id <STATUS_FIELD_ID> --single-select-option-id <OPTION_ID>
```

### Key Commands

```powershell
# See all open issues
gh issue list

# See issues for a specific milestone
gh issue list --milestone "M1: Complete Read-Only Viewer"

# Create an issue
gh issue create --title "Title" --body "Body" --label "tier-1-read" --milestone "M1: Complete Read-Only Viewer"

# Close an issue
gh issue close 42 --comment "Fixed in commit abc1234"

# View issue details
gh issue view 42
```

### Labels

| Label | Meaning |
| ----- | ------- |
| tier-0-infra | Build, CI, lint, git hooks |
| tier-1-read | Parse more block types (read-only) |
| tier-2-orders | Issue orders (write capability) |
| tier-3-turns | Submit turns, run host, reload |
| tier-4-parity | Full fat client feature parity |
| automation | Fat client GUI automation harness |

### Milestones

#### Web Track

| # | Milestone | Description |
| - | --------- | ----------- |
| 1 | M0: Infrastructure & Quality | Git hooks, CI, lint, test hygiene |
| 2 | M1: Complete Read-Only Viewer | Parse ship designs, tech, queues, waypoints |
| 3 | M2: Issue Orders via Web UI | Waypoints, production, research, .x1 writing |
| 4 | M3: Playable Turn Loop | Write .x1, run host, reload in browser |

#### Automation Track (Fat Client GUI)

| # | Milestone | Description |
| - | --------- | ----------- |
| 5 | MA0: Automation Foundation | Launch Stars! via OTVDM, find window, capture screenshot |
| 6 | MA1: Read via GUI | Navigate screens, template-match text, cross-verify vs files |
| 7 | MA2: Command via GUI | Set waypoints, change production, allocate research via clicks |
| 8 | MA3: Autonomous Play | AI decision loop drives the fat client through full turns |

## Running Things

```powershell
# From stars_web/ directory:

# Run tests
$env:PYTHONPATH = "src"; python -m pytest tests/ --tb=short -q

# Start dev server (option 1 — batch file)
.\start.bat

# Start dev server (option 2 — manual)
$env:PYTHONPATH = "src"; python -m stars_web.run

# Start dev server with different game data
$env:PYTHONPATH = "src"; python -m stars_web.run ..\starswine4

# Star map UI at http://127.0.0.1:5000
```

## Git Workflow

- **Default branch:** master
- **Feature branches:** `feature/<name>` → PR → merge to master
- **Current branch:** feature/game-state-loader (has all work so far)
- **Commit early and often** — user's explicit preference
- **Push after every logical unit of work**

## Stars! File Format Quick Reference

- All files are sequences of **blocks**: 2-byte header (type[6] | size[10]) + data
- Block type 8 = file header (unencrypted, 16 bytes, contains J3J3 magic)
- Block type 0 = footer (unencrypted)
- All other blocks XOR-encrypted via L'Ecuyer PRNG seeded from file header
- Block type 7 = game settings + planet coordinates (trailing data unencrypted)
- Block type 13/14 = planet detail (variable-length, flag-driven)
- Block type 16/17 = fleet detail
- Known bug in reference implementations: `frac_len` has erroneous `1 +` — we fixed this

## Key Decisions & Conventions

- TDD: Write failing test first, then implement
- Store LLM artifacts in `docs/llm/`, not in prompts folder
- INVENTORY.md in every visible folder
- Git LFS for images (.gitattributes configured)
- Python 3.11+, Flask 3.x, pytest 9.x
- No external dependencies for core parsing library (stdlib only)

## Known Issues at Last Session End

1. **HTTP 500 fixed** — default game_dir path had one too many `..` segments (fixed in app.py)
2. **69 VS Code lint problems** — markdown style + CSS vendor prefix (GitHub issue #1)
3. **Git hooks not set up** — need pre-commit running pytest + lint
4. **INVENTORY.md coverage incomplete** — autoplay, starswine4 folders still need them
5. **Race screenshots not shrunk** — 1320x1118, need ~660px
6. **tests/INVENTORY.md says 118 tests** — actually 130 now (needs update)
7. **Feature branch not merged** — feature/game-state-loader has all work, master is behind
