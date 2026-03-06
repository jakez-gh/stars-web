#!/usr/bin/env python3
"""Stars! Web Service Status and Management Tool.

Displays information about running Stars! services, port assignments,
and provides commands to manage them.

Usage:
    python -m stars_web.status [command]

Commands:
    info        Show workspace ID and assigned port
    ports       List all running Stars! services and their ports
    kill        Kill all running Stars! services
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from stars_web.port_manager import (
    get_assigned_port,
    get_lock_file,
    get_workspace_id,
    is_port_in_use,
)


def show_info() -> None:
    """Show workspace information."""
    workspace_id = get_workspace_id()
    port = get_assigned_port()
    lock_file = get_lock_file()

    print("=" * 60)
    print("Workspace Information")
    print("=" * 60)
    print(f"Workspace ID:     {workspace_id}")
    print(f"Assigned Port:    {port}")
    print(f"Current Dir:      {os.getcwd()}")
    print(f"Lock File:        {lock_file}")
    print(f"Port in Use:      {is_port_in_use(port)}")

    if lock_file.exists():
        try:
            with open(lock_file) as f:
                lock_data = json.load(f)
                print(f"Lock Owner PID:   {lock_data.get('pid', 'unknown')}")
                print(f"Lock Timestamp:   {lock_data.get('timestamp', 'unknown')}")
        except Exception:
            pass

    print("=" * 60)


def list_running_services() -> list[dict]:
    """List all running Stars! services identified by lock files.

    Returns:
        List of dicts with service info (workspace_id, port, pid, lock_file, workspace).
        Returns empty list if no services found.
    """
    config_dir = Path.home() / ".stars_web"
    services = []

    if not config_dir.exists():
        return services

    lock_files = list(config_dir.glob("*.lock"))
    if not lock_files:
        return services

    for lock_file in sorted(lock_files):
        try:
            with open(lock_file) as f:
                data = json.load(f)
                workspace_id = lock_file.stem
                port = data.get("port", 0)
                pid = data.get("pid", 0)
                workspace = data.get("workspace", "")

                services.append(
                    {
                        "workspace_id": workspace_id,
                        "port": port,
                        "pid": pid,
                        "lock_file": str(lock_file),
                        "workspace": workspace,
                    }
                )
        except Exception:
            # Skip corrupted lock files
            continue

    return services


def kill_service(workspace_id: str | None = None) -> bool:
    """Kill a Stars! service by workspace ID or current workspace.

    Args:
        workspace_id: The workspace ID to kill, or None for current workspace

    Returns:
        True if service was killed, False if not found or error
    """
    if workspace_id is None:
        workspace_id = get_workspace_id()

    lock_file = Path.home() / ".stars_web" / f"{workspace_id}.lock"

    if not lock_file.exists():
        return False

    try:
        with open(lock_file) as f:
            data = json.load(f)
            pid = data.get("pid")

            if pid:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True,
                    )
                else:
                    os.kill(int(pid), 9)

        # Clean up lock file
        lock_file.unlink(missing_ok=True)
        return True

    except Exception:
        return False


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        command = "info"
    else:
        command = sys.argv[1]

    if command == "info":
        show_info()
    elif command == "ports":
        services = list_running_services()
        if not services:
            print("No Stars! services running (no lock files found).")
        else:
            print("=" * 60)
            print("Running Stars! Services")
            print("=" * 60)
            for service in services:
                workspace_id = service["workspace_id"]
                port = service["port"]
                pid = service["pid"]
                workspace = service["workspace"]
                in_use = is_port_in_use(port) if isinstance(port, int) else False

                print(f"  {workspace_id}")
                print(
                    f"    Port:      {port} {'(in use)' if in_use else '(not listening)'}"
                )
                print(f"    PID:       {pid}")
                print(f"    Workspace: {workspace}")
                print()
            print("=" * 60)
    elif command == "kill":
        workspace_id = get_workspace_id()
        success = kill_service(workspace_id)
        if success:
            print(f"Successfully killed service {workspace_id}")
        else:
            print(f"No service found for workspace {workspace_id}")
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
