"""Template matching: locate UI elements in Stars! screenshots.

Uses NumPy for normalised cross-correlation (no OpenCV required).
Reference template PNGs live in ``src/stars_web/automation/templates/``.

Usage::

    from PIL import Image
    from stars_web.automation.matcher import Matcher

    screenshot = Image.open("shot.png")
    match = Matcher.find(screenshot, "templates/planet_header.png")
    if match:
        x, y, score = match

    ok = Matcher.pixel_matches(screenshot, x=42, y=10, expected=(0, 0, 0))
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image

# Directory where reference template PNGs are stored
TEMPLATES_DIR = Path(__file__).parent / "templates"


class MatchResult(NamedTuple):
    """Result of a template-match search."""

    x: int
    """Left edge of the best match in the screenshot (pixels)."""
    y: int
    """Top edge of the best match in the screenshot (pixels)."""
    score: float
    """Normalised cross-correlation score in the range ``[0.0, 1.0]``."""


def _to_gray_array(img: Image.Image) -> np.ndarray:
    """Convert a PIL Image to a 2-D float32 grayscale array."""
    return np.array(img.convert("L"), dtype=np.float32)


def _ncc(image: np.ndarray, template: np.ndarray) -> np.ndarray:
    """Compute a normalised cross-correlation map using sliding windows.

    Returns an array the same shape as *image* (padded with zeros at the
    edges where the template would extend beyond the image).  Values range
    from -1.0 to 1.0; 1.0 is a perfect match.
    """
    ih, iw = image.shape
    th, tw = template.shape

    # Subtract template mean
    tmpl = template - template.mean()
    tmpl_norm = np.sqrt((tmpl**2).sum()) or 1.0

    result = np.zeros((ih, iw), dtype=np.float32)

    # Slide the template across the image with a vectorised stride trick
    # (efficient enough for typical Stars! dialog sizes)
    for y in range(ih - th + 1):
        for x in range(iw - tw + 1):
            patch = image[y : y + th, x : x + tw]
            patch_zm = patch - patch.mean()
            denom = np.sqrt((patch_zm**2).sum()) * tmpl_norm or 1.0
            result[y, x] = float(np.sum(patch_zm * tmpl) / denom)

    return result


class Matcher:
    """Template-matching helpers for Stars! screenshots."""

    DEFAULT_THRESHOLD: float = 0.85
    """Default minimum NCC score required to accept a match."""

    # ------------------------------------------------------------------
    # Template search
    # ------------------------------------------------------------------

    @staticmethod
    def find(
        screenshot: Image.Image,
        template: Image.Image | str | Path,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> MatchResult | None:
        """Search *screenshot* for *template*.

        Parameters
        ----------
        screenshot:
            Full-screen or windowed PIL Image to search within.
        template:
            Reference image — either a PIL Image, a file path, or a
            template name relative to :data:`TEMPLATES_DIR`.
        threshold:
            Minimum NCC score to accept.  Matches below this are ignored.

        Returns
        -------
        MatchResult or None
            The best match above *threshold*, or *None* if not found.
        """
        if isinstance(template, (str, Path)):
            p = Path(template)
            if not p.is_absolute():
                p = TEMPLATES_DIR / p
            template = Image.open(p)

        ss_arr = _to_gray_array(screenshot)
        tpl_arr = _to_gray_array(template)

        if tpl_arr.shape[0] > ss_arr.shape[0] or tpl_arr.shape[1] > ss_arr.shape[1]:
            return None

        corr = _ncc(ss_arr, tpl_arr)
        best_flat = int(np.argmax(corr))
        best_y, best_x = divmod(best_flat, corr.shape[1])
        best_score = float(corr[best_y, best_x])

        if best_score < threshold:
            return None

        return MatchResult(x=best_x, y=best_y, score=best_score)

    # ------------------------------------------------------------------
    # Pixel helpers
    # ------------------------------------------------------------------

    @staticmethod
    def pixel_at(screenshot: Image.Image, x: int, y: int) -> tuple[int, int, int]:
        """Return the (R, G, B) colour of pixel (*x*, *y*)."""
        rgb = screenshot.convert("RGB")
        return rgb.getpixel((x, y))  # type: ignore[return-value]

    @staticmethod
    def pixel_matches(
        screenshot: Image.Image,
        x: int,
        y: int,
        expected: tuple[int, int, int],
        tolerance: int = 10,
    ) -> bool:
        """Return True if the pixel at (*x*, *y*) is close to *expected*.

        Parameters
        ----------
        tolerance:
            Maximum per-channel absolute difference allowed.
        """
        actual = Matcher.pixel_at(screenshot, x, y)
        return all(abs(int(a) - int(e)) <= tolerance for a, e in zip(actual, expected))

    @staticmethod
    def list_templates() -> list[Path]:
        """Return all PNG files in :data:`TEMPLATES_DIR`."""
        if not TEMPLATES_DIR.exists():
            return []
        return sorted(TEMPLATES_DIR.glob("*.png"))
