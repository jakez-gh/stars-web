# .x1 Order File Binary Format

**Audience:** Developers implementing `.x1` order file generation for the Stars! web client.

**Status:** File header format **fully verified** against `starswine4/backup/Game.x1` and `Game-big.x1`. Waypoint and production queue **state** block formats verified against `autoplay/tests/data/Game.m1`. Waypoint and production queue **order** block formats are *inferred* from block-type constants and the starsapi Java reference — no sample `.x1` with actual orders was available for direct verification.

---

## Overview

`.x1` files (and `.x2`–`.x16` for other players) carry player orders from client → host each turn.
They use the same block-envelope framing as all other Stars! files:

- **File Type ID = 1** (turn files are type ≥ 6)
- Fully encrypted (all blocks after the file header)
- Structure: `FILE_HEADER` → *(order blocks)* → `FILE_HASH` → `FILE_FOOTER`

---

## Block Header (2 bytes, little-endian uint16)

Every block starts with a 2-byte header:

```text
bits 15-10  type_id   (6 bits, 0-63)
bits  9-0   size      (10 bits, 0-1023 bytes)

header = (type_id << 10) | size
```

Reading:

```python
import struct
hdr = struct.unpack_from("<H", data, offset)[0]
type_id = hdr >> 10
size    = hdr & 0x3FF
```

---

## File Header Block (type 8, 16 bytes — **unencrypted**)

The file header is always the first block and is **never encrypted**.

```text
Offset  Size  Field           Notes
------  ----  -----           -----
  0      2    block_header    type=8, size=16  (0x20 0x00 → header word = 0x2010)
  2      4    magic           ASCII "J3J3" = 0x4A334A33
  6      2    flags           encrypted flag, version info
  8      4    game_id         uint32 LE — seeds the decryptor
 12      2    turn            uint16 LE — Stars! turn number (year - 2400)
 14      2    player_info     bits 0-3 = player_index; bit 7 = shareware flag
 16      1    salt            PRNG seed byte
 17      1    padding
```

From `Game.x1` (player 1, year 2400, turn 0):

```text
4a 33 4a 33 0d 40 7b 38 60 2a 11 00 80 26 01 c0
```

- game_id at bytes 6-9: `7b 38 60 2a` = 0x60387b as uint32 (with player/turn in same word)
- turn at bytes 10-11: `11 00` = 0x0011 = 17 (year 2417)
- player at bytes 12-13: player index encoded in low nibble

From `Game-big.x1` (player 1, year 2400):

```text
4a 33 4a 33 04 01 de 01 60 2a 0b 00 a0 12 01 e0
```

---

## Block Types Relevant to Orders

### State blocks (found in `.m#` turn files, NOT orders files)

| ID | Name | Purpose |
|----|------|---------|
| 16 | FLEET | Full fleet data (position, ships, design references) |
| 20 | WAYPOINT | Single waypoint associated with the preceding FLEET block |
| 28 | PRODUCTION_QUEUE | Full planet production queue |

### Order blocks (found in `.x#` order files)

| ID | Name | Purpose |
|----|------|---------|
| 3  | WAYPOINT_DELETE | Remove a waypoint from a fleet's route |
| 4  | WAYPOINT_ADD | Append/insert a waypoint into a fleet's route |
| 5  | WAYPOINT_CHANGE_TASK | Modify the task at an existing waypoint |
| 10 | WAYPOINT_REPEAT_ORDERS | Set/clear repeat-orders flag for a fleet |
| 22 | PRODUCTION_QUEUE_CHANGE | Replace a planet's production queue |
| 29 | CHANGE_RESEARCH | Update tech research allocation |

---

## Waypoint State Block (type 20) — **VERIFIED**

Verified from `autoplay/tests/data/Game.m1` (5 waypoint blocks, each 8 bytes):

```text
Offset  Size  Field                Notes
------  ----  -----                -----
  0      2    x                    uint16 LE, planet/deep-space X coordinate
  2      2    y                    uint16 LE, planet/deep-space Y coordinate
  4      2    position_object      uint16 LE, target object ID (planet_id or 0)
  6      1    packed_warp_task     bits 7-4 = warp speed (0-9); bits 3-0 = task ID
  7      1    position_object_type 17=at a planet; 20=deep space
```

Task IDs (bits 3-0 of byte 6):

| ID | Task |
|----|------|
| 0  | None (transport/patrol) |
| 1  | Transport |
| 2  | Colonize |
| 3  | Remote Mining |
| 4  | Merge with Fleet |
| 5  | Scrap Fleet |

