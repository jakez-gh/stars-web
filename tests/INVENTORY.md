# INVENTORY — tests/

pytest test suite for the stars_web library. All tests use real game data files
from the autoplay repo (`../autoplay/tests/data/Game.*`).

## Files

| File | Description | Test Count |
| ---- | ----------- | ---------- |
| __init__.py | Package marker (empty) | — |
| test_stars_random.py | PRNG seed init, deterministic output, negative seed correction | 8 |
| test_decryptor.py | Salt→prime index mapping, init rounds, XOR decryption | 13 |
| test_file_header.py | Magic validation, field extraction, flag parsing | 20 |
| test_block_reader.py | Block envelope parsing, decryption integration, type-7 extra data | 9 |
| test_integration.py | End-to-end: read real files, verify planet names/positions/counts | 29 |
| test_game_state.py | Game settings, planet state (Blossom), fleets, load_game API | 39 |
| test_app.py | Flask app factory, API JSON, HTML page, error handling | 12 |
| test_ship_designs.py | Stars! string decoding, ShipDesign dataclass, design block parsing, real file integration | 18 |

## Total: 148 tests

## Test Data

Tests depend on game data files at `../../autoplay/tests/data/`:

- `Game.xy` — universe definition (turn 0)
- `Game.m1` — player 1 turn file (turn 1, year 2401)
- `Game.hst` — host file (turn 1)
- `Game.h1`, `Game.h2` — history files

Tests that require data files skip gracefully if the path doesn't exist.

## Running

```bash
python -m pytest              # all 130 tests
python -m pytest -k "blossom" # just Blossom planet tests
python -m pytest --cov        # with coverage
```
