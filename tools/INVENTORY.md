# INVENTORY — tools/

Developer utilities for debugging binary file formats and enforcing documentation quality.
These scripts are run manually or via pre-commit — they are **not** part of the installed package.

## Files

| File | Description |
| ---- | ----------- |
| `INVENTORY.md` | This file |
| `analyze_message_blocks.py` | Dumps all blocks from a game file, annotating Type 24 message blocks with hex + ASCII content |
| `tools_dump_blocks.py` | Prints any block whose raw data decodes as printable ASCII — useful for finding text in unknown blocks |
| `check_inventory.py` | Inventory quality gate: parses MANIFEST sections in all INVENTORY.md files and fails if any file/folder is undocumented |

## Usage

```powershell
# Dump message blocks from a game file
py -3.11 tools/analyze_message_blocks.py ../starswine4/Game.m1

# Dump ASCII-readable blocks
py -3.11 tools/tools_dump_blocks.py ../starswine4/Game.m1

# Run inventory quality gate (also runs as pre-commit hook)
py -3.11 tools/check_inventory.py
```

## MANIFEST

### FILES

- INVENTORY.md
- analyze_message_blocks.py
- check_inventory.py
- tools_dump_blocks.py

### FOLDERS

(none)