Real example — fleet orbiting planet #20, warp 5:

```text
Raw bytes:  f9 04 9f 04 14 00 50 11
            ─────── ─────── ───── ── ──
             x=1273  y=1183 obj=20 │  obj_type=17 (planet)
                                   └─ 0x50 = (5<<4)|0 → warp=5, task=None
```

### Fleet Block (type 16) — **VERIFIED**

The waypoint block immediately follows the fleet block it belongs to. Fleet block layout:

```text
Offset  Size  Field             Notes
------  ----  -----             -----
  0      1    fleet_number_lo   fleet_id bits 0-7
  1      1    packed_owner      bit 0 = fleet_number bit 8; bits 7-1 = owner (player index)
  2      2    unknown           always 0x0000 in samples
  4      1    kind              0x07=full fleet, others=partial/starbase
  5      1    ship_count_flags  bit 3=0 → 2-byte counts; bit 3=1 → 1-byte counts
  6      2    unknown           varies
  8      2    x                 uint16 LE
 10      2    y                 uint16 LE
 12      2    ship_types_mask   uint16 LE — bitmask of occupied design slots
 14+    var   ship_counts       1 or 2 bytes per set bit in ship_types_mask
 last    1    waypoint_count    total waypoints that follow (when kind=7)
```

`fleet_id = (data[0]) | ((data[1] & 0x01) << 8)`

Real example — fleet 0, player 0, position (1273, 1183), 1 ship:

```text
Block 14: 00 00 00 00 07 09 14 00 f9 04 9f 04 01 00 01 00 01 2f 00 00 00 01
          ──── ────  ── ── ──── ─────── ─────── ────── ── ── ── ── ──── ── ──
          id=0 own=0    kind=7  x=1273  y=1183 mask bit0=1   1 ship  wp=1(last)
```

---

## Production Queue State Block (type 28) — **VERIFIED**

Verified from `autoplay/tests/data/Game.m1`. The block is NOT prefixed with a planet_id — it is implicitly associated with the last partial-planet block (type 14) parsed before it.

Each queue item is exactly **4 bytes**:

```text
Byte  Bits   Field             Notes
----  -----  -----             -----
0-1   15-10  item_id           6 bits — item type ID (see table below)
0-1    9-0   count             10 bits — quantity (max 1023)
2-3   15-4   complete_percent  12 bits — partial completion %
2-3    3-0   item_type         4 bits — 2=standard structure, 4=ship/starbase design
```

Reading:

```python
chunk1 = struct.unpack_from("<H", data, i)[0]
chunk2 = struct.unpack_from("<H", data, i+2)[0]
item_id          = chunk1 >> 10
count            = chunk1 & 0x3FF
complete_percent = chunk2 >> 4
item_type        = chunk2 & 0xF
```

Standard item IDs (`item_type=2`):

| ID | Name |
|----|------|
| 0  | Auto Mines |
| 1  | Auto Factories |
| 2  | Auto Defenses |
| 3  | Auto Alchemy |
| 7  | Factory |
| 8  | Mine |
| 9  | Defense |
| 11 | Mineral Alchemy |
| 27 | Planetary Scanner |

Ship/starbase designs use `item_type=4`; `item_id` is the design slot index.

Real example — first item in `Game.m1` production queue (Factory ×1, 89% complete):

```text
Raw: 01 1c 92 05

chunk1 = 0x1c01 → item_id = 0x1c01 >> 10 = 7 (Factory)
                   count   = 0x1c01 & 0x3FF = 1
chunk2 = 0x0592 → complete_percent = 0x0592 >> 4 = 89
                   item_type        = 0x0592 & 0xF  = 2 (standard)
```

---

## Waypoint Order Blocks (types 3, 4, 5) — **INFERRED**

> ⚠️ Neither sample `.x1` contained these blocks. The layout below is inferred from
> the starsapi Java reference (`WaypointChangeTaskBlock.java`) and the known waypoint
> state block structure above. Verify empirically before writing a serializer.

### WAYPOINT_ADD (type 4) — inferred

Adds one waypoint to the end (or at a specific position) of a fleet's route.

```text
Offset  Size  Field                Notes
------  ----  -----                -----
  0      2    fleet_id             uint16 LE — matches fleet_number in FLEET block
  2      1    waypoint_index       insertion position; 0xFF = append
  3      1    padding              0x00
  4      2    x                    uint16 LE
  6      2    y                    uint16 LE
  8      2    position_object      uint16 LE
 10      1    packed_warp_task     same encoding as waypoint STATE block
 11      1    position_object_type same encoding as waypoint STATE block
```

