"""Domain-object→dict serializers for Stars! game objects.

All functions are pure (no Flask, no I/O, no side-effects) so they can
be called from the Flask API, the MCP server, tests, or any other
consumer without coupling to a specific framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from stars_web.game_state import Fleet, Planet, PlayerRace, ShipDesign

if TYPE_CHECKING:
    from stars_web.binary.battle_record import BattleRecord
    from stars_web.binary.game_object import Minefield
    from stars_web.binary.player_scores import PlayerScore
    from stars_web.binary.turn_message import TurnMessage


# ── Production queue ──────────────────────────────────────────────────────────


def serialize_production_queue(
    planet_id: int,
    production_queues: dict,
    pending_prod: dict,
) -> list[dict]:
    """Return the effective production queue for *planet_id*.

    If a pending production override exists it replaces the parsed queue.
    """
    if planet_id in pending_prod:
        return pending_prod[planet_id]
    return [
        {
            "name": qi.item_name,
            "count": qi.count,
            "quantity": qi.count,
            "complete_percent": qi.complete_percent,
        }
        for qi in production_queues.get(planet_id, [])
    ]


# ── Planet ────────────────────────────────────────────────────────────────────


def serialize_planet(
    p: Planet,
    production_queues: dict,
    pending_prod: dict,
) -> dict:
    """Serialize a Planet to a JSON-safe dict including the effective queue."""
    return {
        "id": p.planet_id,
        "name": p.name,
        "x": p.x,
        "y": p.y,
        "owner": p.owner,
        "population": p.population,
        "mines": p.mines,
        "factories": p.factories,
        "defenses": p.defenses,
        "ironium": p.ironium,
        "boranium": p.boranium,
        "germanium": p.germanium,
        "ironium_conc": p.ironium_conc,
        "boranium_conc": p.boranium_conc,
        "germanium_conc": p.germanium_conc,
        "gravity": p.gravity,
        "temperature": p.temperature,
        "radiation": p.radiation,
        "has_starbase": p.has_starbase,
        "is_homeworld": p.is_homeworld,
        "production_queue": serialize_production_queue(
            p.planet_id, production_queues, pending_prod
        ),
    }


# ── Fleet ─────────────────────────────────────────────────────────────────────


def serialize_waypoints(fleet: Fleet, pending_wp: dict) -> list[dict]:
    """Return the effective waypoint list for *fleet*.

    If a pending waypoints override exists it replaces the parsed list.
    """
    if fleet.fleet_id in pending_wp:
        return pending_wp[fleet.fleet_id]
    return [{"x": wp.x, "y": wp.y, "warp": wp.warp, "task": wp.task_name} for wp in fleet.waypoints]


def serialize_fleet(f: Fleet, pending_wp: dict) -> dict:
    """Serialize a Fleet to a JSON-safe dict including effective waypoints."""
    return {
        "id": f.fleet_id,
        "name": f.name,
        "owner": f.owner,
        "x": f.x,
        "y": f.y,
        "ship_count": f.ship_count,
        "waypoints": serialize_waypoints(f, pending_wp),
    }


# ── Ship design ───────────────────────────────────────────────────────────────


def serialize_design_summary(d: ShipDesign) -> dict:
    """Compact design shape used in /api/game-state (no build stats)."""
    return {
        "id": d.design_number,
        "name": d.name,
        "hull_name": d.hull_name,
        "is_starbase": d.is_starbase,
    }


def serialize_design(d: ShipDesign) -> dict:
    """Full design shape used in /api/designs (all fields)."""
    return {
        "id": d.design_number,
        "name": d.name,
        "hull_id": d.hull_id,
        "hull_name": d.hull_name,
        "is_starbase": d.is_starbase,
        "armor": d.armor,
        "slot_count": d.slot_count,
        "turn_designed": d.turn_designed,
        "total_built": d.total_built,
        "total_remaining": d.total_remaining,
    }


# ── Player ────────────────────────────────────────────────────────────────────


def serialize_player(p: PlayerRace) -> dict:
    """Serialize a PlayerRace including tech levels when full data is present."""
    return {
        "player_number": p.player_number,
        "name": p.name_singular,
        "name_plural": p.name_plural,
        "ship_designs": p.ship_designs,
        "planets": p.planets,
        "fleets": p.fleets,
        "starbase_designs": p.starbase_designs,
        "logo": p.logo,
        "has_full_data": p.has_full_data,
        "prt": p.prt,
        "prt_name": p.prt_name,
        "tech": (
            {
                "energy": p.tech_energy,
                "weapons": p.tech_weapons,
                "propulsion": p.tech_propulsion,
                "construction": p.tech_construction,
                "electronics": p.tech_electronics,
                "biotech": p.tech_biotech,
            }
            if p.has_full_data
            else None
        ),
        "relations": p.relations,
    }


# ── Score ─────────────────────────────────────────────────────────────────────


def serialize_score(s: "PlayerScore") -> dict:
    """Serialize a PlayerScore snapshot."""
    return {
        "player_id": s.player_id,
        "num_planets": s.num_planets,
        "total_score": s.total_score,
        "resources_a": s.resources_a,
        "starbases": s.starbases,
        "ships_unarmed": s.ships_unarmed,
        "ships_escort": s.ships_escort,
        "ships_capital": s.ships_capital,
        "tech_score": s.tech_score,
        "rank": s.rank,
    }


# ── Battle ────────────────────────────────────────────────────────────────────


def serialize_battle(b: "BattleRecord") -> dict:
    """Serialize a BattleRecord summary."""
    return {
        "battle_id": b.battle_id,
        "x": b.x,
        "y": b.y,
        "num_tokens": b.num_tokens,
        "event_bytes": len(b.events_raw),
    }


# ── Minefield ─────────────────────────────────────────────────────────────────


def serialize_minefield(obj: "Minefield") -> dict:
    """Serialize a Minefield object."""
    return {
        "x": obj.x,
        "y": obj.y,
        "owner": obj.owner,
        "radius": obj.radius,
        "quantity": obj.quantity,
    }


# ── Message ───────────────────────────────────────────────────────────────────


def serialize_message(m: "TurnMessage") -> dict:
    """Serialize a TurnMessage."""
    return {"action_code": m.action_code, "text": m.text}
