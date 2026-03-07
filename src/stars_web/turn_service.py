"""Turn submission service.

Encapsulates the multi-step process of writing pending orders to a
.x1 file and invoking the Stars! host binary.  Zero Flask dependency —
callable from the Flask route **and** the future MCP ``submit_turn``
tool without duplicating the logic.

Responsibilities extracted from the former god-function
``api_submit_turn`` (#199):

1. ``detect_game_files`` — scan the game directory for .xy / .m# files
2. ``read_x1_turn``       — parse the .x1 file header to get turn number
3. ``build_and_write_orders`` — serialize pending orders into the .x1 file
4. ``run_host``           — invoke otvdm.exe + stars.exe
"""

from __future__ import annotations

import os
import subprocess


# ── File detection ────────────────────────────────────────────────────────────


def detect_game_files(game_dir: str) -> tuple[str, int]:
    """Return ``(game_prefix, player_num)`` for the game in *game_dir*.

    Raises:
        ValueError: if no .xy file or no .m# file is found.
    """
    xy_files = [f for f in os.listdir(game_dir) if f.lower().endswith(".xy")]
    if not xy_files:
        raise ValueError("No .xy file found in game directory")
    prefix = xy_files[0].rsplit(".", 1)[0]

    m_files = sorted(
        f
        for f in os.listdir(game_dir)
        if f.lower().startswith(prefix.lower() + ".m") and f[-1].isdigit()
    )
    if not m_files:
        raise ValueError("No .m# file found in game directory")

    player_num = int(m_files[0].rsplit(".m", 1)[1])
    return prefix, player_num


# ── Header reading ────────────────────────────────────────────────────────────


def read_x1_turn(game_dir: str, prefix: str, player_num: int) -> tuple[bytes, int]:
    """Read the .x1 file header and return ``(header_bytes, turn)``.

    Raises:
        ValueError: if the file is missing or cannot be parsed.
    """
    from stars_web.block_reader import read_blocks

    x1_path = os.path.join(game_dir, f"{prefix}.x{player_num}")
    if not os.path.exists(x1_path):
        raise ValueError(f"{prefix}.x{player_num} not found in game directory")

    with open(x1_path, "rb") as fh:
        source = fh.read()

    blocks = read_blocks(source)
    if not blocks or blocks[0].file_header is None:
        raise ValueError("Could not parse .x1 file header")

    return blocks[0].data, blocks[0].file_header.turn


# ── Order serialization ───────────────────────────────────────────────────────


def build_and_write_orders(
    game_dir: str,
    prefix: str,
    player_num: int,
    header_bytes: bytes,
    pending_wp: dict,
    pending_prod: dict,
) -> None:
    """Serialize *pending_wp* and *pending_prod* into the .x1 order file.

    Raises:
        ValueError: if a production item name is unrecognised.
    """
    from stars_web.domain_constants import WAYPOINT_TASKS
    from stars_web.order_serializer import (
        OBJ_TYPE_DEEP_SPACE,
        ProductionItem,
        ProductionQueueOrder,
        WaypointOrder,
        build_order_file,
    )

    task_name_to_id: dict[str, int] = {v: k for k, v in WAYPOINT_TASKS.items()}

    waypoint_orders: list[WaypointOrder] = []
    for fleet_id, wps in pending_wp.items():
        for wp in wps:
            raw_task = wp.get("task", 0)
            task_int = (
                task_name_to_id.get(raw_task, 0) if isinstance(raw_task, str) else int(raw_task)
            )
            waypoint_orders.append(
                WaypointOrder(
                    fleet_id=fleet_id,
                    x=int(wp["x"]),
                    y=int(wp["y"]),
                    warp=int(wp.get("warp", 5)),
                    task=task_int,
                    obj_type=OBJ_TYPE_DEEP_SPACE,
                )
            )

    production_orders: list[ProductionQueueOrder] = []
    for planet_id, items in pending_prod.items():
        prod_items = [ProductionItem.from_name(it["name"], int(it["quantity"])) for it in items]
        production_orders.append(ProductionQueueOrder(planet_id=planet_id, items=prod_items))

    x1_path = os.path.join(game_dir, f"{prefix}.x{player_num}")
    new_x1 = build_order_file(
        header_bytes,
        waypoint_orders=waypoint_orders,
        production_orders=production_orders,
    )
    with open(x1_path, "wb") as fh:
        fh.write(new_x1)


# ── Host invocation ───────────────────────────────────────────────────────────


def run_host(game_dir: str) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    """Invoke ``otvdm.exe stars.exe`` in *game_dir*.

    Raises:
        ValueError: if ``otvdm.exe`` is not found.
        subprocess.TimeoutExpired: if the host takes > 60 s.
        OSError: on other process-launch failures.
    """
    otvdm_path = os.path.join(game_dir, "otvdm", "otvdm.exe")
    stars_path = os.path.join(game_dir, "stars", "stars.exe")

    if not os.path.exists(otvdm_path):
        raise ValueError(f"Host launcher not found: {otvdm_path}")

    return subprocess.run(
        [otvdm_path, stars_path],
        cwd=game_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
