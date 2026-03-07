"""Flask web application for Stars! game viewer.

Serves a star map UI that visualizes parsed game state from
Stars! binary save files.
"""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from stars_web.game_state import load_game

# Valid research fields accepted by POST /api/research
_RESEARCH_FIELDS = frozenset(
    {"energy", "weapons", "propulsion", "construction", "electronics", "biotechnology"}
)


def _sidecar_path(game_dir: str) -> str:
    """Return absolute path for the pending-orders JSON sidecar file."""
    return os.path.join(game_dir, ".orders_pending.json")


def _load_pending_orders(app: Flask) -> None:
    """Populate in-memory pending dicts from sidecar file (if present).

    Called once at startup so orders survive a server restart.
    Silently ignores missing or malformed files.
    """
    path = _sidecar_path(app.config["GAME_DIR"])
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # JSON keys are strings; convert fleet/planet ids back to int
            waypoints = data.get("waypoints", {})
            app.config["PENDING_WAYPOINTS"] = {int(k): v for k, v in waypoints.items()}
            production = data.get("production", {})
            app.config["PENDING_PRODUCTION"] = {int(k): v for k, v in production.items()}
            app.config["PENDING_RESEARCH"] = data.get("research", {})
    except Exception:
        pass  # corrupted sidecar — start with empty state


def _save_pending_orders(app: Flask) -> None:
    """Write current pending-orders state to sidecar file atomically (temp-rename).

    JSON schema::

        {
          "waypoints": {"7": [{"x": 150, "y": 225, "warp": 6, "task": "None"}]},
          "production": {"42": [{"name": "Factory", "quantity": 10, ...}]},
          "research": {"field": "weapons", "resources": 50}
        }
    """
    path = _sidecar_path(app.config["GAME_DIR"])
    tmp_path = path + ".tmp"
    data = {
        "waypoints": {str(k): v for k, v in app.config["PENDING_WAYPOINTS"].items()},
        "production": {str(k): v for k, v in app.config["PENDING_PRODUCTION"].items()},
        "research": app.config["PENDING_RESEARCH"],
    }
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)  # atomic on POSIX; best-effort on Windows
    except OSError:
        # Silently skip persistence if game dir is read-only (e.g., test fixtures)
        pass


def _delete_sidecar(app: Flask) -> None:
    """Remove sidecar file after successful turn submission."""
    path = _sidecar_path(app.config["GAME_DIR"])
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _load_cache_manifest() -> dict[str, str]:
    """Load cache-buster hashes from the manifest file.

    Returns a dict mapping asset names to their SHA256 hashes.
    If the manifest doesn't exist, returns empty dict (no cache-busting).
    """
    manifest_path = Path(__file__).parent / "static" / "._cache_manifest.json"
    try:
        if manifest_path.exists():
            with open(manifest_path) as f:
                data = json.load(f)
                return data.get("hashes", {})
    except Exception:
        pass
    return {}


