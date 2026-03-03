"""End-to-end browser tests for the Stars! web UI.

TDD spec — these tests document required UI behaviour.
They are marked ``e2e`` and excluded from the default pytest run.

Pre-requisites to run:
    pip install pytest-playwright
    playwright install chromium

Run:
    pytest -m e2e

The dev server must be running on http://127.0.0.1:5000 before running
these tests (start it with start.ps1 or start.bat).
"""

import pytest

pytestmark = pytest.mark.e2e

# Bail out with a clear message when playwright is not installed instead of
# a confusing ImportError.
playwright = pytest.importorskip(
    "playwright",
    reason=(
        "playwright not installed — run: "
        "pip install pytest-playwright && playwright install chromium"
    ),
)

BASE_URL = "http://127.0.0.1:5000"


# ---------------------------------------------------------------------------
# Page-load smoke tests
# ---------------------------------------------------------------------------
class TestPageLoads:
    """Basic health checks — no route should blow up."""

    def test_index_returns_200(self, page):
        resp = page.goto(BASE_URL)
        assert resp.status == 200

    def test_title_contains_stars(self, page):
        page.goto(BASE_URL)
        assert "Stars!" in page.title()

    def test_no_server_error_on_page(self, page):
        page.goto(BASE_URL)
        content = page.content()
        assert "Internal Server Error" not in content
        assert "500" not in page.title()

    def test_canvas_exists(self, page):
        page.goto(BASE_URL)
        assert page.query_selector("#star-map") is not None

    def test_game_title_populated_after_fetch(self, page):
        """#game-title should be updated from /api/game-state (not stay 'Stars!')."""
        page.goto(BASE_URL)
        page.wait_for_function(
            "document.getElementById('game-title').textContent !== 'Stars!'",
            timeout=5000,
        )
        title = page.text_content("#game-title")
        assert title and title != "Stars!"

    def test_game_info_shows_year(self, page):
        """#game-info should show 'Year NNNN' after the API fetch."""
        page.goto(BASE_URL)
        page.wait_for_function(
            "document.getElementById('game-info').textContent.includes('Year')",
            timeout=5000,
        )
        info = page.text_content("#game-info")
        assert "Year" in info


# ---------------------------------------------------------------------------
# Changelog modal
# ---------------------------------------------------------------------------
class TestChangelogModal:
    """Modal must appear on first load and be dismissible."""

    def _clear_seen_id(self, page):
        page.evaluate("localStorage.removeItem('seen_changelog_id')")

    def test_modal_appears_on_fresh_load(self, page):
        """With no stored id, modal must be visible within the poll window."""
        page.goto(BASE_URL)
        self._clear_seen_id(page)
        page.reload()
        page.wait_for_selector("#changelog-modal:not(.hidden)", timeout=7000)
        assert page.is_visible("#changelog-modal")

    def test_modal_has_non_empty_title(self, page):
        page.goto(BASE_URL)
        self._clear_seen_id(page)
        page.reload()
        page.wait_for_selector("#changelog-modal:not(.hidden)", timeout=7000)
        title = page.text_content("#changelog-title")
        assert title and len(title.strip()) > 0

    def test_modal_has_at_least_one_item(self, page):
        page.goto(BASE_URL)
        self._clear_seen_id(page)
        page.reload()
        page.wait_for_selector("#changelog-modal:not(.hidden)", timeout=7000)
        items = page.query_selector_all("#changelog-list li")
        assert len(items) > 0

    def test_dismiss_hides_modal(self, page):
        page.goto(BASE_URL)
        self._clear_seen_id(page)
        page.reload()
        page.wait_for_selector("#changelog-modal:not(.hidden)", timeout=7000)
        page.click("#changelog-dismiss")
        page.wait_for_selector("#changelog-modal.hidden", timeout=3000)
        assert not page.is_visible("#changelog-modal")

    def test_dismiss_persists_across_reload(self, page):
        """After dismissing once, a reload must NOT re-show the modal."""
        page.goto(BASE_URL)
        self._clear_seen_id(page)
        page.reload()
        page.wait_for_selector("#changelog-modal:not(.hidden)", timeout=7000)
        page.click("#changelog-dismiss")
        page.reload()
        page.wait_for_timeout(2000)
        assert not page.is_visible("#changelog-modal")

    def test_modal_not_shown_when_id_already_seen(self, page):
        """Pre-seeding localStorage with the current id must suppress the modal."""

        page.goto(BASE_URL)
        # Read current id from the API, then pre-seed it
        resp = page.request.get(f"{BASE_URL}/api/changelog")
        data = resp.json()
        page.evaluate(f"localStorage.setItem('seen_changelog_id', '{data['id']}')")
        page.reload()
        page.wait_for_timeout(2000)
        assert not page.is_visible("#changelog-modal")


