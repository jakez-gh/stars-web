# INVENTORY — src/stars_web/

Core library for parsing Stars! binary file formats, assembling game state,
and serving a Flask web UI.

## Files

| File | Description |
| ---- | ----------- |
| `__init__.py` | Package marker (empty) |
| `stars_random.py` | L'Ecuyer Combined LCG PRNG — used for XOR encryption |
| `decryptor.py` | Derives PRNG seeds from file header, decrypts block data |
| `file_header.py` | Parses the 16-byte file header (type 8 block): magic, game_id, turn, salt, player |
| `block_reader.py` | Reads a Stars! file into a list of typed/decrypted Block objects |
| `planet_names.py` | 999-entry lookup table mapping name_id → planet name string |
| `stars_string.py` | Decodes Stars! custom nibble-based text encoding used in design names |
| `game_state.py` | High-level loader: assembles GameState from .xy/.m#/.hst. Parses types 6/7/13/14/16/17/20/26/28 |
| `order_serializer.py` | Serializes player orders back to binary format for writing .m# files |
| `app.py` | Flask application factory — registers API blueprints and serves the web UI |
| `run.py` | Entry-point: launches the Flask dev server with configured host/port |
| `lifecycle.py` | Manages Stars! game process lifecycle (start, stop, detect running) |
| `port_manager.py` | Deterministic port allocation using game ID hash to avoid collisions |
| `status.py` | Polls game/server status and exposes a JSON status endpoint |
| `web_builder.py` | Generates star map HTML from game state for browser rendering |
| `changelog.json` | Machine-readable changelog indexed by version (populated by release tooling) |

## Folders

| Folder | Description |
| ------ | ----------- |
| `binary/` | Standalone binary block decoders — one module per block type (Types 6/12/13/14/16/17/19/20/24/25/28/30/43/45/EOF). See `binary/INVENTORY.md`. |
| `automation/` | Windows GUI automation helpers for driving the Stars! fat client (input, window, screen, navigator, matcher, harness) |
| `static/` | Flask static assets (CSS, JS) served at `/static/` |
| `templates/` | Jinja2 HTML templates for Flask routes |

## Data Flow

```text
Game.xy / Game.m# / Game.hst  (raw bytes)
  → block_reader.read_blocks()
      → file_header.FileHeader       (from type-8 block)
      → decryptor.Decryptor          (seeds from header, XOR decrypt)
      → list[Block]                  (typed, decrypted)
  → game_state.load_game()
      → GameState (planets, fleets, designs, settings)
  → binary/<module>.decode_*(blocks)
      → strongly-typed dataclass per block
  → order_serializer → writes .m# back to disk
  → app.py Flask API → web UI
```

## Dependencies

- Python 3.11+ stdlib (`struct`, `os`, `dataclasses`, `hashlib`, `subprocess`)
- Flask (web server)
- No external dependencies for core parsing

## MANIFEST

Machine-readable file list for quality gate verification.

### FILES
- INVENTORY.md
- __init__.py
- app.py
- block_reader.py
- changelog.json
- decryptor.py
- file_header.py
- game_state.py
- lifecycle.py
- order_serializer.py
- planet_names.py
- port_manager.py
- run.py
- stars_random.py
- stars_string.py
- status.py
- web_builder.py

### FOLDERS
- automation/
- binary/
- static/
- templates/
