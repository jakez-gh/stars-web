"""Flask web application for Stars! game viewer.

Serves a star map UI that visualizes parsed game state from
Stars! binary save files.
"""

import os

from flask import Flask, jsonify, render_template

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
                "..", "..", "..", "..", "autoplay", "tests", "data",
            ),
        )

    app.config["GAME_DIR"] = os.path.abspath(game_dir)

    @app.route("/")
    def index():
        """Serve the star map page."""
        return render_template("star_map.html")

    @app.route("/api/game-state")
    def api_game_state():
        """Return parsed game state as JSON."""
        try:
            state = load_game(app.config["GAME_DIR"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        planets = []
        for p in state.planets:
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
            }
            planets.append(planet_data)

        fleets = []
        for f in state.fleets:
            fleets.append({
                "id": f.fleet_id,
                "owner": f.owner,
                "x": f.x,
                "y": f.y,
                "ship_count": f.ship_count,
            })

        return jsonify({
            "game_id": state.game_id,
            "year": state.year,
            "turn": state.turn,
            "version": state.version,
            "player_index": state.player_index,
            "settings": {
                "game_name": state.settings.game_name,
                "universe_size": state.settings.universe_size_label,
                "density": state.settings.density_label,
                "player_count": state.settings.player_count,
                "planet_count": state.settings.planet_count,
            },
            "planets": planets,
            "fleets": fleets,
        })

    return app