# ---------------------------------------------------------------------------
# Waypoint add form
# ---------------------------------------------------------------------------
class TestWaypointForm:
    """Fleet detail panel must include an Add Waypoint form (issue #34).

    These tests require a fleet visible in the game; they interact with the
    canvas directly via pixel coordinates derived from the API.
    """

    def _get_fleet_screen_pos(self, page):
        """Return pixel coords of the first fleet on screen after the game loads."""
        page.wait_for_function(
            "window._gameState && window._gameState.fleets.length > 0",
            timeout=5000,
        )
        return page.evaluate(
            """() => {
            const gs = window._gameState;
            const canvas = document.getElementById('star-map');
            const fleet = gs.fleets[0];
            const viewX = window._viewX ?? 0;
            const viewY = window._viewY ?? 0;
            const zoom  = window._zoom ?? 1;
            const sx = (fleet.x - viewX) * zoom + canvas.width  / 2;
            const sy = (fleet.y - viewY) * zoom + canvas.height / 2;
            return { x: sx, y: sy };
        }"""
        )

    def test_fleet_panel_has_add_waypoint_section(self, page):
        """Clicking a fleet must reveal an 'Add Waypoint' section in the panel."""
        page.goto(BASE_URL)
        pos = self._get_fleet_screen_pos(page)
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#detail-panel:not(.hidden)", timeout=3000)
        assert page.query_selector("#wp-dest") is not None, "#wp-dest select missing"

    def test_waypoint_form_has_warp_selector(self, page):
        """Warp speed selector must be present in the add-waypoint form."""
        page.goto(BASE_URL)
        pos = self._get_fleet_screen_pos(page)
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#detail-panel:not(.hidden)", timeout=3000)
        assert page.query_selector("#wp-warp") is not None, "#wp-warp select missing"

    def test_waypoint_form_has_add_button(self, page):
        """'Add Waypoint' button must be present and labelled."""
        page.goto(BASE_URL)
        pos = self._get_fleet_screen_pos(page)
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#detail-panel:not(.hidden)", timeout=3000)
        btn = page.query_selector("#wp-add-btn")
        assert btn is not None, "#wp-add-btn button missing"

    def test_planet_dropdown_populated(self, page):
        """Planet dropdown must have at least one <option> beyond the default."""
        page.goto(BASE_URL)
        pos = self._get_fleet_screen_pos(page)
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#detail-panel:not(.hidden)", timeout=3000)
        count = page.evaluate("() => document.getElementById('wp-dest').options.length")
        assert count > 1, f"Expected >1 options in #wp-dest, got {count}"


# ---------------------------------------------------------------------------
# Waypoint add flow (issue #37)
# ---------------------------------------------------------------------------
class TestWaypointAdd:
    """Submitting the Add Waypoint form posts to the API and updates the panel."""

    def _get_fleet_screen_pos(self, page):
        page.wait_for_function(
            "window._gameState && window._gameState.fleets.length > 0",
            timeout=5000,
        )
        return page.evaluate(
            """() => {
            const gs = window._gameState;
            const canvas = document.getElementById('star-map');
            const fleet = gs.fleets[0];
            const viewX = window._viewX ?? 0;
            const viewY = window._viewY ?? 0;
            const zoom  = window._zoom ?? 1;
            const sx = (fleet.x - viewX) * zoom + canvas.width  / 2;
            const sy = (fleet.y - viewY) * zoom + canvas.height / 2;
            return { x: sx, y: sy };
        }"""
        )

    def _open_fleet_panel(self, page):
        page.goto(BASE_URL)
        pos = self._get_fleet_screen_pos(page)
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#detail-panel:not(.hidden)", timeout=3000)
        # choose the first real planet from the dropdown
        page.select_option("#wp-dest", index=1)
        page.wait_for_function(
            "document.getElementById('wp-x').value !== ''",
            timeout=2000,
        )

    def test_add_waypoint_shows_toast(self, page):
        """Clicking Add Waypoint must show a 'Waypoint added' toast."""
        self._open_fleet_panel(page)
        page.click("#wp-add-btn")
        page.wait_for_selector("#toast.visible", timeout=5000)
        assert page.text_content("#toast") == "Waypoint added"

    def test_add_waypoint_updates_waypoints(self, page):
        """After the API call succeeds, fleet.waypoints must grow by one."""
        page.goto(BASE_URL)
        pos = self._get_fleet_screen_pos(page)
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#detail-panel:not(.hidden)", timeout=3000)

        initial = page.evaluate("() => (window._gameState.fleets[0].waypoints || []).length")

        page.select_option("#wp-dest", index=1)
        page.wait_for_function(
            "document.getElementById('wp-x').value !== ''",
            timeout=2000,
        )
        page.click("#wp-add-btn")
        page.wait_for_function(
            f"(window._gameState.fleets[0].waypoints || []).length > {initial}",
            timeout=5000,
        )
        final = page.evaluate("() => (window._gameState.fleets[0].waypoints || []).length")
        assert final == initial + 1


