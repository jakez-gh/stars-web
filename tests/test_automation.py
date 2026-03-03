"""Tests for the automation package: launcher, window, screen, input.

Most tests here are unit/static tests that do not require a running game.
Live tests (marked with ``@pytest.mark.live``) require Stars! to be running
and are skipped automatically when the game is not running.

Tests that require the real ``otvdm.exe`` + ``stars.exe`` binaries are
skipped when those files are absent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_GAME_DIR = Path(__file__).parent.parent.parent / "starswine4"
_OTVDM = _GAME_DIR / "otvdm" / "otvdm.exe"
_STARS = _GAME_DIR / "stars" / "stars.exe"

_SKIP_NO_GAME = pytest.mark.skipif(
    not (_OTVDM.exists() and _STARS.exists()),
    reason="otvdm.exe / stars.exe not present",
)

_SKIP_NO_WINDOW = pytest.mark.skipif(
    True,  # always skip live tests in CI — set to False to run locally
    reason="live Stars! window required",
)


# ===========================================================================
# Launcher
# ===========================================================================


class TestLauncherPaths:
    """Launcher path properties resolve correctly regardless of OS state."""

    def test_otvdm_path(self) -> None:
        from stars_web.automation.launcher import Launcher

        launcher = Launcher(_GAME_DIR)
        assert launcher.otvdm_exe == _GAME_DIR / "otvdm" / "otvdm.exe"

    def test_stars_path(self) -> None:
        from stars_web.automation.launcher import Launcher

        launcher = Launcher(_GAME_DIR)
        assert launcher.stars_exe == _GAME_DIR / "stars" / "stars.exe"

    def test_otvdm_path_string_input(self) -> None:
        from stars_web.automation.launcher import Launcher

        launcher = Launcher(str(_GAME_DIR))
        assert isinstance(launcher.otvdm_exe, Path)

    def test_missing_otvdm_raises(self, tmp_path: Path) -> None:
        from stars_web.automation.launcher import Launcher

        launcher = Launcher(tmp_path)
        with pytest.raises(FileNotFoundError, match="otvdm.exe"):
            launcher.start(timeout=1)

    def test_missing_stars_raises(self, tmp_path: Path) -> None:
        from stars_web.automation.launcher import Launcher

        # Create otvdm.exe but not stars.exe
        otvdm_dir = tmp_path / "otvdm"
        otvdm_dir.mkdir()
        (otvdm_dir / "otvdm.exe").write_bytes(b"")

        launcher = Launcher(tmp_path)
        with pytest.raises(FileNotFoundError, match="stars.exe"):
            launcher.start(timeout=1)

    def test_start_timeout_raises(self, tmp_path: Path) -> None:
        """If the window never appears, TimeoutError is raised."""
        from stars_web.automation.launcher import Launcher

        # Create both stub executables
        otvdm_dir = tmp_path / "otvdm"
        otvdm_dir.mkdir()
        stars_dir = tmp_path / "stars"
        stars_dir.mkdir()

        fake_otvdm = otvdm_dir / "otvdm.exe"
        fake_stars = stars_dir / "stars.exe"

        if sys.platform == "win32":
            # Write a tiny Windows batch script that immediately exits
            bat = tmp_path / "noop.bat"
            bat.write_text("@exit 0\n")
            fake_otvdm.write_bytes(b"")  # placeholder
            fake_stars.write_bytes(b"")  # placeholder

            launcher = Launcher(tmp_path)
            # Patch Popen and _find_stars_hwnd so the process "runs"
            # but no window ever appears (timeout must fire).
            with (
                mock.patch("subprocess.Popen") as mock_popen,
                mock.patch(
                    "stars_web.automation.launcher._find_stars_hwnd",
                    return_value=None,
                ),
            ):
                mock_proc = mock.MagicMock()
                mock_popen.return_value = mock_proc
                with pytest.raises(TimeoutError):
                    launcher.start(timeout=0.3)
        else:
            pytest.skip("Windows only")


class TestFindStarsHwnd:
    """_find_stars_hwnd returns None when no matching window exists."""

    def test_returns_none_when_no_window(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.launcher import _find_stars_hwnd

        # When Stars! is not running this should return None
        # (it may return a hwnd if game happens to be open — that's fine too)
        result = _find_stars_hwnd()
        assert result is None or isinstance(result, int)


# ===========================================================================
# Window
# ===========================================================================


class TestStarsWindowNotFound:
    """StarsWindow.find() raises RuntimeError when the game is not running."""

    def test_find_raises_when_not_running(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.window import StarsWindow

        with mock.patch("stars_web.automation.window._find_stars_hwnd", return_value=None):
            with pytest.raises(RuntimeError, match="Stars! window not found"):
                StarsWindow.find()


class TestStarsWindowMocked:
    """StarsWindow methods call the expected Win32 APIs."""

    def _make_window(self):
        from stars_web.automation.window import StarsWindow

        return StarsWindow(hwnd=12345)

    def test_window_rect_calls_getwindowrect(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        win = self._make_window()

        import ctypes.wintypes

        def fake_get_window_rect(hwnd, rect_ptr):
            rect = ctypes.cast(rect_ptr, ctypes.POINTER(ctypes.wintypes.RECT)).contents
            rect.left = 10
            rect.top = 20
            rect.right = 810
            rect.bottom = 620
            return 1

        with mock.patch(
            "stars_web.automation.window._user32.GetWindowRect",
            side_effect=fake_get_window_rect,
        ):
            result = win.window_rect()

        assert result == (10, 20, 810, 620)

    def test_client_size_is_positive(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        win = self._make_window()

        import ctypes.wintypes

        def fake_get_client_rect(hwnd, rect_ptr):
            rect = ctypes.cast(rect_ptr, ctypes.POINTER(ctypes.wintypes.RECT)).contents
            rect.left = 0
            rect.top = 0
            rect.right = 640
            rect.bottom = 480
            return 1

        def fake_client_to_screen(hwnd, pt_ptr):
            pt = ctypes.cast(pt_ptr, ctypes.POINTER(ctypes.wintypes.POINT)).contents
            pt.x += 50
            pt.y += 30
            return 1

        with (
            mock.patch(
                "stars_web.automation.window._user32.GetClientRect",
                side_effect=fake_get_client_rect,
            ),
            mock.patch(
                "stars_web.automation.window._user32.ClientToScreen",
                side_effect=fake_client_to_screen,
            ),
        ):
            w, h = win.client_size()

        assert w == 640
        assert h == 480


# ===========================================================================
# Screen
# ===========================================================================


class TestScreenMocked:
    """Screen.capture() calls ImageGrab.grab with the correct bbox."""

    def test_capture_uses_client_rect(self) -> None:
        from stars_web.automation.screen import Screen
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=99)

        bbox = (0, 0, 640, 480)

        with (
            mock.patch.object(win, "client_rect_screen", return_value=bbox),
            mock.patch("stars_web.automation.screen.ImageGrab.grab") as mock_grab,
        ):
            Screen.capture(win)

        mock_grab.assert_called_once_with(bbox=bbox, all_screens=True)

    def test_save_returns_path(self, tmp_path: Path) -> None:
        from PIL import Image

        from stars_web.automation.screen import Screen
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=99)
        fake_img = Image.new("RGB", (640, 480), color=(0, 128, 255))

        with mock.patch.object(Screen, "capture", return_value=fake_img):
            out = Screen.save(win, tmp_path / "test.png")

        assert out.exists()
        assert out.suffix == ".png"

    def test_save_auto_name(self, tmp_path: Path) -> None:
        from PIL import Image

        from stars_web.automation.screen import Screen
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=99)
        fake_img = Image.new("RGB", (640, 480))

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with mock.patch.object(Screen, "capture", return_value=fake_img):
                out = Screen.save(win)  # no path → auto-generated
        finally:
            os.chdir(old_cwd)

        assert out.name.startswith("screenshot_")
        assert out.suffix == ".png"

    def test_is_blank_true_for_solid_image(self) -> None:
        from PIL import Image

        from stars_web.automation.screen import Screen
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=99)
        blank = Image.new("RGB", (640, 480), color=(0, 0, 0))

        with mock.patch.object(Screen, "capture", return_value=blank):
            assert Screen.is_blank(win) is True

    def test_is_blank_false_for_varied_image(self) -> None:
        from PIL import Image

        from stars_web.automation.screen import Screen
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=99)
        varied = Image.new("RGB", (640, 480))
        varied.putpixel((0, 0), (255, 0, 0))
        varied.putpixel((1, 0), (0, 255, 0))

        with mock.patch.object(Screen, "capture", return_value=varied):
            assert Screen.is_blank(win) is False


# ===========================================================================
# Input
# ===========================================================================


class TestInputConstants:
    """Virtual-key constants have the expected Win32 values."""

    def test_vk_f1(self) -> None:
        from stars_web.automation.input import Input

        assert Input.VK_F1 == 0x70

    def test_vk_f10(self) -> None:
        from stars_web.automation.input import Input

        assert Input.VK_F10 == 0x79

    def test_vk_escape(self) -> None:
        from stars_web.automation.input import Input

        assert Input.VK_ESCAPE == 0x1B

    def test_vk_return(self) -> None:
        from stars_web.automation.input import Input

        assert Input.VK_RETURN == 0x0D

    def test_f_keys_sequential(self) -> None:
        from stars_web.automation.input import Input

        f_keys = [
            Input.VK_F1,
            Input.VK_F2,
            Input.VK_F3,
            Input.VK_F4,
            Input.VK_F5,
            Input.VK_F6,
            Input.VK_F7,
            Input.VK_F8,
            Input.VK_F9,
            Input.VK_F10,
        ]
        for i in range(len(f_keys) - 1):
            assert f_keys[i + 1] == f_keys[i] + 1


class TestInputSendInputMocked:
    """Input methods call _send with INPUT structures of the correct type."""

    def test_key_calls_send_input(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation import input as inp_mod

        sent: list = []

        with (
            mock.patch.object(inp_mod, "_send", side_effect=lambda *a: sent.extend(a)),
            mock.patch("time.sleep"),
        ):
            inp_mod.Input.key(inp_mod.Input.VK_F1)

        # One key-down and one key-up were sent (two separate _send calls)
        assert len(sent) == 2
        # Both are keyboard INPUT structures
        for item in sent:
            assert item.type == inp_mod._INPUT_KEYBOARD

    def test_key_combo_presses_both_keys(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation import input as inp_mod

        sent: list = []

        with (
            mock.patch.object(inp_mod, "_send", side_effect=lambda *a: sent.extend(a)),
            mock.patch("time.sleep"),
        ):
            inp_mod.Input.key_combo(inp_mod.Input.VK_MENU, inp_mod.Input.VK_F4)

        # Two key-down calls and two key-up calls = 4 _INPUT structs
        assert len(sent) == 4

    def test_click_calls_send_input(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation import input as inp_mod

        sent: list = []

        with (
            mock.patch.object(inp_mod, "_send", side_effect=lambda *a: sent.extend(a)),
            mock.patch("time.sleep"),
            mock.patch.object(
                inp_mod._user32, "GetSystemMetrics", side_effect=lambda m: 1920 if m == 0 else 1080
            ),
        ):
            inp_mod.Input.click(960, 540)

        # move + left-down + left-up = 3 _INPUT structs
        assert len(sent) == 3
        assert all(s.type == inp_mod._INPUT_MOUSE for s in sent)


# ===========================================================================
# Navigator
# ===========================================================================


class TestNavigatorHotkeys:
    """Navigator maps StarScreen values to the correct VK codes."""

    def test_all_screens_have_hotkeys(self) -> None:
        from stars_web.automation.navigator import StarScreen, _SCREEN_HOTKEYS

        for screen in StarScreen:
            assert screen in _SCREEN_HOTKEYS, f"{screen} has no hotkey registered"

    def test_planets_is_f1(self) -> None:
        from stars_web.automation.input import Input
        from stars_web.automation.navigator import StarScreen, _SCREEN_HOTKEYS

        assert _SCREEN_HOTKEYS[StarScreen.PLANETS] == Input.VK_F1

    def test_fleets_is_f2(self) -> None:
        from stars_web.automation.input import Input
        from stars_web.automation.navigator import StarScreen, _SCREEN_HOTKEYS

        assert _SCREEN_HOTKEYS[StarScreen.FLEETS] == Input.VK_F2

    def test_scanner_is_f3(self) -> None:
        from stars_web.automation.input import Input
        from stars_web.automation.navigator import StarScreen, _SCREEN_HOTKEYS

        assert _SCREEN_HOTKEYS[StarScreen.SCANNER] == Input.VK_F3

    def test_race_is_f10(self) -> None:
        from stars_web.automation.input import Input
        from stars_web.automation.navigator import StarScreen, _SCREEN_HOTKEYS

        assert _SCREEN_HOTKEYS[StarScreen.RACE] == Input.VK_F10


class TestNavigatorGo:
    """Navigator.go() calls Input.key with the right vk and invokes verify_fn."""

    def _make_nav(self, verify_fn=None):
        from stars_web.automation.navigator import Navigator
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        return Navigator(win, settle_delay=0, verify_fn=verify_fn)

    def test_go_calls_focus_and_key(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.input import Input
        from stars_web.automation.navigator import StarScreen

        nav = self._make_nav()
        with (
            mock.patch.object(nav.win, "focus") as mock_focus,
            mock.patch.object(Input, "key") as mock_key,
            mock.patch("time.sleep"),
        ):
            nav.go(StarScreen.PLANETS)

        mock_focus.assert_called_once()
        mock_key.assert_called_once_with(Input.VK_F1)

    def test_go_raises_on_verification_failure(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.input import Input
        from stars_web.automation.navigator import StarScreen

        nav = self._make_nav(verify_fn=lambda win, screen: False)
        with (
            mock.patch.object(nav.win, "focus"),
            mock.patch.object(Input, "key"),
            mock.patch("time.sleep"),
            pytest.raises(RuntimeError, match="verification failed"),
        ):
            nav.go(StarScreen.SCANNER)

    def test_go_succeeds_when_verify_returns_true(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.input import Input
        from stars_web.automation.navigator import StarScreen

        nav = self._make_nav(verify_fn=lambda win, screen: True)
        with (
            mock.patch.object(nav.win, "focus"),
            mock.patch.object(Input, "key"),
            mock.patch("time.sleep"),
        ):
            nav.go(StarScreen.FLEETS)  # should not raise


# ===========================================================================
# Matcher
# ===========================================================================


class TestMatcherPixelHelpers:
    """Matcher pixel helpers work on synthetic images."""

    def _solid(self, color: tuple, size: tuple = (100, 100)):
        from PIL import Image

        img = Image.new("RGB", size, color=color)
        return img

    def test_pixel_at(self) -> None:
        from stars_web.automation.matcher import Matcher

        img = self._solid((255, 0, 128))
        assert Matcher.pixel_at(img, 0, 0) == (255, 0, 128)

    def test_pixel_matches_exact(self) -> None:
        from stars_web.automation.matcher import Matcher

        img = self._solid((10, 20, 30))
        assert Matcher.pixel_matches(img, 0, 0, (10, 20, 30), tolerance=0)

    def test_pixel_matches_within_tolerance(self) -> None:
        from stars_web.automation.matcher import Matcher

        img = self._solid((10, 20, 30))
        assert Matcher.pixel_matches(img, 0, 0, (15, 25, 35), tolerance=5)

    def test_pixel_not_matches_outside_tolerance(self) -> None:
        from stars_web.automation.matcher import Matcher

        img = self._solid((0, 0, 0))
        assert not Matcher.pixel_matches(img, 0, 0, (50, 50, 50), tolerance=10)

    def test_list_templates_returns_list(self) -> None:
        from stars_web.automation.matcher import Matcher

        result = Matcher.list_templates()
        assert isinstance(result, list)


class TestMatcherFind:
    """Matcher.find() returns a MatchResult for a perfect-match template."""

    def test_find_exact_match(self) -> None:
        from PIL import Image

        from stars_web.automation.matcher import Matcher

        # Create a 60×60 screenshot with a distinctive 10×10 pattern at (20, 15)
        screenshot = Image.new("RGB", (60, 60), color=(100, 100, 100))
        # Draw a checkerboard template at that position (not flat — avoids NCC degenerate case)
        for y in range(10):
            for x in range(10):
                c = 255 if (x + y) % 2 == 0 else 0
                screenshot.putpixel((20 + x, 15 + y), (c, c, c))

        # Template is the same 10×10 checkerboard
        template = Image.new("RGB", (10, 10))
        for y in range(10):
            for x in range(10):
                c = 255 if (x + y) % 2 == 0 else 0
                template.putpixel((x, y), (c, c, c))

        result = Matcher.find(screenshot, template, threshold=0.90)
        assert result is not None
        assert result.x == 20
        assert result.y == 15
        assert result.score > 0.90

    def test_find_returns_none_when_no_match(self) -> None:
        from PIL import Image

        from stars_web.automation.matcher import Matcher

        # Black screenshot, white template — no match above threshold
        screenshot = Image.new("RGB", (50, 50), color=(100, 100, 100))
        template = Image.new("RGB", (10, 10), color=(255, 255, 255))

        result = Matcher.find(screenshot, template, threshold=0.99)
        assert result is None

    def test_find_returns_none_when_template_larger_than_screenshot(self) -> None:
        from PIL import Image

        from stars_web.automation.matcher import Matcher

        screenshot = Image.new("RGB", (10, 10), color=(0, 0, 0))
        template = Image.new("RGB", (20, 20), color=(255, 255, 255))

        result = Matcher.find(screenshot, template)
        assert result is None


# ===========================================================================
# CrossVerifier
# ===========================================================================


class TestCrossVerifierReport:
    """VerificationReport helpers."""

    def test_ok_with_no_mismatches(self) -> None:
        from stars_web.automation.cross_verify import VerificationReport

        report = VerificationReport(checks_run=3)
        assert report.ok() is True

    def test_not_ok_with_mismatches(self) -> None:
        from stars_web.automation.cross_verify import Mismatch, VerificationReport

        report = VerificationReport(
            mismatches=[Mismatch("Planet X", "pop", 100, 200)],
            checks_run=1,
        )
        assert report.ok() is False

    def test_summary_ok(self) -> None:
        from stars_web.automation.cross_verify import VerificationReport

        report = VerificationReport(checks_run=5)
        assert "OK" in report.summary()
        assert "5" in report.summary()

    def test_summary_with_mismatches(self) -> None:
        from stars_web.automation.cross_verify import Mismatch, VerificationReport

        report = VerificationReport(
            mismatches=[Mismatch("Planet Y", "shields", 0, 10)],
            checks_run=2,
        )
        s = report.summary()
        assert "Planet Y" in s
        assert "shields" in s


# ===========================================================================
# Commander
# ===========================================================================


class TestWaypointSetter:
    """WaypointSetter calls the correct Input methods in order."""

    def test_set_calls_click_right_click_return(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.commander import WaypointSetter
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        ws = WaypointSetter(win, settle_delay=0)

        calls: list[str] = []

        with (
            mock.patch.object(win, "focus"),
            mock.patch(
                "stars_web.automation.commander.Input.click",
                side_effect=lambda *a: calls.append("click"),
            ),
            mock.patch(
                "stars_web.automation.commander.Input.right_click",
                side_effect=lambda *a: calls.append("right_click"),
            ),
            mock.patch(
                "stars_web.automation.commander.Input.key",
                side_effect=lambda *a: calls.append("key"),
            ),
            mock.patch("time.sleep"),
        ):
            ws.set(100, 200, 300, 400, confirm=True)

        assert calls.count("click") == 1
        assert calls.count("right_click") == 1
        assert calls.count("key") == 2  # Enter x2 (menu pick + confirm)

    def test_set_no_confirm(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.commander import WaypointSetter
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        ws = WaypointSetter(win, settle_delay=0)

        calls: list[str] = []

        with (
            mock.patch.object(win, "focus"),
            mock.patch(
                "stars_web.automation.commander.Input.click",
                side_effect=lambda *a: calls.append("click"),
            ),
            mock.patch(
                "stars_web.automation.commander.Input.right_click",
                side_effect=lambda *a: calls.append("right_click"),
            ),
            mock.patch(
                "stars_web.automation.commander.Input.key",
                side_effect=lambda *a: calls.append("key"),
            ),
            mock.patch("time.sleep"),
        ):
            ws.set(100, 200, 300, 400, confirm=False)

        assert calls.count("key") == 1  # only one Enter (menu pick)


class TestProductionEditor:
    """ProductionEditor calls the correct Input methods."""

    def test_open_double_clicks(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.commander import ProductionEditor
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        pe = ProductionEditor(win, settle_delay=0)

        click_count = []

        with (
            mock.patch.object(win, "focus"),
            mock.patch(
                "stars_web.automation.commander.Input.click",
                side_effect=lambda *a: click_count.append(1),
            ),
            mock.patch("time.sleep"),
        ):
            pe.open(200, 300)

        assert sum(click_count) == 2

    def test_confirm_sends_return(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.commander import ProductionEditor
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        pe = ProductionEditor(win, settle_delay=0)

        from stars_web.automation.input import Input

        with (
            mock.patch.object(win, "focus"),
            mock.patch("stars_web.automation.commander.Input.key") as mock_key,
            mock.patch("time.sleep"),
        ):
            pe.confirm()

        mock_key.assert_called_once_with(Input.VK_RETURN)

    def test_cancel_sends_escape(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.commander import ProductionEditor
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        pe = ProductionEditor(win, settle_delay=0)

        from stars_web.automation.input import Input

        with (
            mock.patch.object(win, "focus"),
            mock.patch("stars_web.automation.commander.Input.key") as mock_key,
            mock.patch("time.sleep"),
        ):
            pe.cancel()

        mock_key.assert_called_once_with(Input.VK_ESCAPE)


class TestResearchAllocator:
    """ResearchAllocator.open() navigates to the Research screen."""

    def test_open_goes_to_research_screen(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.commander import ResearchAllocator
        from stars_web.automation.navigator import StarScreen
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        ra = ResearchAllocator(win, settle_delay=0)

        with (
            mock.patch.object(win, "focus"),
            mock.patch.object(ra._nav, "go") as mock_go,
            mock.patch("time.sleep"),
        ):
            ra.open()

        mock_go.assert_called_once_with(StarScreen.RESEARCH)


# ===========================================================================
# GUIHostRunner
# ===========================================================================


class TestGUIHostRunnerPaths:
    """GUIHostRunner resolves .m file path correctly."""

    def test_m_file_path(self, tmp_path: Path) -> None:
        from stars_web.automation.host_runner import GUIHostRunner
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        runner = GUIHostRunner(win, game_dir=tmp_path, game_prefix="Game", player_number=3)

        assert runner.m_file == tmp_path / "Game.m3"

    def test_generate_turn_raises_if_m_missing(self, tmp_path: Path) -> None:
        from stars_web.automation.host_runner import GUIHostRunner
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        runner = GUIHostRunner(win, game_dir=tmp_path, game_prefix="Game")

        with pytest.raises(FileNotFoundError):
            runner.generate_turn(timeout=1)

    def test_generate_turn_detects_mtime_change(self, tmp_path: Path) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        import threading

        from stars_web.automation.host_runner import GUIHostRunner
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        m = tmp_path / "Game.m1"
        m.write_bytes(b"old turn data")

        runner = GUIHostRunner(win, game_dir=tmp_path, game_prefix="Game")

        def write_new_m():
            # Wait briefly, then update the file so mtime changes
            import time as _t

            _t.sleep(0.15)
            m.write_bytes(b"new turn data")

        t = threading.Thread(target=write_new_m, daemon=True)

        with (
            mock.patch.object(win, "focus"),
            mock.patch.object(runner, "open_file_menu"),
            mock.patch.object(runner, "navigate_to_generate_turn"),
        ):
            t.start()
            result = runner.generate_turn(timeout=5)
            t.join(timeout=2)

        assert result == m

    def test_generate_turn_timeout(self, tmp_path: Path) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows only")

        from stars_web.automation.host_runner import GUIHostRunner
        from stars_web.automation.window import StarsWindow

        win = StarsWindow(hwnd=1)
        m = tmp_path / "Game.m1"
        m.write_bytes(b"old")

        runner = GUIHostRunner(win, game_dir=tmp_path, game_prefix="Game")

        with (
            mock.patch.object(win, "focus"),
            mock.patch.object(runner, "open_file_menu"),
            mock.patch.object(runner, "navigate_to_generate_turn"),
            mock.patch("stars_web.automation.host_runner._POLL_INTERVAL", 0),
        ):
            with pytest.raises(TimeoutError):
                runner.generate_turn(timeout=0.05)
