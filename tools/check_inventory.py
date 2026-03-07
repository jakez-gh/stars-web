#!/usr/bin/env python3
"""
Inventory Quality Gate — stars_web
====================================
Verifies that every INVENTORY.md MANIFEST section exactly matches the actual
contents of the directory that contains it.

Each INVENTORY.md may have a ## MANIFEST section with:

    ### FILES
    - filename.py
    - other.py

    ### FOLDERS
    - subfolder/
    - (none)          ← signals the list is intentionally empty

Rules enforced:
  ❌  A file/folder exists on disk but is absent from the MANIFEST list
  ⚠️   A name is in the MANIFEST but does not exist on disk (stale entry)

Exit codes:
  0 — all MANIFEST sections pass
  1 — one or more ❌ errors found
  2 — script error

Usage:
    py -3.11 tools/check_inventory.py            # check whole project
    py -3.11 tools/check_inventory.py src/       # check under src/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure Unicode emoji characters (✅ ❌ ⚠️) print correctly on Windows
# consoles that default to CP-1252.
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Items to ignore when scanning actual directory contents ──────────────────

ALWAYS_IGNORE: set[str] = {
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    ".ruff_cache",
    ".mypy_cache",
    ".git",
    ".venv",
    "node_modules",
    "htmlcov",
    "dist",
    "build",
    ".DS_Store",
    "Thumbs.db",
    "coverage.xml",
    ".coverage",
}

# Dot-prefixed items that are explicitly tracked (not ignored)
TRACKED_DOT_FILES: set[str] = {
    ".gitignore",
    ".gitattributes",
    ".markdownlint.json",
    ".pre-commit-config.yaml",
    ".github",
    ".githooks",
}


def should_ignore(name: str) -> bool:
    """Return True if this item should be excluded from inventory checks."""
    if name in ALWAYS_IGNORE:
        return True
    # Ignore dot-prefixed items unless explicitly tracked
    if name.startswith(".") and name not in TRACKED_DOT_FILES:
        return True
    # Ignore .pyc files
    if name.endswith(".pyc"):
        return True
    return False


# ── MANIFEST parser ────────────────────────────────────────────────────────────


def parse_manifest(inventory_path: Path) -> tuple[set[str], set[str]] | None:
    """
    Parse the ## MANIFEST section of an INVENTORY.md file.

    Returns (files, folders) or None if no MANIFEST section exists.
    Files and folders are returned as plain names (no trailing slash, no backticks).
    """
    content = inventory_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    in_manifest = False
    in_files = False
    in_folders = False
    files: set[str] = set()
    folders: set[str] = set()

    for line in lines:
        stripped = line.strip()

        if stripped == "## MANIFEST":
            in_manifest = True
            in_files = in_folders = False
            continue

        if not in_manifest:
            continue

        # Stop if we hit a new top-level section
        if stripped.startswith("## ") and stripped != "## MANIFEST":
            break

        if stripped == "### FILES":
            in_files = True
            in_folders = False
            continue

        if stripped == "### FOLDERS":
            in_files = False
            in_folders = True
            continue

        # Skip sub-section headers and blank lines
        if stripped.startswith("#") or not stripped:
            continue

        # Parse list items
        if stripped.startswith("- "):
            item = stripped[2:].strip()

            # Skip placeholder
            if item.lower() in {"(none)", "none"}:
                continue

            # Normalise: strip backticks, trailing slashes
            item = item.strip("`").rstrip("/")

            if in_files:
                files.add(item)
            elif in_folders:
                folders.add(item)

    if not in_manifest:
        return None  # No MANIFEST section — not checked

    return files, folders


# ── Directory scanner ─────────────────────────────────────────────────────────


def get_actual_items(directory: Path) -> tuple[set[str], set[str]]:
    """Return (files, folders) actually present in *directory* (one level only)."""
    files: set[str] = set()
    folders: set[str] = set()

    for item in directory.iterdir():
        if should_ignore(item.name):
            continue
        if item.is_dir():
            folders.add(item.name)
        else:
            files.add(item.name)

    return files, folders


# ── Checker ────────────────────────────────────────────────────────────────────


def check_directory(inventory_path: Path) -> list[str]:
    """
    Check one INVENTORY.md.

    Returns a list of issue strings (empty = pass).
    Lines starting with ❌ are hard failures; ⚠️ are warnings.
    """
    directory = inventory_path.parent
    result = parse_manifest(inventory_path)

    if result is None:
        return [f"⚠️  NO MANIFEST section in {inventory_path.relative_to(Path.cwd())}"]

    manifest_files, manifest_folders = result
    actual_files, actual_folders = get_actual_items(directory)

    issues: list[str] = []
    rel = str(inventory_path.parent.relative_to(Path.cwd())).replace("\\", "/")

    # Missing from MANIFEST (hard errors)
    for f in sorted(actual_files - manifest_files):
        issues.append(f"❌  [{rel}] FILE not in MANIFEST: {f}")
    for d in sorted(actual_folders - manifest_folders):
        issues.append(f"❌  [{rel}] FOLDER not in MANIFEST: {d}/")

    # In MANIFEST but not on disk (warnings — may be intentional, e.g., generated)
    for f in sorted(manifest_files - actual_files):
        issues.append(f"⚠️   [{rel}] MANIFEST lists FILE not on disk: {f}")
    for d in sorted(manifest_folders - actual_folders):
        issues.append(f"⚠️   [{rel}] MANIFEST lists FOLDER not on disk: {d}/")

    return issues


# ── Main ───────────────────────────────────────────────────────────────────────


def find_inventory_files(root: Path) -> list[Path]:
    """Recursively find all INVENTORY.md files under *root*, skipping ignored dirs."""
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories from traversal
        dirnames[:] = [d for d in dirnames if not should_ignore(d)]
        if "INVENTORY.md" in filenames:
            results.append(Path(dirpath) / "INVENTORY.md")
    return sorted(results)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    root = Path(argv[0]) if argv else Path.cwd()
    root = root.resolve()

    if not root.exists():
        print(f"❌  ERROR: path does not exist: {root}", file=sys.stderr)
        return 2

    inventory_files = find_inventory_files(root)
    if not inventory_files:
        print(f"⚠️  No INVENTORY.md files found under {root}")
        return 0

    all_issues: list[str] = []
    checked = 0
    skipped = 0

    for inv in inventory_files:
        issues = check_directory(inv)
        if issues and issues[0].startswith("⚠️  NO MANIFEST"):
            skipped += 1
        else:
            checked += 1
        all_issues.extend(issues)

    # Report
    errors = [i for i in all_issues if i.startswith("❌")]
    warnings = [i for i in all_issues if i.startswith("⚠️")]

    if all_issues:
        print()
        print("=" * 72)
        print("INVENTORY QUALITY GATE RESULTS")
        print("=" * 72)
        for issue in all_issues:
            print(issue)
        print()

    if errors:
        print(
            f"❌  FAILED — {len(errors)} error(s), {len(warnings)} warning(s) "
            f"across {checked} checked / {skipped} skipped (no MANIFEST)"
        )
        return 1

    print(
        f"✅  PASSED — {checked} INVENTORY.md files verified"
        + (f", {len(warnings)} warning(s)" if warnings else "")
        + (f", {skipped} without MANIFEST section (skipped)" if skipped else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
