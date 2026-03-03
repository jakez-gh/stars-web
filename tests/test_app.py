"""Tests for the Flask web application."""

import os
import shutil
from unittest.mock import MagicMock, patch

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


class TestWaypointOrdersAPI:
    """Tests for POST /api/fleet/<id>/waypoints (issue #35)."""

    def test_route_exists(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert any("waypoints" in r for r in rules)

    def test_post_returns_200(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post(
                "/api/fleet/0/waypoints",
                json={"waypoints": [{"x": 100, "y": 200, "warp": 5, "task": "None"}]},
            )
            assert resp.status_code == 200

    def test_post_returns_stored_waypoints(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            wps = [{"x": 100, "y": 200, "warp": 5, "task": "None"}]
            data = client.post("/api/fleet/0/waypoints", json={"waypoints": wps}).get_json()
            assert "waypoints" in data
            assert data["waypoints"][0]["x"] == 100

    def test_post_rejects_waypoint_missing_y(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/fleet/0/waypoints", json={"waypoints": [{"x": 100}]})
            assert resp.status_code == 400

    def test_post_rejects_missing_waypoints_key(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/fleet/0/waypoints", json={})
            assert resp.status_code == 400

    def test_post_empty_list_clears_pending(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            client.post(
                "/api/fleet/0/waypoints",
                json={"waypoints": [{"x": 1, "y": 2, "warp": 5, "task": "None"}]},
            )
            data = client.post("/api/fleet/0/waypoints", json={"waypoints": []}).get_json()
            assert data["waypoints"] == []

    def test_pending_visible_in_game_state(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            state = client.get("/api/game-state").get_json()
            fleet_id = state["fleets"][0]["id"]
            client.post(
                f"/api/fleet/{fleet_id}/waypoints",
                json={"waypoints": [{"x": 999, "y": 888, "warp": 7, "task": "None"}]},
            )
            state2 = client.get("/api/game-state").get_json()
            fleet = next(f for f in state2["fleets"] if f["id"] == fleet_id)
            assert any(wp["x"] == 999 for wp in fleet["waypoints"])


class TestProductionOrdersAPI:
    """Tests for POST /api/planet/<id>/production (issue #42)."""

    def test_route_exists(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert any("production" in r for r in rules)

    def test_post_returns_200(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post(
                "/api/planet/0/production",
                json=[{"name": "Factory", "quantity": 5}],
            )
            assert resp.status_code == 200

    def test_post_returns_stored_queue(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.post(
                "/api/planet/0/production",
                json=[{"name": "Factory", "quantity": 5}],
            ).get_json()
            assert isinstance(data, list)
            assert data[0]["name"] == "Factory"
            assert data[0]["quantity"] == 5

    def test_post_rejects_item_missing_name(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/planet/0/production", json=[{"quantity": 5}])
            assert resp.status_code == 400

    def test_post_rejects_non_list_body(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/planet/0/production", json={"name": "Factory", "quantity": 5})
            assert resp.status_code == 400

    def test_pending_visible_in_game_state(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            state = client.get("/api/game-state").get_json()
            planet = next(p for p in state["planets"] if p["owner"] >= 0)
            planet_id = planet["id"]
            client.post(
                f"/api/planet/{planet_id}/production",
                json=[{"name": "Mine", "quantity": 99}],
            )
            state2 = client.get("/api/game-state").get_json()
            p2 = next(p for p in state2["planets"] if p["id"] == planet_id)
            assert any(
                qi["name"] == "Mine" and qi.get("quantity", qi.get("count")) == 99
                for qi in p2["production_queue"]
            )

    def test_post_shorter_list_removes_items(self):
        """Posting a subset replaces the full queue, enabling client-side remove."""
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            # Add two items
            client.post(
                "/api/planet/1/production",
                json=[{"name": "Mine", "quantity": 3}, {"name": "Factory", "quantity": 5}],
            )
            # Remove the first by posting only the second
            resp = client.post(
                "/api/planet/1/production",
                json=[{"name": "Factory", "quantity": 5}],
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) == 1
            assert data[0]["name"] == "Factory"

    def test_post_empty_list_clears_queue(self):
        """Posting an empty list replaces the queue with nothing."""
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            client.post(
                "/api/planet/1/production",
                json=[{"name": "Mine", "quantity": 2}],
            )
            resp = client.post("/api/planet/1/production", json=[])
            assert resp.status_code == 200
            assert resp.get_json() == []


class TestSubmitTurnButton:
    """Unit tests for the has_pending_orders flag in /api/game-state (issue #49)."""

    def test_has_pending_orders_false_with_no_pending(self):
        """has_pending_orders is False when no waypoints or production orders exist."""
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            assert data["has_pending_orders"] is False

    def test_has_pending_orders_true_after_waypoint_post(self):
        """has_pending_orders becomes True after a waypoint order is POSTed."""
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            client.post(
                "/api/fleet/1/waypoints",
                json={"waypoints": [{"x": 100, "y": 200, "warp": 5}]},
            )
            data = client.get("/api/game-state").get_json()
            assert data["has_pending_orders"] is True

    def test_has_pending_orders_true_after_production_post(self):
        """has_pending_orders becomes True after a production order is POSTed."""
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            client.post(
                "/api/planet/1/production",
                json=[{"name": "Mine", "quantity": 3}],
            )
            data = client.get("/api/game-state").get_json()
            assert data["has_pending_orders"] is True


# ---------------------------------------------------------------------------
# TestSubmitTurnAPI (issue #50)
# ---------------------------------------------------------------------------


@pytest.fixture()
def game_dir_with_x1(tmp_path):
    """Temp game directory with Game.xy, Game.m1, Game.x1, and otvdm/otvdm.exe."""
    _skip_if_no_data()

    # Copy real game files
    for name in ("Game.xy", "Game.m1"):
        shutil.copy(os.path.join(TEST_DATA_DIR, name), tmp_path / name)

    # Build a minimal .x1 from the .m1 header bytes
    from stars_web.block_reader import read_blocks
    from stars_web.order_serializer import build_order_file

    with open(tmp_path / "Game.m1", "rb") as f:
        m_bytes = f.read()
    m_blocks = read_blocks(m_bytes)
    x1_raw = build_order_file(m_blocks[0].data)
    with open(tmp_path / "Game.x1", "wb") as f:
        f.write(x1_raw)

    # Create dummy otvdm.exe + stars.exe (paths only; subprocess is mocked)
    (tmp_path / "otvdm").mkdir()
    (tmp_path / "otvdm" / "otvdm.exe").write_bytes(b"")
    (tmp_path / "stars").mkdir()
    (tmp_path / "stars" / "stars.exe").write_bytes(b"")

    return str(tmp_path)


class TestSubmitTurnAPI:
    """Tests for POST /game/submit-turn (issue #50)."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/game/submit-turn" in rules

    def test_success_path_returns_ok(self, game_dir_with_x1):
        """Mocked host returns 0: response is status=ok and pending orders are cleared."""
        app = create_app(game_dir=game_dir_with_x1)
        mock_result = MagicMock(returncode=0, stdout="done\n", stderr="")

        with app.test_client() as client:
            # Plant a pending waypoint
            client.post(
                "/api/fleet/1/waypoints",
                json={"waypoints": [{"x": 100, "y": 200, "warp": 5}]},
            )
            assert app.config["PENDING_WAYPOINTS"]

            with patch("subprocess.run", return_value=mock_result):
                resp = client.post("/game/submit-turn")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "turn" in data
        # Pending orders must be cleared after successful submission
        assert not app.config["PENDING_WAYPOINTS"]
        assert not app.config["PENDING_PRODUCTION"]

    def test_failure_path_returns_error(self, game_dir_with_x1):
        """Mocked host returns non-zero: response is status=error, pending NOT cleared."""
        app = create_app(game_dir=game_dir_with_x1)
        mock_result = MagicMock(returncode=1, stdout="", stderr="host error")

        with app.test_client() as client:
            client.post(
                "/api/fleet/1/waypoints",
                json={"waypoints": [{"x": 100, "y": 200, "warp": 5}]},
            )

            with patch("subprocess.run", return_value=mock_result):
                resp = client.post("/game/submit-turn")

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["status"] == "error"
        # Pending orders should be preserved on failure
        assert app.config["PENDING_WAYPOINTS"]

    def test_no_x1_file_returns_error(self, tmp_path):
        """Missing .x1 file → 500 with descriptive error."""
        _skip_if_no_data()
        for name in ("Game.xy", "Game.m1"):
            shutil.copy(os.path.join(TEST_DATA_DIR, name), tmp_path / name)
        # Deliberately do NOT create Game.x1
        app = create_app(game_dir=str(tmp_path))
        with app.test_client() as client:
            resp = client.post("/game/submit-turn")
        assert resp.status_code == 500
        assert resp.get_json()["status"] == "error"

    def test_no_otvdm_returns_error(self, game_dir_with_x1):
        """Missing otvdm.exe → 500 with descriptive error."""
        os.remove(os.path.join(game_dir_with_x1, "otvdm", "otvdm.exe"))
        app = create_app(game_dir=game_dir_with_x1)
        with app.test_client() as client:
            resp = client.post("/game/submit-turn")
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["status"] == "error"
        assert "otvdm" in data["log"].lower() or "not found" in data["log"].lower()

    def test_production_orders_submitted(self, game_dir_with_x1):
        """Production orders are serialized and pending is cleared on success."""
        app = create_app(game_dir=game_dir_with_x1)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        with app.test_client() as client:
            client.post(
                "/api/planet/1/production",
                json=[{"name": "Mine", "quantity": 5}],
            )
            assert app.config["PENDING_PRODUCTION"]

            with patch("subprocess.run", return_value=mock_result):
                resp = client.post("/game/submit-turn")

        assert resp.status_code == 200
        assert not app.config["PENDING_PRODUCTION"]
