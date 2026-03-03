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
