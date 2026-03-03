"""Tests for the Flask web application."""

import os

import pytest

from stars_web.app import create_app


# Path to test game data — use absolute path resolved from this file's location
TEST_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "autoplay", "tests", "data")
)


def _skip_if_no_data():
    if not os.path.exists(os.path.join(TEST_DATA_DIR, "Game.xy")):
        pytest.skip("Test game data not found")


class TestAppFactory:
    """Test Flask app creation."""

    def test_create_app_returns_flask(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        assert app is not None

    def test_app_has_index_route(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/" in rules

    def test_app_has_api_route(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/game-state" in rules


class TestGameStateAPI:
    """Test the /api/game-state endpoint."""

    def test_returns_json(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.get("/api/game-state")
            assert resp.status_code == 200
            assert resp.content_type.startswith("application/json")

    def test_has_planets(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            assert "planets" in data
            assert len(data["planets"]) == 32

    def test_has_fleets(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            assert "fleets" in data
            assert len(data["fleets"]) > 0

    def test_has_settings(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            settings = data["settings"]
            assert settings["game_name"] == "Shooting Fish in a Barrel"
            assert settings["planet_count"] == 32

    def test_planet_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            planet = data["planets"][0]
            for field in ["id", "name", "x", "y", "owner", "population"]:
                assert field in planet, f"Missing field: {field}"

    def test_blossom_in_planets(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            names = [p["name"] for p in data["planets"]]
            assert "Blossom" in names

    def test_year_is_2401(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            assert data["year"] == 2401

    def test_fleet_has_name_field(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            fleet = data["fleets"][0]
            assert "name" in fleet, "Fleet must have a name field"
            assert fleet["name"]  # non-empty

    def test_fleet_name_includes_number(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            fleet = data["fleets"][0]
            assert "#" in fleet["name"] or fleet["name"][0].isalpha()

    def test_fleet_has_waypoints_field(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            fleet = data["fleets"][0]
            assert "waypoints" in fleet, "Fleet must expose waypoints list"
            assert isinstance(fleet["waypoints"], list)

    def test_planet_has_production_queue_field(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            planet = data["planets"][0]
            assert "production_queue" in planet, "Planet must have a production_queue field"
            assert isinstance(planet["production_queue"], list)

    def test_owned_planet_production_queue_items_have_name_and_count(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            owned = [p for p in data["planets"] if p["owner"] >= 0]
            assert owned, "No owned planets to test queue on"
            for planet in owned:
                for item in planet["production_queue"]:
                    assert "name" in item, f"Queue item missing 'name' on planet {planet['name']}"
                    assert "count" in item, f"Queue item missing 'count' on planet {planet['name']}"

    def test_invalid_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/game-state")
            assert resp.status_code == 500


class TestChangelogAPI:
    """Test the /api/changelog endpoint."""

    def test_returns_200(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.get("/api/changelog")
            assert resp.status_code == 200

    def test_returns_json(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.get("/api/changelog")
            assert resp.content_type.startswith("application/json")

    def test_has_id_field(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/changelog").get_json()
            assert "id" in data
            assert data["id"]  # non-empty

    def test_has_title_field(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/changelog").get_json()
            assert "title" in data
            assert data["title"]  # non-empty

    def test_has_items_list(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/changelog").get_json()
            assert "items" in data
            assert isinstance(data["items"], list)
            assert len(data["items"]) > 0

    def test_returns_200_with_invalid_game_dir(self):
        """Changelog must never 500 — it does not depend on game data."""
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/changelog")
            assert resp.status_code == 200

    def test_has_route(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/changelog" in rules


class TestAllRoutesSmoke:
    """Smoke test: no route should ever return 5xx with valid game data."""

    ROUTES = ["/", "/api/game-state", "/api/changelog"]

    def test_no_route_returns_5xx(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            for route in self.ROUTES:
                resp = client.get(route)
                assert (
                    resp.status_code < 500
                ), f"{route} returned {resp.status_code} — expected no 5xx"


class TestIndexPage:
    """Test the star map HTML page."""

    def test_returns_html(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.get("/")
            assert resp.status_code == 200
            assert b"star-map" in resp.data
            assert b"Stars!" in resp.data
