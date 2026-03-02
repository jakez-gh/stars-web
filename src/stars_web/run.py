"""Run the Stars! web UI development server.

Usage:
    python -m stars_web.run [game_dir]

If game_dir is not provided, uses STARS_GAME_DIR env var or
falls back to ../autoplay/tests/data.
"""

import sys

from stars_web.app import create_app


def main():
    game_dir = sys.argv[1] if len(sys.argv) > 1 else None
    app = create_app(game_dir)
    print(f"Loading game from: {app.config['GAME_DIR']}")
    print("Star map at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
