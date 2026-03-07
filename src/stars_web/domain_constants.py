"""Stars! domain constants shared across all consumers.

Keeping these in a framework-free module lets the Flask API, the MCP
server, front-end validation helpers, and tests all import from one
canonical source without pulling in Flask or any other framework.
"""

from __future__ import annotations

# ── Research ──────────────────────────────────────────────────────────────────

RESEARCH_FIELDS: frozenset[str] = frozenset(
    {"energy", "weapons", "propulsion", "construction", "electronics", "biotechnology"}
)

# ── Waypoint tasks ────────────────────────────────────────────────────────────

WAYPOINT_TASKS: dict[int, str] = {
    0: "None",
    1: "Transport",
    2: "Colonize",
    3: "Remote Mining",
    4: "Merge with Fleet",
    5: "Scrap Fleet",
    6: "Lay Mine Field",
    7: "Patrol",
    8: "Route",
    9: "Transfer",
}
