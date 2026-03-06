import sys
from stars_web.block_reader import read_blocks


def main(filename):
    with open(filename, "rb") as f:
        data = f.read()
    blocks = read_blocks(data)
    for block in blocks:
        try:
            s = block.data.decode("ascii")
            if any(c.isalpha() for c in s):
                print(f"Type {block.type_id}, size {block.size}: {s}")
        except UnicodeDecodeError:
            pass


if __name__ == "__main__":
    for fn in sys.argv[1:]:
        main(fn)
