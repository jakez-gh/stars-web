# INVENTORY — tests/

pytest test suite for the stars_web library (1179 collected, 1176 passing, 84.42% coverage).
Game-data smoke tests use `../starswine4/` and `../../autoplay/tests/data/`.

## Files

| File | Module Under Test | Count |
| ---- | ----------------- | ----- |
| `__init__.py` | — (package marker) | — |
| `conftest.py` | — (shared fixtures) | — |
| `INVENTORY.md` | — (this file) | — |
| `test_app.py` | app.py (Flask factory, routes, API) | 88 |
| `test_automation.py` | automation/ (input, window, navigator, matcher) | 61 |
| `test_battle_plan.py` | binary/battle_plan.py (Type 30) | 46 |
| `test_battle_record.py` | binary/battle_record.py (Type 31 — BattleToken, BattleRecord) | 50 |
| `test_binary_player_race.py` | binary/player_race.py (Type 6) | 52 |
| `test_block_reader.py` | block_reader.py (envelope, decryption) | 9 |
| `test_decryptor.py` | decryptor.py (seeds, XOR) | 13 |
| `test_design_block.py` | binary/design_block.py (Type 26 — PartialDesign, FullDesign, DesignSlot) | 63 |
| `test_e2e.py` | End-to-end game flow (all skipped unless full env) | 0* |
| `test_event.py` | binary/event.py (Type 12) | 24 |
| `test_file_footer.py` | binary/file_footer.py (EOF block) | 22 |
| `test_file_header.py` | file_header.py (type-8 block) | 20 |
| `test_fleet.py` | binary/fleet.py (Types 16/17) | 89 |
| `test_fleet_order.py` | binary/fleet_order.py (Type 20) | 54 |
| `test_game_object.py` | binary/game_object.py (Type 25) | 36 |
| `test_game_state.py` | game_state.py (load_game, GameState API) | 39 |
| `test_integration.py` | End-to-end: real files, planet names/positions | 35 |
| `test_lifecycle.py` | lifecycle.py (process start/stop/detect) | 16 |
| `test_order_serializer.py` | order_serializer.py (binary round-trip) | 33 |
| `test_planet.py` | binary/planet.py (Types 13/14) | 55 |
| `test_player_race.py` | game_state.parse_player_block, PRT_NAMES (Type 6 via game_state) | 16 |
| `test_player_scores.py` | binary/player_scores.py (Type 45) | 60 |
| `test_port_manager.py` | port_manager.py (deterministic port allocation) | 14 |
| `test_production_queue.py` | binary/production_queue.py (Type 28) | 51 |
| `test_production_queues.py` | game_state.parse_production_queue_block (Type 28 via game_state) | 17 |
| `test_run.py` | run.py (server entry-point) | 4 |
| `test_ship_design.py` | binary/ship_design.py (Type 43) | 47 |
| `test_ship_designs.py` | game_state.ShipDesign, parse_design_block (Type 26 via game_state) | 18 |
| `test_stars_random.py` | stars_random.py (PRNG) | 8 |
| `test_status.py` | status.py (status polling) | 28 |
| `test_turn_message.py` | binary/turn_message.py (Type 24) | 29 |
| `test_waypoint_task.py` | binary/waypoint_task.py (Type 19) | 47 |
| `test_waypoints.py` | game_state waypoint parsing (Type 20 via game_state) | 16 |
| `test_web_builder.py` | web_builder.py (HTML star-map generation) | 19 |

*test_e2e.py: 29 tests collected but all deselected/skipped without full game environment.

## Total: 1179 collected (1176 passing, 3 skipped)

## Coverage: 84.42% (as of last full run)

## Test Data

| Source | Path | Used By |
| ------ | ---- | ------- |
| Multiplayer game files | `../starswine4/Game-big.m?` | binary/*.py smoke tests |
| Single-player game files | `../starswine4/Game.m?` | integration tests |
| autoplay test data | `../../autoplay/tests/data/Game.*` | unit + integration |

All file-dependent tests call `pytest.mark.skipif(not path.exists(), ...)` to skip gracefully.

## Naming Conventions

- `test_<module>.py` → tests `binary/<module>.py` directly (standalone decoder)
- `test_<module>s.py` (plural) → tests `game_state.parse_*_block()` API against same block type
- `test_binary_player_race.py` → binary/player_race.py (renamed to avoid conflict with test_player_race.py)

## Running

```bash
py -3.11 -m pytest              # all tests with coverage
py -3.11 -m pytest -k "planet"  # tests matching a keyword
py -3.11 -m pytest tests/test_binary_player_race.py -v  # single file
```

## MANIFEST

Machine-readable file list for quality gate verification.

### FILES

- INVENTORY.md
- __init__.py
- conftest.py
- test_app.py
- test_automation.py
- test_battle_plan.py
- test_battle_record.py
- test_binary_player_race.py
- test_block_reader.py
- test_decryptor.py
- test_design_block.py
- test_e2e.py
- test_event.py
- test_file_footer.py
- test_file_header.py
- test_fleet.py
- test_fleet_order.py
- test_game_object.py
- test_game_state.py
- test_integration.py
- test_lifecycle.py
- test_order_serializer.py
- test_planet.py
- test_player_race.py
- test_player_scores.py
- test_port_manager.py
- test_production_queue.py
- test_production_queues.py
- test_run.py
- test_ship_design.py
- test_ship_designs.py
- test_stars_random.py
- test_status.py
- test_turn_message.py
- test_waypoint_task.py
- test_waypoints.py
- test_web_builder.py

### FOLDERS

(none)
