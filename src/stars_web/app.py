"""Flask web application for Stars! game viewer.

Serves a star map UI that visualizes parsed game state from
Stars! binary save files.
"""

import json
import os

from flask import Flask, jsonify, render_template, request

from stars_web.game_state import load_game


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

    _changelog_path = os.path.join(os.path.dirname(__file__), "changelog.json")

    @app.route("/")
    def index():
        """Serve the star map page."""
        return render_template("star_map.html")

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
                "has_pending_orders": bool(pending_wp) or bool(pending_prod),
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
        return jsonify(stored)

    return app
