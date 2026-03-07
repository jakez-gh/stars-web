"""Run the Stars! web UI development server.

Usage:
    python -m stars_web.run [game_dir]

If game_dir is not provided, uses STARS_GAME_DIR env var or
falls back to ../autoplay/tests/data.

Port Assignment:
    - Automatically selects a port in range 10000-40000
    - Same port for every run on the same machine/workspace
    - Avoids conflicts with system, privileged, and ephemeral port ranges
    - Automatically kills any existing process using the assigned port
    - Acquires a lock to prevent multiple instances on different ports

Server Lifecycle:
    - Gracefully handles shutdown signals (SIGTERM, SIGINT)
    - Automatically cleans up lock files on exit
    - Shows clear status messages for port and workspace info
"""

import os
import subprocess
import sys

from stars_web.app import create_app
from stars_web.lifecycle import setup_lifecycle_manager
from stars_web.port_manager import (
    acquire_lock,
    get_assigned_port,
    is_port_in_use,
    release_lock,
)


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
            # Match lines with the specific port
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pids.add(parts[-1])
        if not pids:
            return False
        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                pass
        return True
    else:
        try:
            result = subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


def main() -> None:
    """Start the web server with deterministic port allocation."""
    # Get the assigned port for this workspace
    port = get_assigned_port()

    # The Werkzeug reloader spawns a child process (WERKZEUG_RUN_MAIN=true).
    # Only the outer launcher process needs to acquire/release the lock.
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if not is_reloader_child:
        # Set up lifecycle management for graceful shutdown
        lifecycle = setup_lifecycle_manager()

        # Attempt to acquire the lock (waits up to 30 seconds for existing process)
        print(f"Acquiring lock for port {port}...")
        if not acquire_lock(port, timeout=30.0):
            print(f"ERROR: Could not acquire lock for port {port}")
            print("Another instance may be running or the port is stuck.")
            print("Try manually killing any process on this port or wait a minute.")
            sys.exit(1)

        # Register cleanup on exit
        lifecycle.on_exit(release_lock)

    try:
        if not is_reloader_child:
            # Kill any existing process on the port (safety measure)
            if is_port_in_use(port):
                print(f"Killing existing process on port {port}...")
                kill_port(port)

        # Load game directory
        game_dir = sys.argv[1] if len(sys.argv) > 1 else None
        app = create_app(game_dir)

        if not is_reloader_child:
            print(f"\n{'=' * 60}")
            print(f"Loading game from: {app.config['GAME_DIR']}")
            print(f"Star map at http://127.0.0.1:{port}")
            print(f"Workspace port: {port} (deterministic, consistent across runs)")
            print(f"{'=' * 60}\n")

        # Only run with reloader in the outer launcher process
        if not is_reloader_child:
            app.run(debug=True, port=port, use_reloader=True)
        else:
            app.run(debug=True, port=port, use_reloader=False)

    except Exception as e:
        print(f"Error starting server: {e}")
        raise
    finally:
        # Lifecycle manager cleanup is called automatically via atexit
        pass


if __name__ == "__main__":
    main()
