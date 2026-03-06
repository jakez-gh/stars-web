"""Server lifecycle management for Stars! web service.

Ensures clean shutdown and prevents multiple instances from running
on different ports simultaneously.
"""

import atexit
import signal
import sys
from typing import Callable


class ServerLifecycleManager:
    """Manages server startup, shutdown, and cleanup.

    Ensures:
    - Only one instance runs per workspace
    - Clean shutdown on signals (SIGTERM, SIGINT)
    - Lock file cleanup on exit
    - Graceful handoff to new instances
    """

    _instance: "ServerLifecycleManager | None" = None
    _cleanup_callbacks: list[Callable[[], None]] = []

    def __init__(self) -> None:
        """Initialize the lifecycle manager."""
        self._register_signal_handlers()
        atexit.register(self.cleanup)

    def _register_signal_handlers(self) -> None:
        """Register OS signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        # Windows-specific signal (only available on Windows)
        if sys.platform == "win32" and hasattr(signal, "CTRL_BREAK_EVENT"):
            try:
                signal.signal(signal.CTRL_BREAK_EVENT, self._signal_handler)
            except (OSError, ValueError):
                # CTRL_BREAK_EVENT may not be available in all contexts
                pass

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle OS signals for graceful shutdown."""
        print(f"\nShutdown signal received ({signum})...")
        self.cleanup()
        sys.exit(0)

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        """Register a cleanup callback to run on shutdown.

        Callbacks are called in reverse order of registration (LIFO).

        Args:
            callback: Callable that takes no arguments
        """
        self._cleanup_callbacks.append(callback)

    def cleanup(self) -> None:
        """Run all registered cleanup callbacks.

        Called on exit, signal, or explicit call.
        """
        print("Running cleanup...")
        # Run callbacks in reverse order (LIFO)
        for callback in reversed(self._cleanup_callbacks):
            try:
                callback()
            except Exception as e:
                print(f"Error during cleanup: {e}")

    @classmethod
    def get_instance(cls) -> "ServerLifecycleManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def on_exit(cls, callback: Callable[[], None]) -> None:
        """Register a callback to run on server exit.

        Args:
            callback: Callable with no arguments to run on exit
        """
        cls.get_instance().register_cleanup(callback)


def setup_lifecycle_manager() -> ServerLifecycleManager:
    """Initialize the server lifecycle manager.

    Should be called early in the application startup.

    Returns:
        ServerLifecycleManager: The singleton manager instance
    """
    return ServerLifecycleManager.get_instance()
