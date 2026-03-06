# INVENTORY — src/stars_web/binary/

Standalone binary block decoders for Stars! file format block types.
Each module handles one or more block type IDs and is independent of `game_state.py`.

## Block Type → Module Map

| Block Type | Module | Classes / Key Exports | Sizes (bytes) | Status |
|------------|--------|-----------------------|---------------|--------|
| 6  | player_race.py | `PlayerCompact`, `PlayerRaceData` | 15–144 | ✅ complete |
| 12 | event.py | `Event`, `EventType` | variable | ✅ complete |
| 13/14 | planet.py | `PlanetDetail` | 20–44 | ✅ complete |
| 16/17 | fleet.py | `FleetDetail` | 24–78 | ✅ complete |
| 19 | waypoint_task.py | `WaypointTask` | 10 (fixed) | ✅ complete |
| 20 | fleet_order.py | `FleetOrder` | 4 (fixed) | ✅ complete |
| 24 | turn_message.py | `TurnMessage` | variable | ✅ complete |
| 25 | game_object.py | `Minefield`, `Wormhole`, `Salvage`, `Packet` | variable | ✅ complete |
| 28 | production_queue.py | `ProductionItem`, `ProductionQueue` | variable | ✅ complete |
| 30 | battle_plan.py | `BattlePlan` | 6 per record | ✅ complete |
| 43 | ship_design.py | `ShipDesign`, `ShipDesignCount` | 2 or 18 | ✅ complete |
| 45 | player_scores.py | `PlayerScore` | 14 (fixed) | ✅ complete |
| EOF | file_footer.py | `FileFooter` | 6 (fixed) | ✅ complete |
| **26** | *(pending)* | FleetDetail variable-length | 13–78 | ❌ not started |
| **31** | *(pending)* | BattleCombatLog | 144–611 | ❌ not started |

## Files

| File | Block Type | Description |
|------|-----------|-------------|
| `__init__.py` | — | Re-exports all public symbols from every module |
| `battle_plan.py` | 30 | Decodes named battle plans (4 slots, 6 bytes each) |
| `event.py` | 12 | Decodes game event notifications with event type enum |
| `file_footer.py` | EOF | Decodes the end-of-file footer block (6 bytes, year/flags) |
| `fleet.py` | 16/17 | Decodes fleet records: partial (no cargo) vs full; supports ship counts |
| `fleet_order.py` | 20 | Decodes waypoint/order records: targeted vs open-space, 4 bytes fixed |
| `game_object.py` | 25 | Decodes passive map objects: minefields, wormholes, salvage, packets |
| `planet.py` | 13/14 | Decodes planet state: owner, population, mines, factories, hab, minerals |
| `player_race.py` | 6 | Decodes player/race data: compact summary (< 50 B) or full race descriptor (≥ 50 B) |
| `player_scores.py` | 45 | Decodes per-player score snapshot (14-byte fixed record) |
| `production_queue.py` | 28 | Decodes planet production queues: ordered list of build items |
| `ship_design.py` | 43 | Decodes ship designs: count record (2 B) or design record (18 B) |
| `turn_message.py` | 24 | Decodes in-game turn messages: text + action code |
| `waypoint_task.py` | 19 | Decodes waypoint tasks: destinations, fuel, cargo orders |

## Design Conventions

- Every module is **standalone** — imports only stdlib (`struct`, `dataclasses`)
- Every dataclass is **frozen** (`frozen=True`) for immutability and hashability
- Every `decode_*_block(data: bytes)` function raises `ValueError` on bad/short input
- Every `decode_*s(blocks: list)` batch function silently skips non-matching type IDs
- Property-based tests (Hypothesis) cover all decoders with round-trip checks
- Real game-file smoke tests run against `starswine4/` game data

## MANIFEST

Machine-readable file list for quality gate verification.

### FILES
- INVENTORY.md
- __init__.py
- battle_plan.py
- event.py
- file_footer.py
- fleet.py
- fleet_order.py
- game_object.py
- planet.py
- player_race.py
- player_scores.py
- production_queue.py
- ship_design.py
- turn_message.py
- waypoint_task.py

### FOLDERS
(none)
