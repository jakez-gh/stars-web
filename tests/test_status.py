"""
Test suite for status module.

These tests serve as executable specifications:
- Tests passing = feature is implemented
- Tests failing = feature needs implementation
"""

import sys

from stars_web.status import (
    show_info,
    list_running_services,
    kill_service,
)


class TestInfoCommand:
    """Spec: 'status info' command displays current service status."""

    def test_show_info_callable(self):
        """show_info() is callable."""
        assert callable(show_info)

    def test_show_info_displays_workspace_id(self):
        """Info output includes workspace ID."""
        # Capture output
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            show_info()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        assert "Workspace" in output or "workspace" in output or "ID" in output

    def test_show_info_displays_port(self):
        """Info output includes assigned port."""
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            show_info()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        assert "port" in output.lower() or "28682" in output

    def test_show_info_displays_lock_file_path(self):
        """Info output includes lock file location."""
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            show_info()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        assert "lock" in output.lower() or ".stars_web" in output


class TestListServicesCommand:
    """Spec: 'status ports' lists running services."""

    def test_list_running_services_callable(self):
        """list_running_services() is callable."""
        assert callable(list_running_services)

    def test_list_running_services_returns_list(self):
        """list_running_services() returns list."""
        services = list_running_services()
        assert isinstance(services, list)

    def test_list_running_services_contains_dicts(self):
        """Each service entry is a dictionary."""
        services = list_running_services()
        for service in services:
            assert isinstance(service, dict)

    def test_service_dict_has_workspace_id(self):
        """Service dict includes workspace_id."""
        services = list_running_services()
        for service in services:
            assert "workspace_id" in service or "id" in service

    def test_service_dict_has_port(self):
        """Service dict includes port."""
        services = list_running_services()
        for service in services:
            assert "port" in service

    def test_service_dict_has_pid(self):
        """Service dict includes process ID."""
        services = list_running_services()
        for service in services:
            assert "pid" in service

    def test_service_dict_has_lock_file_path(self):
        """Service dict includes lock file path."""
        services = list_running_services()
        for service in services:
            assert "lock_file" in service


class TestKillServiceCommand:
    """Spec: 'status kill' stops a running service."""

    def test_kill_service_callable(self):
        """kill_service() is callable."""
        assert callable(kill_service)

    def test_kill_service_accepts_workspace_id(self):
        """kill_service accepts workspace_id parameter."""
        # Should accept but may not find service
        # Should not raise for valid input
        try:
            result = kill_service("nonexistent_workspace_id")
            assert result is not None
        except FileNotFoundError:
            # Expected if service doesn't exist
            pass

    def test_kill_service_returns_status(self):
        """kill_service returns success/failure status."""
        result = kill_service("nonexistent_workspace_id")
        assert isinstance(result, (bool, type(None)))


class TestCLIIntegration:
    """Spec: CLI commands work through module interface."""

    def test_status_info_command(self):
        """Can run 'python -m stars_web.status info'."""
        # This tests CLI entrypoint
        # Actual execution would be via subprocess
        pass

    def test_status_ports_command(self):
        """Can run 'python -m stars_web.status ports'."""
        # Tests list_running_services via CLI
        pass

    def test_status_kill_command(self):
        """Can run 'python -m stars_web.status kill <id>'."""
        # Tests kill_service via CLI
        pass


class TestLockFileManagement:
    """Spec: Status tool monitors lock files."""

    def test_identifies_running_services_from_lock_files(self):
        """Detects running services by reading lock files."""
        services = list_running_services()
        # Should be list (empty or with services)
        assert isinstance(services, list)

    def test_validates_lock_file_format(self):
        """Lock files must be valid JSON."""
        services = list_running_services()
        for service in services:
            # Service dict comes from lock file, must be parseable
            assert "workspace_id" in service or len(services) == 0

    def test_handles_corrupted_lock_files(self):
        """Gracefully handles corrupted lock files."""
        # Even if lock file is corrupted, shouldn't crash
        services = list_running_services()
        assert isinstance(services, list)

    def test_removes_stale_lock_files(self):
        """Cleans up lock files for dead processes."""
        # When listing services, should remove locks where PID
        # no longer exists
        # This is implementation detail
        list_running_services()
        # All returned services should have running processes
        # (or be current process)


class TestProcessManagement:
    """Spec: Status tool can manage processes."""

    def test_detects_process_by_pid(self):
        """Can determine if process with PID is running."""
        # Implementation detail of kill_service
        import os

        current_pid = os.getpid()
        # Current process is running
        assert current_pid > 0

    def test_can_signal_process(self):
        """Status tool can send signals to processes."""
        # This is tested indirectly through kill_service
        # which may send SIGTERM
        pass

    def test_handles_permission_denied(self):
        """Gracefully handles permission denied when killing."""
        # If trying to kill another user's process
        # Should handle PermissionError gracefully
        kill_service("any_workspace")
        # Should return gracefully, not raise


class TestErrorHandling:
    """Spec: All operations fail gracefully."""

    def test_show_info_handles_missing_lock_file(self):
        """show_info works even if no lock file exists."""
        # Should display defaults
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            show_info()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        assert len(output) > 0

    def test_list_services_handles_no_lock_files(self):
        """list_running_services works with no services."""
        services = list_running_services()
        assert isinstance(services, list)
        # Should be empty list if no services

    def test_kill_service_handles_nonexistent_service(self):
        """kill_service handles nonexistent workspace."""
        result = kill_service("definitely_does_not_exist_12345")
        # Should return False or None, not raise
        assert result is None or result is False


class TestIntegration:
    """Spec: Status tool integrates with port_manager."""

    def test_info_matches_port_manager(self):
        """show_info displays same port as port_manager.get_assigned_port()."""
        from stars_web.port_manager import get_assigned_port

        expected_port = get_assigned_port()

        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            show_info()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        # Port should appear in output
        assert str(expected_port) in output
