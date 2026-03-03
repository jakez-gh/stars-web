# Stars! GUI automation reference templates

This directory holds PNG reference images used by `matcher.py` for
template matching against live Stars! screenshots.

## Adding templates

1. Run Stars! via `Launcher.start()`
2. Navigate to the desired screen with `Navigator.go()`
3. Capture a screenshot with `Screen.save(win, "shot.png")`
4. Crop the region of interest in an image editor
5. Save the cropped PNG here with a descriptive name, e.g.:
   - `planet_header.png` — top-left corner of the planet summary panel
   - `fleet_header.png`  — top-left corner of the fleet list panel
   - `scanner_minimap.png` — the mini-map in the scanner screen

## Naming convention

`<screen>_<element>.png`
