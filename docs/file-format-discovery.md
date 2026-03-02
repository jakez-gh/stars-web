# Reverse-Engineering Stars! File Formats: A Step-by-Step Tutorial

**Audience:** Anyone curious about binary file reverse engineering, or who wants to understand the Stars! (1995) save file format well enough to build tools around it.

**What you'll learn:** How to go from opaque `.m1` / `.hst` / `.xy` binary files to a working parser, using hex dumps, cross-referencing with a running game, and building on prior community work.

---

## Table of Contents

1. [Gathering Your Materials](#1-gathering-your-materials)
2. [First Look: Hex Dump Everything](#2-first-look-hex-dump-everything)
3. [Finding the Magic Bytes](#3-finding-the-magic-bytes)
4. [Prior Art: Standing on Shoulders](#4-prior-art-standing-on-shoulders)
5. [The Block Envelope](#5-the-block-envelope)
6. [Cracking the Encryption](#6-cracking-the-encryption)
7. [The Planets Block (Type 7): Your First Win](#7-the-planets-block-type-7-your-first-win)
8. [Planet Detail Blocks (Type 13/14): Variable-Length Hell](#8-planet-detail-blocks-type-1314-variable-length-hell)
9. [The frac_len Bug: When References Are Wrong](#9-the-frac_len-bug-when-references-are-wrong)
10. [Fleet Blocks (Type 16/17)](#10-fleet-blocks-type-1617)
11. [Cross-Verification: The Essential Loop](#11-cross-verification-the-essential-loop)
12. [Lessons & Tips](#12-lessons--tips)

---

## 1. Gathering Your Materials

Before you touch a hex editor, set yourself up:

1. **Install Stars! v2.6/2.7** — the original Windows game (runs fine under OTVDM or Wine).
2. **Create a test game** with known, simple settings:
   - Tiny universe, 2 players, Normal density.
   - Give it a memorable name like "Shooting Fish in a Barrel."
   - Pick a simple race (Jack of All Trades — no LRTs to complicate things).
3. **Play exactly one turn** so the first `.m1` file is generated.
4. **Screenshot everything** — planet summary, fleet list, production queue. You'll compare these against parsed output constantly.
5. **Copy the game files somewhere safe.** You need:
   - `Game.xy` — universe definition (planet positions, game settings)
   - `Game.m1` — player 1's turn file (your planets, fleets, designs)
   - `Game.m2` — player 2's turn file
   - `Game.hst` — host file (full game state)
   - `Game.h1`, `Game.h2` — history files

> **Tip:** Keep a second copy of the files. You'll re-read them hundreds of times, and it's easy to accidentally overwrite them by generating a new turn.

---

## 2. First Look: Hex Dump Everything

Open `Game.m1` in a hex editor (HxD, xxd, or Python):

```python
with open("Game.m1", "rb") as f:
    data = f.read()

# Print first 64 bytes
for i in range(0, min(64, len(data)), 16):
    hex_part = " ".join(f"{b:02x}" for b in data[i:i+16])
    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data[i:i+16])
    print(f"{i:04x}: {hex_part:<48} {ascii_part}")
```

You'll see something like:

```text
0000: 10 20 4a 33 4a 33 xx xx xx xx xx xx xx xx xx xx  . J3J3..........
0010: xx xx xx xx xx xx xx xx xx xx xx xx xx xx xx xx  ................
```

Two things jump out immediately:

- `4a 33 4a 33` = ASCII `J3J3` — a magic signature at offset 2
- The first two bytes (`10 20`) are *not* part of the magic — they're something else

Everything after the first ~18 bytes looks like noise. That's because most of the file is encrypted.

---

## 3. Finding the Magic Bytes

Open every file type and look for that `J3J3`:

```python
for ext in ["xy", "m1", "m2", "hst", "h1", "h2"]:
    with open(f"Game.{ext}", "rb") as f:
        data = f.read(20)
    j3_pos = data.find(b"J3J3")
    print(f"Game.{ext}: J3J3 at offset {j3_pos}")
```

Every file has `J3J3` at offset 2. This tells you:

- Bytes 0-1 are a 2-byte prefix (some kind of header for the header)
- Bytes 2-17 are a fixed, readable structure

Look at that 2-byte prefix in binary. For our file it's `0x2010`:

- `0x2010` as a uint16 LE = `0x2010` → binary: `0010 0000 0001 0000`
- Upper 6 bits: `001000` = 8
- Lower 10 bits: `0000010000` = 16

So: type_id=8, size=16. This becomes The Block Header format (more on this next).

---

## 4. Prior Art: Standing on Shoulders

Before reinventing the wheel, search for existing work:

- **[stars-4x/starsapi-python](https://github.com/stars-4x/starsapi-python)** by raptor (2014) — Python reference implementation with PRNG, decryption, and basic block parsing. This is the Rosetta Stone.
- **[stars-4x/starsapi](https://github.com/stars-4x/starsapi)** — Java version with more complete block type documentation (planet blocks, fleet blocks, player blocks).
- **stars-research** and various community wikis — scattered format notes.

> **Critical lesson:** Prior art is invaluable but not infallible. We found at least one confirmed bug in the reference implementations (the `frac_len` calculation — see section 9). Always verify against your own hex dumps.

Read through the reference code to understand the overall architecture. Here's what you'll learn:

1. Every Stars! file is a sequence of **blocks**.
2. The first block is always a **file header** (type 8), unencrypted.
3. All subsequent blocks are **XOR-encrypted** using a PRNG seeded from the file header.
4. The file ends with a **footer block** (type 0), unencrypted.

---

## 5. The Block Envelope

Every block starts with a 2-byte header:

```text
uint16 LE:
  bits 10-15: type_id (6 bits → 0-63)
  bits 0-9:   size (10 bits → 0-1023 bytes)
```

Reading blocks is just a loop:

```python
offset = 0
while offset + 2 <= len(file_bytes):
    header = int.from_bytes(file_bytes[offset:offset+2], "little")
    type_id = header >> 10
    size = header & 0x3FF
    offset += 2

    block_data = file_bytes[offset:offset+size]
    offset += size
    # ... do something with (type_id, size, block_data)
```

Known block types from the reference implementations:

| type_id | Name             | Found in         |
|---------|------------------|------------------|
| 0       | File footer      | All files        |
| 6       | Player/Race      | .m#, .hst        |
| 7       | Planets (map)    | .xy, .hst        |
| 8       | File header      | All files        |
| 13      | Planet (full)    | .hst, .m# (own)  |
| 14      | Planet (partial) | .m# (scanned)    |
| 16      | Fleet (full)     | .hst, .m# (own)  |
| 17      | Fleet (partial)  | .m# (other's)    |
| 20      | Waypoints        | .m#              |
| 26      | Ship design      | .m#, .hst        |
| 28      | Production queue | .m#              |
| 30      | Battle plans     | .m#              |

---

## 6. Cracking the Encryption

The file header block (type 8, always the first block) contains 16 bytes that initialize decryption:

```text
Offset  Size  Field
0-3     4     Magic "J3J3"
4-7     4     game_id (uint32)
8-9     2     version (packed: major[4]|minor[7]|increment[5])
10-11   2     turn (uint16, year = 2400 + turn)
12-13   2     player_data (packed: salt[11 upper]|player[5 lower])
14      1     file_type (0=xy, 1=x#, 2=hst, 3=m#, 4=h#, 5=r#)
15      1     flags (bit0=submitted, bit1=host_using, etc.)
```

### The PRNG

Stars! uses **L'Ecuyer's Combined Linear Congruential Generator** — two independent LCGs whose outputs are combined:

```text
Generator A: multiplier=40014, modulus=2147483563 (0x7FFFFFAB)
Generator B: multiplier=40692, modulus=2147483399 (0x7FFFFF07)
```

Each call to `next_random()` advances both generators and returns a 32-bit value:

```python
def next_random(self):
    # Advance A: Schrage's method to avoid overflow
    a1 = (self.seed_a % 53668) * 40014
    a2 = (self.seed_a // 53668) * 12211
    self.seed_a = a1 - a2
    if self.seed_a < 0:
        self.seed_a += 0x7FFFFFAB

    # Advance B
    b1 = (self.seed_b % 52774) * 40692
    b2 = (self.seed_b // 52774) * 3791
    self.seed_b = b1 - b2
    if self.seed_b < 0:
        self.seed_b += 0x7FFFFF07

    result = self.seed_a - self.seed_b
    if self.seed_a < self.seed_b:
        result += 0x100000000  # Wrap to unsigned 32-bit
    return result
```

### Seed Derivation

The seeds come from a **primes table** — the first 64 primes starting from 3, except that index 55 contains 279 instead of the expected 269. This matches the original Stars! binary exactly.

The 11-bit salt from the file header selects two prime indices:

```python
index1 = salt & 0x1F          # Lower 5 bits → 0-31
index2 = (salt >> 5) & 0x1F   # Middle 5 bits → 0-31

if (salt >> 10) == 1:          # Top bit
    index1 += 32               # First index into upper half
else:
    index2 += 32               # Second index into upper half

seed1 = primes[index1]
seed2 = primes[index2]
```

The PRNG is then advanced for `init_rounds` before use:

```python
part2 = (player_index & 3) + 1
part3 = (turn & 3) + 1
part4 = (game_id & 3) + 1
rounds = part4 * part3 * part2  # + 1 if shareware
```

### Decryption

Each encrypted block is XOR'd in 4-byte chunks (little-endian):

```python
# Pad to 4-byte boundary
for i in range(0, padded_size, 4):
    chunk = data[i] | (data[i+1]<<8) | (data[i+2]<<16) | (data[i+3]<<24)
    decrypted_chunk = chunk ^ prng.next_random()
    # Write 4 decrypted bytes back (little-endian)
```

> **How to verify this works:** Decrypt a block and look for sensible values. Planet blocks should contain coordinates that fall within the map bounds. If you see garbage, your PRNG or seed derivation is wrong.

---

## 7. The Planets Block (Type 7): Your First Win

The type-7 block in the `.xy` file is the best place to start because it contains readable game settings and planet positions. After decryption:

```text
Offset  Size  Field
0-3     4     (unknown header)
4-5     2     universe_size (0=Tiny, 1=Small, 2=Medium, 3=Large, 4=Huge)
6-7     2     density (0=Sparse, 1=Normal, 2=Dense, 3=Packed)
8-9     2     player_count
10-11   2     planet_count
12-13   2     starting_distance
16-17   2     game_settings_bits (flags for beginner minerals, slow tech, etc.)
32-63   32    game_name (null-terminated ASCII)
```

**The twist:** After the encrypted block data, there are `planet_count × 4` bytes of **unencrypted** planet coordinate data appended directly:

```python
# Each planet is a 32-bit word:
planet_word = uint32 LE
name_id  = planet_word >> 22          # 10 bits → index into planet name table
y        = (planet_word >> 10) & 0xFFF # 12 bits → Y coordinate
x_offset = planet_word & 0x3FF        # 10 bits → delta from previous X

# X coordinates are cumulative:
x = 1000  # Starting value
for each planet:
    x = x + x_offset
```

### How to verify

Compare parsed planet names and coordinates against the game screen:

1. Take a screenshot of the star map.
2. Parse the `.xy` file.
3. Check that your homeworld name matches.
4. Check that the planet count matches.
5. Check that coordinates are within the expected range for a Tiny universe (~1000-1800).

This was our first successful cross-validation — Blossom at (1254, 1200) matched the star map exactly.

---

## 8. Planet Detail Blocks (Type 13/14): Variable-Length Hell

Type-13 (full detail) and type-14 (partial/scanned) planet blocks appear in `.m#` files. They contain the juicy data — population, minerals, installations — but the format is **variable-length** and **flag-driven**.

### Fixed Header (4 bytes)

```text
Byte 0:   planet_number[7:0]
Byte 1:   planet_number[10:8] (bits 0-2) | owner[4:0] (bits 3-7)
Bytes 2-3: flags (uint16 LE)
```

Owner value 31 (0x1F) means unowned.

### Flag Bits

```text
Bit 0:  NOT remote mining (inverted meaning!)
Bit 1:  has environment info
Bit 2:  is in use
Bit 7:  is homeworld
Bit 9:  has starbase
Bit 10: is terraformed
Bit 11: has installations
Bit 12: has artifact
Bit 13: has surface minerals
Bit 14: has route/destination
```

### Variable Sections

After the 4-byte header, the block contains zero or more **optional sections** based on the flags. You must parse them in order — there are no offset pointers, just sequential data:

**Section 1: Environment** (if visible — determined by a combination of flags)

```text
1 byte:  pre_env_byte — encodes fractional concentration lengths
         frac_len = ((byte>>4)&3) + ((byte>>2)&3) + (byte&3)
N bytes: fractional mineral concentration data (frac_len bytes)
6 bytes: ironium_conc, boranium_conc, germanium_conc, gravity, temperature, radiation
3 bytes: (if terraformed) original gravity, temp, rad
2 bytes: (if owned) estimates
```

**Section 2: Surface Minerals** (if has_surface_minerals or is_in_use)

Uses a **variable-length integer encoding** that's worth understanding:

```text
1 byte: length code byte
  bits 0-1: ironium code
  bits 2-3: boranium code
  bits 4-5: germanium code
  bits 6-7: population code

Code → byte count:
  0 → 0 bytes (value is 0)
  1 → 1 byte  (uint8)
  2 → 2 bytes (uint16 LE)
  3 → 4 bytes (uint32 LE)
```

Population is stored in hundreds (divide by 100 for display... or rather, multiply the stored value by 100).

**Section 3: Installations** (if has_installations)

```text
1 byte:  excess population
1 byte:  mines_low (lower 8 bits)
1 byte:  packed — mines_high[3:0] (lower 4 bits) | factories_low[3:0] (upper 4 bits)
1 byte:  factories_high (upper 8 bits shifted by 4)
1 byte:  defenses
3 bytes: unknown/scanner/padding

mines     = mines_low | ((packed & 0x0F) << 8)
factories = ((packed & 0xF0) >> 4) | (factories_high << 4)
```

### Worked Example: Blossom (Type-13, 37 bytes)

Here's a real hex dump with annotations:

```text
Offset  Hex         Meaning
------  ----------  -------
0-1     11 00       planet_number = 0x011 & 0x7FF = 17, owner = (0x00>>3) = 0
2-3     86 2E       flags = 0x2E86 → homeworld, has_env, in_use, has_starbase,
                    has_installations, has_surface_minerals
4       FF          pre_env_byte = 0xFF → frac_len = 3+3+3 = 9
5-13    (9 bytes)   fractional mineral concentration data
14-19   47 59 47    ironium_conc=71, boranium_conc=89, germanium_conc=71
        32 3C 37    gravity=50, temperature=60, radiation=55
20-21   xx xx       estimates (2 bytes, planet is owned)
22      FB          surface mineral length codes:
                    iron=3(4B), bor=2(2B), germ=2(2B), pop=3(4B)
23-26   FB 02 00 00 ironium = 0x000002FB = 763
27-28   2D 02       boranium = 0x022D = 557
29-30   AA 01       germanium = 0x01AA = 426
31-34   0C 01 00 00 population_raw = 0x0000010C = 268 → 268 × 100 = 26,800
35      00          excess population
36      0A          mines_low = 10
37      C0          packed: mines_high=0, factories_low=0xC → mines=10, ...
38      00          factories_high = 0 → factories = (0xC0>>4)|0 = 12
39      0A          defenses = 10
40-42   xx xx xx    unknown/scanner bytes

Total: 4 + 1 + 9 + 6 + 2 + 1 + 4 + 2 + 2 + 4 + 1 + 1 + 1 + 1 + 4 = 37 ✓
```

---

## 9. The frac_len Bug: When References Are Wrong

Both the Java and Python reference implementations calculate `frac_len` as:

```java
// Reference code (WRONG)
frac_len = 1 + ((byte>>4)&3) + ((byte>>2)&3) + (byte&3);
```

We found this is **wrong** through careful byte counting.

### The Proof

Type-14 planet 17 (a partial/scanned planet): total block size = 11 bytes.

```text
4 bytes: fixed header
1 byte:  pre_env_byte = 0x00
? bytes: frac data
6 bytes: conc/hab data
```

With `1 +` : frac_len = 1+0+0+0 = 1 → total = 4+1+1+6 = **12 bytes** (OVERFLOWS the 11-byte block!)
Without `1+`: frac_len = 0+0+0 = 0 → total = 4+1+0+6 = **11 bytes** (EXACT FIT ✓)

The `1 +` was an error in the reference implementations. Our correct formula:

```python
frac_len = ((pre_env_byte >> 4) & 3) + ((pre_env_byte >> 2) & 3) + (pre_env_byte & 3)
```

### The Lesson

**Never trust a reference implementation blindly.** Even well-regarded community code that's been around for years can contain bugs. The only reliable authority is the hex dump of your actual game files, cross-checked against the running game's display.

---

## 10. Fleet Blocks (Type 16/17)

Fleet blocks are simpler than planets but still variable-length.

### Fixed Header (14 bytes)

```text
Byte 0:   fleet_number[7:0]
Byte 1:   fleet_number[8] (bit 0) | owner[6:0] (bits 1-7)
Bytes 2-3: (unknown)
Byte 4:   kind (0=write, 4=has cargo, 7=full data)
Byte 5:   flags (bit 3: if CLEAR, ship counts are 2 bytes each)
Bytes 6-7: (unknown)
Bytes 8-9: x position (uint16 LE)
Bytes 10-11: y position (uint16 LE)
Bytes 12-13: ship_types_mask (uint16 LE — one bit per ship design slot)
```

### Variable Ship Counts

For each bit set in `ship_types_mask`, read either 1 or 2 bytes depending on the flag at byte 5, bit 3:

```python
ship_count_two_bytes = (data[5] & 0x08) == 0  # Note: inverted!
for bit in range(16):
    if ship_types_mask & (1 << bit):
        if ship_count_two_bytes:
            count = uint16 at offset
        else:
            count = uint8 at offset
```

---

## 11. Cross-Verification: The Essential Loop

The single most important technique in this entire process:

1. **Parse values from the binary file.**
2. **Compare against the fat client display.** Take screenshots of planet summary, production, fleet list.
3. **If they don't match, investigate.** The binary is always right (it's what the game reads). Your parser is probably wrong.
4. **Watch for turn differences.** Your screenshots might be from turn N+1 while your data files are from turn N. Population grows, minerals are mined, factories get built. A population of 26,800 at turn 1 becomes 28,800 at turn 2 — that's not a parsing bug, that's game mechanics.

### Cross-Verification Checklist

For each field you parse, verify against the game:

- [ ] Planet names match the star map
- [ ] Planet coordinates place them in the right relative positions
- [ ] Population matches the planet summary screen
- [ ] Mineral amounts match
- [ ] Mine/factory/defense counts match
- [ ] Mineral concentrations match
- [ ] Fleet positions match the fleet list screen
- [ ] Ship counts match

We found that our test data files are **turn 1** (year 2401) while our screenshots were **turn 2** (year 2402). This explained every "wrong" value — population growth, mineral mining, factory construction all accounted for the differences.

---

## 12. Lessons & Tips

### Starting Out

- **Start with the `.xy` file.** It has the simplest structure and gives you planet names and positions — immediate visual feedback.
- **Build a test suite immediately.** Every fact you discover about a field gets a test. When you refactor your parser, these tests catch regressions.
- **Use TDD.** Write the test first ("`Blossom` should be at position (1254, 1200)"), then write the parser to make it pass.

### Debugging Binary Formats

- **Count bytes manually.** When a variable-length block doesn't parse right, hex dump it and annotate every byte by hand. This is how we caught the `frac_len` bug.
- **Check block boundaries.** If your parsed data overflows or underflows the block size, something is wrong.
- **Print intermediate values.** When debugging, print every parsed field, every offset advancement, and the remaining byte count.

### Working With the Community

- **Multiple reference implementations exist** — cross-reference them. The Java version has more complete documentation. The Python version has cleaner code flow.
- **The primes table has a known anomaly** — index 55 is 279 instead of 269. This is intentional in the original Stars! binary. Don't "fix" it.

### Common Pitfalls

| Pitfall                          | Symptom                                      | Fix                                        |
|----------------------------------|----------------------------------------------|--------------------------------------------|
| Wrong byte order                 | Coordinates are nonsensical                  | Stars! uses little-endian everywhere       |
| PRNG matches but data is garbage | First block decrypts fine, subsequent don't  | Check init_rounds calculation              |
| Population off by 100x           | 268 instead of 26,800                        | Population is stored in hundreds           |
| Turn mismatch                    | Values close but not exact                   | Screenshots are N+1, files are N           |
| frac_len +1                      | Block overflow on small planets              | Remove the erroneous +1                    |
| Owner = 31                       | Planet appears owned                         | 31 means unowned (sentinel value)          |

---

## Tools Used

- **Python 3.11** with `struct` for binary parsing
- **pytest** for test-driven development
- **HxD / Python hex dumps** for manual byte analysis
- **Stars! v2.7j r1** fat client for cross-verification screenshots
- **Git** for tracking every discovery as a commit

---

*This document was written alongside active development of a Stars! web client. Every format detail above was verified against real game files with passing tests.*
