"""Run the Stars! web UI development server.

Usage:
    python -m stars_web.run [game_dir]

If game_dir is not provided, uses STARS_GAME_DIR env var or
falls back to ../autoplay/tests/data.
"""

import os
import subprocess
import sys

from stars_web.app import create_app

_PORT = 5000


def kill_port(port: int) -> bool:
    """Kill any process currently listening on *port*.

    Returns True if at least one process was found and signalled,
    False if the port was already free (safe no-op).
    Works on Windows (netstat + taskkill) and POSIX (fuser).
    """
    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
        )
        pids: set[str] = set()
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pids.add(parts[-1])
        if not pids:
            return False
        for pid in pids:
            subprocess.run(
                ["taskkill", "/F", "/PID", pid],
                capture_output=True,
                check=False,
            )
        return True
    else:
        result = subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0


def main() -> None:
    game_dir = sys.argv[1] if len(sys.argv) > 1 else None
    app = create_app(game_dir)
    print(f"Loading game from: {app.config['GAME_DIR']}")
    print(f"Star map at http://127.0.0.1:{_PORT}")
    # WERKZEUG_RUN_MAIN is set to 'true' inside the watchdog child process.
    # Only kill the port in the outer launcher process, never in the reloader.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        if kill_port(_PORT):
            print(f"Killed existing process on port {_PORT}")
    app.run(debug=True, port=_PORT)


if __name__ == "__main__":
    main()