# ---------------------------------------------------------------------------
# Planet production queue add flow (issue #44)
# ---------------------------------------------------------------------------
class TestProductionQueueAdd:
    """Add to Queue form on the planet panel posts to the API and updates the queue."""

    def _get_owned_planet_pos(self, page):
        page.wait_for_function(
            "window._gameState && window._gameState.planets.some(p => p.owner >= 0)",
            timeout=5000,
        )
        return page.evaluate(
            """() => {
            const gs = window._gameState;
            const canvas = document.getElementById('star-map');
            const planet = gs.planets.find(p => p.owner >= 0);
            const viewX = window._viewX ?? 0;
            const viewY = window._viewY ?? 0;
            const zoom  = window._zoom ?? 1;
            const sx = (planet.x - viewX) * zoom + canvas.width  / 2;
            const sy = (planet.y - viewY) * zoom + canvas.height / 2;
            return { x: sx, y: sy };
        }"""
        )

    def _open_planet_panel(self, page):
        page.goto(BASE_URL)
        pos = self._get_owned_planet_pos(page)
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#detail-panel:not(.hidden)", timeout=3000)

    def test_owned_planet_has_add_to_queue_form(self, page):
        """Clicking an owned planet must reveal the Add to Queue form."""
        self._open_planet_panel(page)
        assert page.query_selector("#q-item") is not None, "#q-item select missing"
        assert page.query_selector("#q-add-btn") is not None, "#q-add-btn missing"

    def test_add_to_queue_shows_toast(self, page):
        """Clicking Add in the queue form must show an 'Added to queue' toast."""
        self._open_planet_panel(page)
        page.wait_for_selector("#q-add-btn", timeout=3000)
        page.fill("#q-count", "3")
        page.click("#q-add-btn")
        page.wait_for_selector("#toast.visible", timeout=5000)
        assert page.text_content("#toast") == "Added to queue"

    def test_add_to_queue_updates_planet(self, page):
        """After the API call, the planet's production_queue must grow by one."""
        page.goto(BASE_URL)
        pos = self._get_owned_planet_pos(page)

        planet_id = page.evaluate("() => window._gameState.planets.find(p => p.owner >= 0).id")

        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector("#q-add-btn", timeout=3000)

        initial = page.evaluate(
            f"() => (window._gameState.planets.find(p => p.id === {planet_id}).production_queue || []).length"
        )

        page.fill("#q-count", "2")
        page.click("#q-add-btn")
        page.wait_for_function(
            f"(window._gameState.planets.find(p => p.id === {planet_id}).production_queue || []).length > {initial}",
            timeout=5000,
        )
        final = page.evaluate(
            f"() => (window._gameState.planets.find(p => p.id === {planet_id}).production_queue || []).length"
        )
        assert final == initial + 1

    def test_remove_from_queue_shows_toast(self, page):
        """Clicking × on a queue row removes it and shows 'Removed from queue' toast."""
        page.goto(BASE_URL)
        pos = self._get_owned_planet_pos(page)

        planet_id = page.evaluate("() => window._gameState.planets.find(p => p.owner >= 0).id")

        # First add an item so the queue has at least one row with a remove button.
        page.evaluate(
            f"""async () => {{
                await fetch('/api/planet/{planet_id}/production', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify([{{name: 'Mine', quantity: 1}}]),
                }});
            }}"""
        )

        # Open the planet panel (re-click to pick up the seeded queue).
        page.click("#star-map", position={"x": pos["x"], "y": pos["y"]})
        page.wait_for_selector(".q-rm-btn", timeout=3000)
        page.click(".q-rm-btn")
        page.wait_for_selector("#toast.visible", timeout=5000)
        assert page.text_content("#toast") == "Removed from queue"
