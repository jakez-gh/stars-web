"""Web asset build and deployment for Stars! web service.

Ensures web pages are up-to-date and cache-busting is applied
on each successful CI/CD run.
"""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path


def get_static_dir() -> Path:
    """Get the static assets directory path."""
    return Path(__file__).parent / "static"


def get_templates_dir() -> Path:
    """Get the templates directory path."""
    return Path(__file__).parent / "templates"


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file for cache-busting."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        sha256.update(f.read())
    return sha256.hexdigest()[:8]


def compute_asset_hashes() -> dict[str, str]:
    """Compute hashes for all web assets.

    Returns a dict mapping asset names to their hashes for use in templates.
    This ensures browser cache is invalidated when assets change.
    """
    static_dir = get_static_dir()
    asset_hashes = {}

    css_file = static_dir / "css" / "star_map.css"
    js_file = static_dir / "js" / "star_map.js"

    if css_file.exists():
        asset_hashes["star_map_css"] = compute_file_hash(css_file)

    if js_file.exists():
        asset_hashes["star_map_js"] = compute_file_hash(js_file)

    return asset_hashes


def write_cache_manifest(asset_hashes: dict[str, str]) -> None:
    """Write a cache manifest file with asset hashes.

    This file is loaded by app.py to provide cache-buster parameters
    to the Flask template context.

    Args:
        asset_hashes: Dict mapping asset names to their SHA256 hashes
    """
    static_dir = get_static_dir()
    manifest_path = static_dir / "._cache_manifest.json"

    manifest = {
        "build_time": datetime.utcnow().isoformat(),
        "timestamp": time.time(),
        "version": "1.0",
        "hashes": asset_hashes,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2))


def build_web_assets() -> dict[str, str]:
    """Run full web asset build pipeline.

    1. Computes hashes for all assets
    2. Writes cache manifest with hashes
    3. Returns mapping of assets to hashes

    This should be called at the end of each successful CI run.

    Returns:
        Dict mapping asset names to their cache-buster hashes
    """
    print("Building web assets...")
    asset_hashes = compute_asset_hashes()
    write_cache_manifest(asset_hashes)
    print(f"Updated {len(asset_hashes)} asset cache-buster hashes")
    print("Web assets built successfully")
    return asset_hashes


if __name__ == "__main__":
    build_web_assets()