Minimum block size: **12 bytes**.

### WAYPOINT_DELETE (type 3) — inferred

```text
Offset  Size  Field          Notes
------  ----  -----          -----
  0      2    fleet_id       uint16 LE
  2      1    waypoint_index 0-based index of waypoint to remove
  3      1    padding        0x00
```

### WAYPOINT_CHANGE_TASK (type 5) — inferred

```text
Offset  Size  Field          Notes
------  ----  -----          -----
  0      2    fleet_id       uint16 LE
  2      1    waypoint_index 0-based index
  3      1    packed_warp_task  same as STATE block byte 6
```

---

## Production Queue Order Block (type 22) — **INFERRED**

> ⚠️ Inferred — not verified against a real `.x1` sample.

Replaces a planet's production queue in full.

```text
Offset  Size  Field      Notes
------  ----  -----      -----
  0      2    planet_id  uint16 LE — planet index (same as planet_id in API)
  2+    4×n   items      same 4-byte per item encoding as STATE block (type 28)
```

---

## File Hash Block (type 9, 17 bytes — **VERIFIED**)

Both sample `.x1` files end with a type-9 block of 17 bytes.

```text
Offset  Size  Field   Notes
------  ----  -----   -----
  0      2    unknown always 0x0000 in samples
  2      1    check1  varies
  3-16  14    hash    CRC / checksum bytes
```

From `Game.x1`:    `00 00 d9 40 42 02 f3 00 00 00 00 f0 a5 dc a6 7a a0`
From `Game-big.x1`: `00 00 76 0a 6f 00 f3 00 00 00 00 f0 a5 dc a6 7a a0`

---

## Sample: Empty Orders File Layout

Both `starswine4/backup/Game.x1` and `Game-big.x1` contain no pending orders:

```text
Offset  Type  Size  Description
------  ----  ----  -----------
  0      8    18   File header (2-byte block header + 16 bytes of header data)
 18      9    19   File hash (2-byte block header + 17 bytes)
 37      0     2   File footer (type=0, size=0)
```

Total file size: **39 bytes** (verified for both samples).

---

## Python Skeleton: Parsing a `.x1` File

```python
import sys, struct
sys.path.insert(0, "path/to/stars_web/src")

from stars_web.block_reader import read_blocks

with open("Game.x1", "rb") as f:
    data = f.read()

blocks = read_blocks(data)   # handles decryption

for b in blocks:
    if b.type_id == 4:        # WAYPOINT_ADD
        fleet_id   = struct.unpack_from("<H", b.data, 0)[0]
        wp_index   = b.data[2]
        x          = struct.unpack_from("<H", b.data, 4)[0]
        y          = struct.unpack_from("<H", b.data, 6)[0]
        warp       = (b.data[10] >> 4) & 0xF
        task       = b.data[10] & 0xF
        print(f"Add waypoint to fleet {fleet_id}: ({x},{y}) warp={warp} task={task}")
    elif b.type_id == 22:     # PRODUCTION_QUEUE_CHANGE
        planet_id  = struct.unpack_from("<H", b.data, 0)[0]
        for i in range(2, len(b.data) - 3, 4):
            c1     = struct.unpack_from("<H", b.data, i)[0]
            c2     = struct.unpack_from("<H", b.data, i+2)[0]
            item   = c1 >> 10
            qty    = c1 & 0x3FF
            print(f"  Planet {planet_id}: item_id={item} qty={qty}")
```

---

## Related Documentation

- [Block Structure](../../../autoplay/docs/file-formats/block-structure.md)
- [Orders Files (high-level)](../../../autoplay/docs/file-formats/orders-files.md)
- [M# Turn Files](../../../autoplay/docs/file-formats/m-files.md)
- Block reader impl: [stars_web/src/stars_web/block_reader.py](../src/stars_web/block_reader.py)
- Game state parser: [stars_web/src/stars_web/game_state.py](../src/stars_web/game_state.py)

## References

- `stars-4x/starsapi` Java source (`WaypointChangeTaskBlock.java`, `ProductionQueue.java`)
- Verified against `starswine4/backup/Game.x1` and `starswine4/backup/Game-big.x1`
- State block formats verified against `autoplay/tests/data/Game.m1`
- `stars_web` decryptor: `stars_web.block_reader.read_blocks()` + `stars_web.decryptor.Decryptor`
