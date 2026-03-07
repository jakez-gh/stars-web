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


class TestPlanetDetailAPI:
    """Tests for GET /api/planet/<id>."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/planet/<int:planet_id>" in rules

    def test_known_planet_returns_200(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            pid = data["planets"][0]["id"]
            resp = client.get(f"/api/planet/{pid}")
            assert resp.status_code == 200

    def test_unknown_planet_returns_404(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.get("/api/planet/99999")
            assert resp.status_code == 404

    def test_planet_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            pid = data["planets"][0]["id"]
            planet = client.get(f"/api/planet/{pid}").get_json()
            for field in ["id", "name", "x", "y", "owner", "production_queue"]:
                assert field in planet, f"Missing field: {field}"

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/planet/0")
            assert resp.status_code == 500

    def test_pending_production_reflected(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            pid = data["planets"][0]["id"]
            client.post(
                f"/api/planet/{pid}/production",
                json=[{"name": "Mine", "quantity": 3}],
            )
            planet = client.get(f"/api/planet/{pid}").get_json()
            assert planet["production_queue"][0]["name"] == "Mine"


class TestFleetDetailAPI:
    """Tests for GET /api/fleet/<id>."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/fleet/<int:fleet_id>" in rules

    def test_known_fleet_returns_200(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            fid = data["fleets"][0]["id"]
            resp = client.get(f"/api/fleet/{fid}")
            assert resp.status_code == 200

    def test_unknown_fleet_returns_404(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.get("/api/fleet/99999")
            assert resp.status_code == 404

    def test_fleet_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            fid = data["fleets"][0]["id"]
            fleet = client.get(f"/api/fleet/{fid}").get_json()
            for field in ["id", "name", "x", "y", "owner", "waypoints", "ship_count"]:
                assert field in fleet, f"Missing field: {field}"

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/fleet/0")
            assert resp.status_code == 500

    def test_pending_waypoints_reflected(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/game-state").get_json()
            fid = data["fleets"][0]["id"]
            client.post(
                f"/api/fleet/{fid}/waypoints",
                json={"waypoints": [{"x": 50, "y": 60, "warp": 6}]},
            )
            fleet = client.get(f"/api/fleet/{fid}").get_json()
            assert fleet["waypoints"][0]["x"] == 50


class TestPlayersAPI:
    """Tests for GET /api/players."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/players" in rules

    def test_returns_list(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/players").get_json()
            assert isinstance(data, list)
            assert len(data) >= 1

    def test_player_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            player = client.get("/api/players").get_json()[0]
            for field in ["player_number", "name", "name_plural", "prt_name"]:
                assert field in player, f"Missing field: {field}"

    def test_full_player_has_tech(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            players = client.get("/api/players").get_json()
            full = [p for p in players if p["has_full_data"]]
            if full:
                assert full[0]["tech"] is not None
                assert "energy" in full[0]["tech"]

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/players")
            assert resp.status_code == 500


class TestScoreAPI:
    """Tests for GET /api/score."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/score" in rules

    def test_returns_list(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/score").get_json()
            assert isinstance(data, list)

    def test_score_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            scores = client.get("/api/score").get_json()
            if scores:
                for field in ["player_id", "total_score", "num_planets"]:
                    assert field in scores[0], f"Missing field: {field}"

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/score")
            assert resp.status_code == 500


class TestDesignsAPI:
    """Tests for GET /api/designs."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/designs" in rules

    def test_returns_list(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/designs").get_json()
            assert isinstance(data, list)

    def test_design_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            designs = client.get("/api/designs").get_json()
            if designs:
                for field in ["id", "name", "hull_name", "is_starbase", "armor"]:
                    assert field in designs[0], f"Missing field: {field}"

    def test_only_full_designs_returned(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            designs = client.get("/api/designs").get_json()
            # All returned designs should have armor field (full designs only)
            for d in designs:
                assert "armor" in d

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/designs")
            assert resp.status_code == 500


class TestBattlesAPI:
    """Tests for GET /api/battles."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/battles" in rules

    def test_returns_list(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/battles").get_json()
            assert isinstance(data, list)

    def test_battle_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            battles = client.get("/api/battles").get_json()
            if battles:
                for field in ["battle_id", "x", "y", "num_tokens"]:
                    assert field in battles[0], f"Missing field: {field}"

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/battles")
            assert resp.status_code == 500


class TestMinefieldsAPI:
    """Tests for GET /api/minefields."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/minefields" in rules

    def test_returns_list(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/minefields").get_json()
            assert isinstance(data, list)

    def test_minefield_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            fields_response = client.get("/api/minefields").get_json()
            if fields_response:
                for field in ["x", "y", "owner", "radius", "quantity"]:
                    assert field in fields_response[0], f"Missing field: {field}"

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/minefields")
            assert resp.status_code == 500


class TestMessagesAPI:
    """Tests for GET /api/messages."""

    def test_route_exists(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/messages" in rules

    def test_returns_list(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.get("/api/messages").get_json()
            assert isinstance(data, list)

    def test_message_has_required_fields(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            messages = client.get("/api/messages").get_json()
            if messages:
                for field in ["action_code", "text"]:
                    assert field in messages[0], f"Missing field: {field}"

    def test_invalid_game_dir_returns_500(self):
        app = create_app(game_dir="/nonexistent/path")
        with app.test_client() as client:
            resp = client.get("/api/messages")
            assert resp.status_code == 500


class TestNewRoutesSmoke:
    """Smoke tests: all new endpoints return non-5xx with valid game data."""

    NEW_ROUTES = [
        "/api/players",
        "/api/score",
        "/api/designs",
        "/api/battles",
        "/api/minefields",
        "/api/messages",
    ]

    def test_no_new_route_returns_5xx(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            for route in self.NEW_ROUTES:
                resp = client.get(route)
                assert resp.status_code < 500, f"{route} returned {resp.status_code}"


class TestResearchOrdersAPI:
    """Tests for POST /api/research (issue #85)."""

    def test_route_exists(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/research" in rules

    def test_valid_post_returns_200(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/research", json={"field": "weapons", "resources": 50})
            assert resp.status_code == 200

    def test_valid_post_returns_pending_body(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            data = client.post(
                "/api/research", json={"field": "weapons", "resources": 50}
            ).get_json()
            assert data["status"] == "pending"
            assert data["field"] == "weapons"
            assert data["resources"] == 50

    def test_invalid_field_returns_422(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/research", json={"field": "magic", "resources": 50})
            assert resp.status_code == 422

    def test_missing_field_returns_422(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/research", json={"resources": 50})
            assert resp.status_code == 422

    def test_negative_resources_returns_422(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post("/api/research", json={"field": "weapons", "resources": -1})
            assert resp.status_code == 422

    def test_string_resources_returns_422(self):
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            resp = client.post(
                "/api/research", json={"field": "weapons", "resources": "fifty"}
            )
            assert resp.status_code == 422

    def test_all_valid_fields_accepted(self):
        valid_fields = [
            "energy",
            "weapons",
            "propulsion",
            "construction",
            "electronics",
            "biotechnology",
        ]
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            for field in valid_fields:
                resp = client.post("/api/research", json={"field": field, "resources": 0})
                assert resp.status_code == 200, f"Field '{field}' should be accepted"

    def test_pending_visible_in_game_state(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            client.post("/api/research", json={"field": "propulsion", "resources": 25})
            state = client.get("/api/game-state").get_json()
            assert state["pending_research"]["field"] == "propulsion"
            assert state["pending_research"]["resources"] == 25

    def test_has_pending_orders_true_with_research(self):
        _skip_if_no_data()
        app = create_app(game_dir=TEST_DATA_DIR)
        with app.test_client() as client:
            client.post("/api/research", json={"field": "energy", "resources": 10})
            state = client.get("/api/game-state").get_json()
            assert state["has_pending_orders"] is True


@pytest.mark.uses_sidecar
class TestSidecarPersistence:
    """Tests for JSON sidecar persistence surviving server restarts (issue #126)."""    

    def test_waypoint_post_writes_sidecar(self, tmp_path):
        app = create_app(game_dir=str(tmp_path))
        with app.test_client() as client:
            client.post(
                "/api/fleet/7/waypoints",
                json={"waypoints": [{"x": 150, "y": 225, "warp": 6, "task": "None"}]},
            )
        import json

        sidecar = tmp_path / ".orders_pending.json"
        assert sidecar.exists()
        data = json.loads(sidecar.read_text())
        assert "7" in data["waypoints"]
        assert data["waypoints"]["7"][0]["x"] == 150

    def test_production_post_writes_sidecar(self, tmp_path):
        app = create_app(game_dir=str(tmp_path))
        with app.test_client() as client:
            client.post(
                "/api/planet/42/production",
                json=[{"name": "Factory", "quantity": 10}],
            )
        import json

        sidecar = tmp_path / ".orders_pending.json"
        assert sidecar.exists()
        data = json.loads(sidecar.read_text())
        assert "42" in data["production"]

    def test_research_post_writes_sidecar(self, tmp_path):
        app = create_app(game_dir=str(tmp_path))
        with app.test_client() as client:
            client.post("/api/research", json={"field": "weapons", "resources": 50})
        import json

        sidecar = tmp_path / ".orders_pending.json"
        assert sidecar.exists()
        data = json.loads(sidecar.read_text())
        assert data["research"]["field"] == "weapons"
        assert data["research"]["resources"] == 50

    def test_sidecar_loaded_on_restart(self, tmp_path):
        """Orders written by first-app instance survive into a second (restart simulation)."""
        import json

        sidecar = tmp_path / ".orders_pending.json"
        sidecar.write_text(
            json.dumps(
                {
                    "waypoints": {
                        "7": [{"x": 150, "y": 225, "warp": 6, "task": "None"}]
                    },
                    "production": {
                        "42": [
                            {
                                "name": "Factory",
                                "quantity": 10,
                                "count": 10,
                                "complete_percent": 0,
                            }
                        ]
                    },
                    "research": {"field": "weapons", "resources": 50},
                }
            )
        )
        app2 = create_app(game_dir=str(tmp_path))
        assert app2.config["PENDING_WAYPOINTS"][7][0]["x"] == 150
        assert app2.config["PENDING_PRODUCTION"][42][0]["name"] == "Factory"
        assert app2.config["PENDING_RESEARCH"]["field"] == "weapons"

    def test_corrupted_sidecar_ignored_on_startup(self, tmp_path):
        """A malformed sidecar does not crash the app; pending dicts start empty."""
        sidecar = tmp_path / ".orders_pending.json"
        sidecar.write_text("{broken json!!")
        app = create_app(game_dir=str(tmp_path))
        assert app.config["PENDING_WAYPOINTS"] == {}
        assert app.config["PENDING_PRODUCTION"] == {}
        assert app.config["PENDING_RESEARCH"] == {}