def create_app(game_dir: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        game_dir: Path to directory containing Stars! game files.
                  Defaults to STARS_GAME_DIR env var or ../autoplay/tests/data.
    """
    app = Flask(__name__)

    if game_dir is None:
        game_dir = os.environ.get(
            "STARS_GAME_DIR",
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "autoplay",
                "tests",
                "data",
            ),
        )

    app.config["GAME_DIR"] = os.path.abspath(game_dir)
    # In-memory pending orders (not yet written to .x1)
    app.config["PENDING_WAYPOINTS"] = {}  # fleet_id -> [{x, y, warp, task}]
    app.config["PENDING_PRODUCTION"] = {}  # planet_id -> [{name, quantity}]
    app.config["PENDING_RESEARCH"] = {}  # {"field": str, "resources": int} or {}
    # Cache-buster hashes for web assets
    app.config["CACHE_HASHES"] = _load_cache_manifest()
    # Restore pending orders that survived a server restart
    _load_pending_orders(app)

    _changelog_path = os.path.join(os.path.dirname(__file__), "changelog.json")

    @app.route("/")
    def index():
        """Serve the star map page."""
        return render_template(
            "star_map.html",
            cache_hashes=app.config["CACHE_HASHES"],
        )

    @app.route("/api/changelog")
    def api_changelog():
        """Return current changelog entry so the UI can show a 'what's new' modal."""
        try:
            with open(_changelog_path, encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify({"id": "unknown", "title": "Changelog unavailable", "items": [str(e)]})

    @app.route("/api/game-state")
    def api_game_state():
        """Return parsed game state as JSON."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        pending_wp = app.config["PENDING_WAYPOINTS"]
        pending_prod = app.config["PENDING_PRODUCTION"]
        pending_research = app.config["PENDING_RESEARCH"]

        planets = []
        for p in state.planets:
            queue = state.production_queues.get(p.planet_id, [])
            serialized_queue = [
                {
                    "name": qi.item_name,
                    "count": qi.count,
                    "quantity": qi.count,
                    "complete_percent": qi.complete_percent,
                }
                for qi in queue
            ]
            # Merge any pending production orders (replace queue)
            if p.planet_id in pending_prod:
                serialized_queue = pending_prod[p.planet_id]

            planet_data = {
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
                "production_queue": serialized_queue,
            }
            planets.append(planet_data)

        fleets = []
        for f in state.fleets:
            waypoints = [
                {"x": wp.x, "y": wp.y, "warp": wp.warp, "task": wp.task_name} for wp in f.waypoints
            ]
            # Merge any pending waypoint orders (replace)
            if f.fleet_id in pending_wp:
                waypoints = pending_wp[f.fleet_id]

            fleets.append(
                {
                    "id": f.fleet_id,
                    "name": f.name,
                    "owner": f.owner,
                    "x": f.x,
                    "y": f.y,
                    "ship_count": f.ship_count,
                    "waypoints": waypoints,
                }
            )

        designs = [
            {
                "id": d.design_number,
                "name": d.name,
                "hull_name": d.hull_name,
                "owner": d.is_starbase,
                "is_starbase": d.is_starbase,
            }
            for d in state.designs
            if d.is_full_design
        ]

        return jsonify(
            {
                "game_id": state.game_id,
                "year": state.year,
                "turn": state.turn,
                "version": state.version,
                "player_index": state.player_index,
                "has_pending_orders": bool(pending_wp) or bool(pending_prod) or bool(pending_research),
                "settings": {
                    "game_name": state.settings.game_name,
                    "universe_size": state.settings.universe_size_label,
                    "density": state.settings.density_label,
                    "player_count": state.settings.player_count,
                    "planet_count": state.settings.planet_count,
                },
                "planets": planets,
                "fleets": fleets,
                "designs": designs,
                "pending_research": pending_research,
            }
        )

    @app.route("/api/fleet/<int:fleet_id>/waypoints", methods=["POST"])
    def api_fleet_waypoints(fleet_id: int):
        """Store pending waypoint orders for a fleet (in-memory; not yet serialized to .x1)."""
        body = request.get_json(silent=True) or {}
        if "waypoints" not in body:
            return jsonify({"error": "Missing 'waypoints' key"}), 400

        wps = body["waypoints"]
        for wp in wps:
            if "x" not in wp or "y" not in wp or "warp" not in wp:
                return jsonify({"error": "Each waypoint needs x, y, warp"}), 400

        # Normalise: ensure task key present
        stored = [
            {
                "x": int(wp["x"]),
                "y": int(wp["y"]),
                "warp": int(wp["warp"]),
                "task": wp.get("task", "None"),
            }
            for wp in wps
        ]
        app.config["PENDING_WAYPOINTS"][fleet_id] = stored
        _save_pending_orders(app)
        return jsonify({"fleet_id": fleet_id, "waypoints": stored})

    @app.route("/api/planet/<int:planet_id>/production", methods=["POST"])
    def api_planet_production(planet_id: int):
        """Store pending production queue for a planet (in-memory; not yet serialized to .x1)."""
        body = request.get_json(silent=True)
        if not isinstance(body, list):
            return jsonify({"error": "Body must be a JSON array"}), 400

        for item in body:
            if "name" not in item or "quantity" not in item:
                return jsonify({"error": "Each item needs name and quantity"}), 400

        stored = [
            {
                "name": item["name"],
                "quantity": int(item["quantity"]),
                "count": int(item["quantity"]),
                "complete_percent": 0,
            }
            for item in body
        ]
        app.config["PENDING_PRODUCTION"][planet_id] = stored
        _save_pending_orders(app)
        return jsonify(stored)

    @app.route("/api/research", methods=["POST"])
    def api_research():
        """Store pending research field allocation.

        Accepts JSON body::

            {"field": "weapons", "resources": 50}

        Returns:
            200 with ``{"status": "pending", "field": ..., "resources": ...}``
            422 for invalid field name or non-integer/negative resources.
        """
        body = request.get_json(silent=True) or {}
        field = body.get("field")
        resources = body.get("resources")

        if field not in _RESEARCH_FIELDS:
            return (
                jsonify(
                    {
                        "error": f"Invalid field '{field}'. Must be one of: {sorted(_RESEARCH_FIELDS)}"
                    }
                ),
                422,
            )
        if not isinstance(resources, int) or isinstance(resources, bool) or resources < 0:
            return jsonify({"error": "'resources' must be a non-negative integer"}), 422

        app.config["PENDING_RESEARCH"] = {"field": field, "resources": resources}
        _save_pending_orders(app)
        return jsonify({"status": "pending", "field": field, "resources": resources})

    @app.route("/api/planet/<int:planet_id>")
    def api_planet(planet_id: int):
        """Return full detail for a single planet by ID."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        planet = next((p for p in state.planets if p.planet_id == planet_id), None)
        if planet is None:
            return jsonify({"error": f"Planet {planet_id} not found"}), 404

        pending_prod = app.config["PENDING_PRODUCTION"]
        queue = state.production_queues.get(planet.planet_id, [])
        serialized_queue = [
            {
                "name": qi.item_name,
                "count": qi.count,
                "quantity": qi.count,
                "complete_percent": qi.complete_percent,
            }
            for qi in queue
        ]
        if planet.planet_id in pending_prod:
            serialized_queue = pending_prod[planet.planet_id]

        return jsonify(
            {
                "id": planet.planet_id,
                "name": planet.name,
                "x": planet.x,
                "y": planet.y,
                "owner": planet.owner,
                "population": planet.population,
                "mines": planet.mines,
                "factories": planet.factories,
                "defenses": planet.defenses,
                "ironium": planet.ironium,
                "boranium": planet.boranium,
                "germanium": planet.germanium,
                "ironium_conc": planet.ironium_conc,
                "boranium_conc": planet.boranium_conc,
                "germanium_conc": planet.germanium_conc,
                "gravity": planet.gravity,
                "temperature": planet.temperature,
                "radiation": planet.radiation,
                "has_starbase": planet.has_starbase,
                "is_homeworld": planet.is_homeworld,
                "production_queue": serialized_queue,
            }
        )

    @app.route("/api/fleet/<int:fleet_id>")
    def api_fleet(fleet_id: int):
        """Return full detail for a single fleet by ID."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        fleet = next((f for f in state.fleets if f.fleet_id == fleet_id), None)
        if fleet is None:
            return jsonify({"error": f"Fleet {fleet_id} not found"}), 404

        pending_wp = app.config["PENDING_WAYPOINTS"]
        waypoints = [
            {"x": wp.x, "y": wp.y, "warp": wp.warp, "task": wp.task_name}
            for wp in fleet.waypoints
        ]
        if fleet.fleet_id in pending_wp:
            waypoints = pending_wp[fleet.fleet_id]

        return jsonify(
            {
                "id": fleet.fleet_id,
                "name": fleet.name,
                "owner": fleet.owner,
                "x": fleet.x,
                "y": fleet.y,
                "ship_count": fleet.ship_count,
                "waypoints": waypoints,
            }
        )

    @app.route("/api/players")
    def api_players():
        """Return all player/race records parsed from Type 6 blocks."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(
            [
                {
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
                for p in state.players
            ]
        )

    @app.route("/api/score")
    def api_score():
        """Return per-player score snapshots parsed from Type 45 blocks."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(
            [
                {
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
                for s in state.player_scores
            ]
        )

    @app.route("/api/designs")
    def api_designs():
        """Return all full ship/starbase designs (own player only)."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(
            [
                {
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
                for d in state.designs
                if d.is_full_design
            ]
        )

    @app.route("/api/battles")
    def api_battles():
        """Return all battle records from the current turn (Type 31 blocks)."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(
            [
                {
                    "battle_id": b.battle_id,
                    "x": b.x,
                    "y": b.y,
                    "num_tokens": b.num_tokens,
                    "event_bytes": len(b.events_raw),
                }
                for b in state.battles
            ]
        )

    @app.route("/api/minefields")
    def api_minefields():
        """Return all minefields visible to the current player (from Type 25 blocks)."""
        from stars_web.binary.game_object import Minefield

        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(
            [
                {
                    "x": obj.x,
                    "y": obj.y,
                    "owner": obj.owner,
                    "radius": obj.radius,
                    "quantity": obj.quantity,
                }
                for obj in state.objects
                if isinstance(obj, Minefield)
            ]
        )

    @app.route("/api/messages")
    def api_messages():
        """Return all turn messages from Type 24 blocks."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(
            [{"action_code": m.action_code, "text": m.text} for m in state.messages]
        )

    @app.route("/game/submit-turn", methods=["POST"])
    def api_submit_turn():
        """Write pending orders to .x1 and invoke the Stars! host binary.

        Returns JSON: {"status": "ok"|"error", "log": "...", "turn": N}
        """
        import subprocess

        from stars_web.block_reader import read_blocks
        from stars_web.game_state import WAYPOINT_TASKS
        from stars_web.order_serializer import (
            OBJ_TYPE_DEEP_SPACE,
            ProductionItem,
            ProductionQueueOrder,
            WaypointOrder,
            build_order_file,
        )

        game_dir = app.config["GAME_DIR"]
        pending_wp = app.config["PENDING_WAYPOINTS"]
        pending_prod = app.config["PENDING_PRODUCTION"]

        # ── Detect game prefix + player number ──────────────────────────────
        xy_files = [f for f in os.listdir(game_dir) if f.lower().endswith(".xy")]
        if not xy_files:
            return (
                jsonify(
                    {"status": "error", "log": "No .xy file found in game directory", "turn": None}
                ),
                500,
            )
        game_prefix = xy_files[0].rsplit(".", 1)[0]

        m_files = sorted(
            f
            for f in os.listdir(game_dir)
            if f.lower().startswith(game_prefix.lower() + ".m") and f[-1].isdigit()
        )
        if not m_files:
            return (
                jsonify(
                    {"status": "error", "log": "No .m# file found in game directory", "turn": None}
                ),
                500,
            )
        player_num = int(m_files[0].rsplit(".m", 1)[1])

        # ── Read source .x1 header ───────────────────────────────────────────
        x1_path = os.path.join(game_dir, f"{game_prefix}.x{player_num}")
        if not os.path.exists(x1_path):
            return (
                jsonify(
                    {
                        "status": "error",
                        "log": f"{game_prefix}.x{player_num} not found in game directory",
                        "turn": None,
                    }
                ),
                500,
            )

        with open(x1_path, "rb") as f:
            source_x1 = f.read()

        blocks = read_blocks(source_x1)
        if not blocks or blocks[0].file_header is None:
            return (
                jsonify(
                    {"status": "error", "log": "Could not parse .x1 file header", "turn": None}
                ),
                500,
            )

        header_bytes = blocks[0].data
        turn = blocks[0].file_header.turn

        # ── Task name → int reverse mapping ─────────────────────────────────
        task_name_to_id = {v: k for k, v in WAYPOINT_TASKS.items()}

        # ── Build order objects ──────────────────────────────────────────────
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
            try:
                prod_items = [
                    ProductionItem.from_name(it["name"], int(it["quantity"])) for it in items
                ]
            except ValueError as exc:
                return jsonify({"status": "error", "log": str(exc), "turn": turn}), 400
            production_orders.append(ProductionQueueOrder(planet_id=planet_id, items=prod_items))

        # ── Serialize to .x1 ────────────────────────────────────────────────
        new_x1 = build_order_file(
            header_bytes,
            waypoint_orders=waypoint_orders,
            production_orders=production_orders,
        )
        with open(x1_path, "wb") as f:
            f.write(new_x1)

        # ── Invoke host ──────────────────────────────────────────────────────
        otvdm_path = os.path.join(game_dir, "otvdm", "otvdm.exe")
        stars_path = os.path.join(game_dir, "stars", "stars.exe")

        if not os.path.exists(otvdm_path):
            return (
                jsonify(
                    {
                        "status": "error",
                        "log": f"Host launcher not found: {otvdm_path}",
                        "turn": turn,
                    }
                ),
                500,
            )

        try:
            result = subprocess.run(
                [otvdm_path, stars_path],
                cwd=game_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return (
                jsonify(
                    {"status": "error", "log": "Host process timed out after 60 s", "turn": turn}
                ),
                500,
            )
        except OSError as exc:
            return jsonify({"status": "error", "log": str(exc), "turn": turn}), 500

        log = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            app.config["PENDING_WAYPOINTS"].clear()
            app.config["PENDING_PRODUCTION"].clear()
            app.config["PENDING_RESEARCH"].clear()
            _delete_sidecar(app)
            return jsonify({"status": "ok", "log": log, "turn": turn})

        return (
            jsonify(
                {
                    "status": "error",
                    "log": log or f"Host exited with code {result.returncode}",
                    "turn": turn,
                }
            ),
            500,
        )

    return app
