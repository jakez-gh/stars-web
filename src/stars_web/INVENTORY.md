# INVENTORY — src/stars_web/

Core library for parsing Stars! binary file formats and assembling game state.

## Files

| File | Description |
| ---- | ----------- |
| __init__.py | Package marker (empty) |
| stars_random.py | L'Ecuyer Combined LCG PRNG — used for XOR encryption |
| decryptor.py | Derives PRNG seeds from file header, decrypts block data |
| file_header.py | Parses the 16-byte file header (type 8 block): magic, game_id, turn, salt, player |
| block_reader.py | Reads a Stars! file into a list of typed/decrypted Block objects |
| planet_names.py | 999-entry lookup table mapping name_id → planet name string |
| stars_string.py | Decodes Stars! custom nibble-based text encoding used in design names |
| game_state.py | High-level loader: assembles GameState from .xy/.m#/.hst files. Parses planet blocks (type 13/14), fleet blocks (type 16/17), design blocks (type 26), production queues (type 28), waypoints (type 20), game settings (type 7) |

## Data Flow

```text
Game.xy / Game.m1 / Game.hst  (raw bytes)
  → block_reader.read_blocks()
      → file_header.FileHeader  (from type-8 block)
      → decryptor.Decryptor     (seeds from header, XOR decrypt)
      → list[Block]             (typed, decrypted)
  → game_state.load_game()
      → GameState (planets, fleets, designs, settings)
```

## Dependencies

- Python 3.11+ standard library only (`struct`, `os`, `dataclasses`)
- No external dependencies for the core library
