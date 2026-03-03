"""Unit tests for run.py server management: kill_port().

TDD cycle: these tests were written RED (kill_port didn't exist),
then run.py was updated to make them GREEN.
"""

import socket
import subprocess
import sys
import time


from stars_web.run import kill_port

# Use an ephemeral port unlikely to collide with anything real.
_TEST_PORT = 15432


def _is_port_free(port: int) -> bool:
    """Return True if nothing is listening on port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _start_dummy_listener(port: int) -> subprocess.Popen:
    """Spawn a subprocess that holds a TCP listen socket on *port*."""
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import socket, time; s=socket.socket(); "
                "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); "
                f"s.bind(('127.0.0.1', {port})); s.listen(1); time.sleep(60)"
            ),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class TestKillPort:
    """kill_port(port) must evict any listener and free the port."""

    def test_returns_false_when_nothing_listening(self):
        """Returns False if no process is listening — safe no-op."""
        assert _is_port_free(_TEST_PORT), "Pre-condition: test port must be free"
        assert kill_port(_TEST_PORT) is False

    def test_returns_true_when_process_listening(self):
        """Returns True after successfully killing a listening process."""
        proc = _start_dummy_listener(_TEST_PORT)
        time.sleep(0.4)
        try:
            result = kill_port(_TEST_PORT)
            assert result is True
        finally:
            proc.kill()
            proc.wait()

    def test_port_free_after_kill(self):
        """Port is actually bindable again after kill_port()."""
        proc = _start_dummy_listener(_TEST_PORT)
        time.sleep(0.4)
        try:
            kill_port(_TEST_PORT)
            time.sleep(0.4)
            assert _is_port_free(_TEST_PORT), "Port must be free after kill_port()"
        finally:
            proc.kill()
            proc.wait()

    def test_idempotent_second_call(self):
        """Calling kill_port twice in a row on a free port returns False both times."""
        assert _is_port_free(_TEST_PORT)
        assert kill_port(_TEST_PORT) is False
        assert kill_port(_TEST_PORT) is False
