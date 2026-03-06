#!/usr/bin/env python3
"""Analyze message blocks in a real game file."""

from stars_web.block_reader import read_blocks


def analyze_game_file(filename):
    """Dump all blocks with their type and size."""
    with open(filename, "rb") as f:
        data = f.read()

    blocks = read_blocks(data)

    print(f"\nFile: {filename}")
    print(f"Total blocks: {len(blocks)}\n")

    for i, block in enumerate(blocks):
        print(f"Block {i}: Type {block.type_id:2d}, Size {block.size:4d} bytes", end="")

        if block.type_id == 24:
            print(" [MESSAGE]", end="")
            # Try to extract fields
            if len(block.data) >= 7:
                print(f"\n    First 20 bytes (hex): {block.data[:20].hex()}")
                print(f"    First 20 bytes (repr): {repr(block.data[:20])}")
                try:
                    # Try to decode as ASCII
                    text = block.data.decode("ascii", errors="ignore")
                    if text:
                        print(f"    Text content: {text[:100]}")
                except:
                    pass
        else:
            try:
                s = block.data.decode("ascii", errors="ignore").strip()
                if s and len(s) < 100:
                    print(f": {s}")
                else:
                    print()
            except:
                print()


if __name__ == "__main__":
    for file in [
        "c:/Users/jake/Documents/stars/autoplay/tests/data/Game.m1",
        "c:/Users/jake/Documents/stars/starswine4/Game.m1",
    ]:
        try:
            analyze_game_file(file)
        except FileNotFoundError:
            print(f"File not found: {file}")
