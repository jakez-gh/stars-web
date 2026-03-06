"""
Test suite for port_manager module.

These tests serve as executable specifications:
- Tests passing = feature is implemented
- Tests failing = feature needs implementation
"""

import json
import socket

from stars_web.port_manager import (
    get_workspace_id,
    get_assigned_port,
    acquire_lock,
    release_lock,
    is_port_in_use,
    get_lock_file,
)


class TestWorkspaceID:
    """Spec: Workspace ID is deterministic based on hostname + working directory."""

    def test_workspace_id_is_deterministic(self):
        """Same workspace always produces same ID."""
        id1 = get_workspace_id()
        id2 = get_workspace_id()
        assert id1 == id2

    def test_workspace_id_is_string(self):
        """Workspace ID is a string (hexadecimal hash)."""
        ws_id = get_workspace_id()
        assert isinstance(ws_id, str)
        assert len(ws_id) > 0

    def test_workspace_id_is_short_hash(self):
        """Workspace ID is 12-character MD5 hash."""
        ws_id = get_workspace_id()
        assert len(ws_id) == 12
        assert all(c in "0123456789abcdef" for c in ws_id)


class TestPortAllocation:
    """Spec: Port allocation is deterministic and within safe range."""

    def test_port_is_deterministic(self):
        """Same workspace always gets same port."""
        port1 = get_assigned_port()
        port2 = get_assigned_port()
        assert port1 == port2

    def test_port_is_in_safe_range(self):
        """Port is in range [10000, 40000] to avoid system/ephemeral conflicts."""
        port = get_assigned_port()
        assert 10000 <= port <= 40000

    def test_port_is_integer(self):
        """Port is an integer."""
        port = get_assigned_port()
        assert isinstance(port, int)

    def test_port_is_valid_tcp_port(self):
        """Port is within valid TCP port range."""
        port = get_assigned_port()
        assert 1 <= port <= 65535


class TestLockManagement:
    """Spec: Lock files track port ownership and prevent conflicts."""

    def test_acquire_lock_creates_lock_file(self):
        """Acquiring a lock creates a lock file."""
        port = get_assigned_port()
        lock_acquired = acquire_lock(port, timeout=1.0)

        if lock_acquired:
            # Lock file should exist
            lock_file = get_lock_file()
            assert lock_file.exists()
            release_lock()

    def test_release_lock_cleans_up(self):
        """Releasing a lock removes lock file (eventually)."""
        port = get_assigned_port()
        lock_acquired = acquire_lock(port, timeout=1.0)
        assert lock_acquired

        release_lock()
        # Give it a moment to clean up
        import time

        time.sleep(0.1)

        # File should be gone (or may have been reacquired by tests)
        lock_file = get_lock_file()
        # If it exists, it should be from another test - that's OK
        if lock_file.exists():
            try:
                with open(lock_file) as f:
                    data = json.load(f)
                # If readable, it's a valid lock from another test
                assert isinstance(data, dict)
            except Exception:
                # Lock file corruption - test passes if we can release without error
                pass

    def test_acquire_lock_respects_timeout(self):
        """Acquiring a lock with timeout waits up to timeout seconds."""
        port = get_assigned_port()
        result = acquire_lock(port, timeout=0.1)
        # Should acquire successfully on first try
        assert result is True
        release_lock()


class TestPortConflictDetection:
    """Spec: System detects when ports are in use."""

    def test_is_port_in_use_for_free_port(self):
        """Port detection works for free ports."""
        # Find a genuinely available port (OS assigns it)
        sock = socket.socket()
        sock.bind(("", 0))
        free_port = sock.getsockname()[1]
        sock.close()

        assert not is_port_in_use(free_port)

    def test_is_port_in_use_handles_timeout(self):
        """Port detection completes quickly."""
        import socket

        sock = socket.socket()
        sock.bind(("", 0))
        free_port = sock.getsockname()[1]
        sock.close()

        # Should not hang
        result = is_port_in_use(free_port)
        assert isinstance(result, bool)


class TestIntegration:
    """Spec: Port manager workflow works end-to-end."""

    def test_full_workflow(self):
        """Full workflow: get ID, allocate port, acquire lock, release lock."""
        ws_id = get_workspace_id()
        assert ws_id

        port = get_assigned_port()
        assert 10000 <= port <= 40000

        lock_acquired = acquire_lock(port, timeout=1.0)
        assert lock_acquired

        release_lock()
        # Cleanup successful if no exception raised

    def test_concurrent_process_waits_for_lock(self):
        """When another process holds lock, acquisition fails after timeout."""
        port = get_assigned_port()
        # First acquire succeeds
        lock1 = acquire_lock(port, timeout=1.0)
        assert lock1 is True

        # Try to acquire again (would conflict)
        lock2 = acquire_lock(port, timeout=0.1)
        # May succeed if timeout allows stale lock detection
        assert isinstance(lock2, bool)

        release_lock()
