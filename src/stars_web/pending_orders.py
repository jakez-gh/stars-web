"""Persistent storage for pending turn orders.

Zero Flask dependency — importable by the Flask API, the MCP server,
or any other consumer without pulling in the web framework.

Sidecar file schema (.orders_pending.json):

    {
      "waypoints":   {"7":  [{"x": 150, "y": 225, "warp": 6, "task": "None"}]},
      "production":  {"42": [{"name": "Factory", "quantity": 10, ...}]},
      "research":    {"field": "weapons", "resources": 50}
    }
"""

from __future__ import annotations

import json
import os

SIDECAR_FILENAME = ".orders_pending.json"

_EMPTY: dict = {"waypoints": {}, "production": {}, "research": {}}


def sidecar_path(game_dir: str) -> str:
    """Return absolute path for the pending-orders JSON sidecar file."""
    return os.path.join(game_dir, SIDECAR_FILENAME)


def load_pending_orders(game_dir: str) -> dict:
    """Load pending orders from the sidecar file.

    Returns a dict of the form::

        {"waypoints": {fleet_id: [...], ...},
         "production": {planet_id: [...], ...},
         "research": {"field": str, "resources": int} or {}}

    Silently returns empty dicts on missing or malformed files.
    """
    path = sidecar_path(game_dir)
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            # JSON keys are strings; convert fleet/planet ids back to int
            waypoints = {int(k): v for k, v in data.get("waypoints", {}).items()}
            production = {int(k): v for k, v in data.get("production", {}).items()}
            research = data.get("research", {})
            return {"waypoints": waypoints, "production": production, "research": research}
    except Exception:
        pass  # corrupted sidecar — start with empty state
    return {"waypoints": {}, "production": {}, "research": {}}


def save_pending_orders(
    game_dir: str,
    waypoints: dict,
    production: dict,
    research: dict,
) -> None:
    """Write current pending-orders state atomically (temp-rename).

    Silently skips if the directory is read-only (e.g. test fixtures).
    """
    path = sidecar_path(game_dir)
    tmp = path + ".tmp"
    data = {
        "waypoints": {str(k): v for k, v in waypoints.items()},
        "production": {str(k): v for k, v in production.items()},
        "research": research,
    }
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)  # atomic on POSIX; best-effort on Windows
    except OSError:
        pass


def delete_sidecar(game_dir: str) -> None:
    """Remove the sidecar file after a successful turn submission."""
    try:
        os.remove(sidecar_path(game_dir))
    except FileNotFoundError:
        pass
