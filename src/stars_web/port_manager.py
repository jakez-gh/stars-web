"""Port management for Stars! web service.

Implements deterministic, non-conflicting port allocation:
- Same port for every run on the same machine/workspace
- Ports in range 10000-40000 (avoids system, privileged, and ephemeral ranges)
- Lock file prevents multiple instances from running simultaneously
- Automatic cleanup of stale lock files
"""

import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def get_workspace_id() -> str:
    """Generate a unique, stable ID for this workspace.

    Uses hostname + workspace path hash to ensure same workspace always
    gets the same port across runs and machines.
    """
    hostname = socket.gethostname()
    workspace = os.getcwd()
    combined = f"{hostname}:{workspace}".encode()
    return hashlib.md5(combined).hexdigest()[:12]


def get_assigned_port() -> int:
    """Get the port assigned to this workspace.

    Returns the same port for every run on the same machine/workspace.
    Port is allocated in range 10000-40000 to avoid:
    - System ports (0-1023)
    - Privileged ports (1024-49151)
    - Ephemeral/dynamic ports (49152-65535)

    Returns:
        int: Port number in range 10000-40000
    """
    workspace_id = get_workspace_id()
    # Convert hex to int, then map to port range
    hash_value = int(workspace_id, 16)
    port_range = 40000 - 10000
    port = (hash_value % port_range) + 10000
    return port


def get_lock_file() -> Path:
    """Get the path to the workspace lock file."""
    config_dir = Path.home() / ".stars_web"
    config_dir.mkdir(exist_ok=True)
    workspace_id = get_workspace_id()
    return config_dir / f"{workspace_id}.lock"


def kill_pid(pid: int) -> bool:
    """Send a termination signal to *pid*.

    On POSIX sends SIGTERM; on Windows uses ``taskkill /F /PID``.
    Returns True if the signal was delivered, False if the PID no longer
    exists or the operation is not permitted.
    """
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        else:
            os.kill(pid, signal.SIGTERM)
            return True
    except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
        return False


def is_port_in_use(port: int) -> bool:
    """Check if a port is currently in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def acquire_lock(port: int, timeout: float = 30.0) -> bool:
    """Acquire the lock for this port.

    If another process holds the lock, attempt to kill it.
    Waits up to `timeout` seconds for the port to become free.

    Args:
        port: Port number to lock
        timeout: Maximum seconds to wait for port to become free

    Returns:
        bool: True if lock acquired, False if timeout exceeded
    """
    lock_file = get_lock_file()
    now = time.time()
    deadline = now + timeout

    while time.time() < deadline:
        # Try to acquire the lock
        if lock_file.exists():
            try:
                with open(lock_file, "r") as f:
                    data = json.load(f)
                old_pid = data.get("pid")
                is_stale = data.get("timestamp", 0) < (now - 60)

                if old_pid and not is_stale:
                    if old_pid == os.getpid():
                        # This process already holds the lock; refresh timestamp.
                        pass  # fall through to overwrite
                    else:
                        # Active lock held by another process — kill it.
                        killed = kill_pid(old_pid)
                        if killed:
                            # Give the old process a moment to release the port.
                            time.sleep(1.5)
                        elif is_port_in_use(port):
                            # PID already gone but port still bound — wait.
                            time.sleep(1)
                            continue
                # Stale lock or old process gone — fall through to overwrite.
            except (json.JSONDecodeError, IOError):
                # Corrupted lock file — overwrite.
                pass

        # Write new lock
        try:
            with open(lock_file, "w") as f:
                json.dump(
                    {
                        "pid": os.getpid(),
                        "port": port,
                        "timestamp": now,
                        "workspace": os.getcwd(),
                    },
                    f,
                )
            return True
        except IOError:
            time.sleep(0.5)

    return False


def release_lock() -> None:
    """Release the lock file for this workspace."""
    lock_file = get_lock_file()
    try:
        lock_file.unlink(missing_ok=True)
    except Exception:
        pass
