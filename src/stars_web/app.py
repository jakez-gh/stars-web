"""Flask web application for Stars! game viewer.

Serves a star map UI that visualizes parsed game state from
Stars! binary save files.
"""

import json
import os
import subprocess
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

from stars_web import pending_orders as _po
from stars_web.domain_constants import RESEARCH_FIELDS
from stars_web.game_state import load_game
from stars_web.serializers import (
    serialize_battle,
    serialize_design,
    serialize_design_summary,
    serialize_fleet,
    serialize_message,
    serialize_minefield,
    serialize_planet,
    serialize_player,
    serialize_score,
)
from stars_web.turn_service import (
    build_and_write_orders,
    detect_game_files,
    read_x1_turn,
    run_host,
)


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
    orders = _po.load_pending_orders(app.config["GAME_DIR"])
    app.config["PENDING_WAYPOINTS"] = orders["waypoints"]
    app.config["PENDING_PRODUCTION"] = orders["production"]
    app.config["PENDING_RESEARCH"] = orders["research"]

    _changelog_path = os.path.join(os.path.dirname(__file__), "changelog.json")

    def _get_state():
        """Load game state once per request (cached on Flask g)."""
        if not hasattr(g, "game_state"):
            g.game_state = load_game(app.config["GAME_DIR"])
        return g.game_state

    def _persist():
        """Write current pending orders to sidecar."""
        _po.save_pending_orders(
            app.config["GAME_DIR"],
            app.config["PENDING_WAYPOINTS"],
            app.config["PENDING_PRODUCTION"],
            app.config["PENDING_RESEARCH"],
        )

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
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        pending_wp = app.config["PENDING_WAYPOINTS"]
        pending_prod = app.config["PENDING_PRODUCTION"]
        pending_research = app.config["PENDING_RESEARCH"]

        return jsonify(
            {
                "game_id": state.game_id,
                "year": state.year,
                "turn": state.turn,
                "version": state.version,
                "player_index": state.player_index,
                "has_pending_orders": bool(pending_wp)
                or bool(pending_prod)
                or bool(pending_research),
                "settings": {
                    "game_name": state.settings.game_name,
                    "universe_size": state.settings.universe_size_label,
                    "density": state.settings.density_label,
                    "player_count": state.settings.player_count,
                    "planet_count": state.settings.planet_count,
                },
                "planets": [
                    serialize_planet(p, state.production_queues, pending_prod)
                    for p in state.planets
                ],
                "fleets": [serialize_fleet(f, pending_wp) for f in state.fleets],
                "designs": [serialize_design_summary(d) for d in state.designs if d.is_full_design],
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
        _persist()
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
        _persist()
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

        if field not in RESEARCH_FIELDS:
            return (
                jsonify(
                    {"error": f"Invalid field '{field}'. Must be one of: {sorted(RESEARCH_FIELDS)}"}
                ),
                422,
            )
        if not isinstance(resources, int) or isinstance(resources, bool) or resources < 0:
            return jsonify({"error": "'resources' must be a non-negative integer"}), 422

        app.config["PENDING_RESEARCH"] = {"field": field, "resources": resources}
        _persist()
        return jsonify({"status": "pending", "field": field, "resources": resources})

    @app.route("/api/planet/<int:planet_id>")
    def api_planet(planet_id: int):
        """Return full detail for a single planet by ID."""
        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        planet = next((p for p in state.planets if p.planet_id == planet_id), None)
        if planet is None:
            return jsonify({"error": f"Planet {planet_id} not found"}), 404

        return jsonify(
            serialize_planet(planet, state.production_queues, app.config["PENDING_PRODUCTION"])
        )

    @app.route("/api/fleet/<int:fleet_id>")
    def api_fleet(fleet_id: int):
        """Return full detail for a single fleet by ID."""
        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        fleet = next((f for f in state.fleets if f.fleet_id == fleet_id), None)
        if fleet is None:
            return jsonify({"error": f"Fleet {fleet_id} not found"}), 404

        return jsonify(serialize_fleet(fleet, app.config["PENDING_WAYPOINTS"]))

    @app.route("/api/players")
    def api_players():
        """Return all player/race records parsed from Type 6 blocks."""
        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify([serialize_player(p) for p in state.players])

    @app.route("/api/score")
    def api_score():
        """Return per-player score snapshots parsed from Type 45 blocks."""
        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify([serialize_score(s) for s in state.player_scores])

    @app.route("/api/designs")
    def api_designs():
        """Return all full ship/starbase designs (own player only)."""
        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify([serialize_design(d) for d in state.designs if d.is_full_design])

    @app.route("/api/battles")
    def api_battles():
        """Return all battle records from the current turn (Type 31 blocks)."""
        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify([serialize_battle(b) for b in state.battles])

    @app.route("/api/minefields")
    def api_minefields():
        """Return all minefields visible to the current player (from Type 25 blocks)."""
        from stars_web.binary.game_object import Minefield

        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(
            [serialize_minefield(obj) for obj in state.objects if isinstance(obj, Minefield)]
        )

    @app.route("/api/messages")
    def api_messages():
        """Return all turn messages from Type 24 blocks."""
        try:
            state = _get_state()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify([serialize_message(m) for m in state.messages])

    @app.route("/game/submit-turn", methods=["POST"])
    def api_submit_turn():
        """Write pending orders to .x1 and invoke the Stars! host binary.

        Returns JSON: {"status": "ok"|"error", "log": "...", "turn": N}
        """
        game_dir = app.config["GAME_DIR"]
        pending_wp = app.config["PENDING_WAYPOINTS"]
        pending_prod = app.config["PENDING_PRODUCTION"]

        try:
            prefix, player_num = detect_game_files(game_dir)
        except ValueError as exc:
            return jsonify({"status": "error", "log": str(exc), "turn": None}), 500

        try:
            header_bytes, turn = read_x1_turn(game_dir, prefix, player_num)
        except ValueError as exc:
            return jsonify({"status": "error", "log": str(exc), "turn": None}), 500

        try:
            build_and_write_orders(
                game_dir, prefix, player_num, header_bytes, pending_wp, pending_prod
            )
        except ValueError as exc:
            return jsonify({"status": "error", "log": str(exc), "turn": turn}), 400

        try:
            result = run_host(game_dir)
        except ValueError as exc:
            return jsonify({"status": "error", "log": str(exc), "turn": turn}), 500
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
            _po.delete_sidecar(game_dir)
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
