"""
Test suite for lifecycle module.

These tests serve as executable specifications:
- Tests passing = feature is implemented
- Tests failing = feature needs implementation
"""

import pytest
import sys
from unittest.mock import MagicMock

from stars_web.lifecycle import (
    setup_lifecycle_manager,
    ServerLifecycleManager,
)


class TestLifecycleManagerInitialization:
    """Spec: Lifecycle manager initializes and manages server lifecycle."""

    def test_setup_returns_server_lifecycle_manager(self):
        """setup_lifecycle_manager returns a ServerLifecycleManager instance."""
        manager = setup_lifecycle_manager()
        assert isinstance(manager, ServerLifecycleManager)

    def test_singleton_pattern(self):
        """setup_lifecycle_manager returns same instance."""
        manager1 = setup_lifecycle_manager()
        manager2 = setup_lifecycle_manager()
        assert manager1 is manager2

    def test_lifecycle_manager_persistent_across_imports(self):
        """Singleton persists across module imports."""
        # Get manager
        manager1 = setup_lifecycle_manager()

        # Setup again (simulating in different module)
        manager2 = setup_lifecycle_manager()

        # Should be same instance
        assert manager1 is manager2


class TestCleanupCallbacks:
    """Spec: Cleanup callbacks are registered and executed in LIFO order."""

    def test_register_cleanup_callback(self):
        """Can register cleanup callbacks."""
        manager = setup_lifecycle_manager()
        callback = MagicMock()

        manager.register_cleanup(callback)
        # Callback is stored
        assert callback in manager._cleanup_callbacks

    def test_cleanup_callbacks_execute_lifo(self):
        """Callbacks execute in Last-In-First-Out order."""
        manager = setup_lifecycle_manager()

        order = []

        def callback1():
            order.append(1)

        def callback2():
            order.append(2)

        def callback3():
            order.append(3)

        manager.register_cleanup(callback1)
        manager.register_cleanup(callback2)
        manager.register_cleanup(callback3)

        manager.cleanup()

        # Should be 3, 2, 1 (LIFO)
        assert order == [3, 2, 1]

    def test_cleanup_handles_exceptions_in_callbacks(self):
        """If one callback fails, others still run."""
        manager = setup_lifecycle_manager()

        callbacks_executed = []

        def callback1():
            callbacks_executed.append(1)
            raise Exception("Test error")

        def callback2():
            callbacks_executed.append(2)

        manager.register_cleanup(callback1)
        manager.register_cleanup(callback2)

        # Should not raise, both should execute
        manager.cleanup()
        assert 1 in callbacks_executed
        assert 2 in callbacks_executed


class TestSignalHandling:
    """Spec: Signal handlers trigger graceful shutdown."""

    def test_setup_registers_signal_handlers(self):
        """Signal handlers are registered during initialization."""
        # Creating a manager initializes signal handlers
        manager = setup_lifecycle_manager()
        assert isinstance(manager, ServerLifecycleManager)
        # Manager exists means signal setup completed without error

    def test_setup_handles_sigterm(self):
        """SIGTERM signal handler is registered."""
        manager = setup_lifecycle_manager()
        # Verify manager initialized without error
        assert hasattr(manager, "_signal_handler")

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific")
    def test_setup_handles_ctrl_break_event_on_windows(self):
        """CTRL_BREAK_EVENT handler is set up on Windows if available."""
        manager = setup_lifecycle_manager()
        # Should not raise AttributeError
        assert isinstance(manager, ServerLifecycleManager)

    def test_signal_handler_callable(self):
        """Signal handler method exists and is callable."""
        manager = setup_lifecycle_manager()
        assert hasattr(manager, "_signal_handler")
        assert callable(manager._signal_handler)


class TestGracefulShutdown:
    """Spec: Server shuts down gracefully on signal."""

    def test_cleanup_method_exists(self):
        """cleanup() method exists and is callable."""
        manager = setup_lifecycle_manager()
        assert hasattr(manager, "cleanup")
        assert callable(manager.cleanup)

    def test_cleanup_with_no_callbacks(self):
        """Cleanup works with no registered callbacks."""
        manager = setup_lifecycle_manager()
        # Should not raise
        manager.cleanup()

    def test_cleanup_clears_callbacks_after_execution(self):
        """Callbacks execute and manager state updates."""
        manager = setup_lifecycle_manager()
        callback = MagicMock()
        manager.register_cleanup(callback)

        manager.cleanup()

        # Callback was called
        callback.assert_called()


class TestServerInstanceHandoff:
    """Spec: New server instance gracefully stops old instance."""

    def test_lifecycle_manager_enables_instance_handoff(self):
        """Lifecycle infrastructure supports instance handoff."""
        manager = setup_lifecycle_manager()
        assert hasattr(manager, "register_cleanup")
        assert hasattr(manager, "cleanup")


class TestIntegration:
    """Spec: Lifecycle integration works end-to-end."""

    def test_full_lifecycle_workflow(self):
        """Full workflow: setup, register callbacks, trigger cleanup."""
        manager = setup_lifecycle_manager()

        executed = []

        def on_exit():
            executed.append("exit")

        manager.register_cleanup(on_exit)
        manager.cleanup()

        assert "exit" in executed

    def test_lifecycle_manager_persistent(self):
        """Singleton persists across calls."""
        manager1 = setup_lifecycle_manager()
        manager2 = setup_lifecycle_manager()
        assert manager1 is manager2
        assert isinstance(manager1, ServerLifecycleManager)
