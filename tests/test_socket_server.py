"""
Comprehensive tests for the Unix domain socket server.

Test requirements from plan (20+ iterations):
1. Single command received
2. 100 rapid commands, all received in order
3. 5 concurrent clients, all commands received
4. Client disconnect doesn't crash server
5. Large command (8KB) received correctly
6. Server stop/start works cleanly
7. Stale socket file removed on start
"""

import os
import queue
import socket
import tempfile
import threading
import time
import pytest

from council.dispatcher.socket_server import SocketServer, send_command


@pytest.fixture
def temp_socket_path():
    """Create a temporary path for a Unix socket."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test.sock")


@pytest.fixture
def command_queue():
    """Create a command queue for testing."""
    return queue.Queue()


@pytest.fixture
def socket_server(temp_socket_path, command_queue):
    """Create and start a socket server, cleanup on teardown."""
    server = SocketServer(temp_socket_path, command_queue)
    yield server
    server.stop()


class TestSocketServerBasic:
    """Basic functionality tests."""

    def test_start_and_stop(self, temp_socket_path, command_queue):
        """Test that server starts and stops cleanly."""
        server = SocketServer(temp_socket_path, command_queue)

        assert server.start()
        assert server.is_running
        assert os.path.exists(temp_socket_path)

        server.stop()
        assert not server.is_running
        assert not os.path.exists(temp_socket_path)

    def test_double_start(self, socket_server, temp_socket_path):
        """Test that starting twice returns True (idempotent)."""
        assert socket_server.start()
        assert socket_server.start()  # Should return True, already running
        assert socket_server.is_running

    def test_socket_file_created(self, socket_server, temp_socket_path):
        """Test that socket file is created on start."""
        assert socket_server.start()
        assert os.path.exists(temp_socket_path)

    def test_socket_file_removed_on_stop(self, socket_server, temp_socket_path):
        """Test that socket file is removed on stop."""
        assert socket_server.start()
        socket_server.stop()
        assert not os.path.exists(temp_socket_path)


class TestSocketServerSingleCommand:
    """Single command tests."""

    def test_single_command_received(self, socket_server, temp_socket_path, command_queue):
        """Test receiving a single command."""
        assert socket_server.start()

        # Send a command
        assert send_command(temp_socket_path, "1: hello world")

        # Wait for command to be processed
        time.sleep(0.1)

        # Check queue
        assert not command_queue.empty()
        source, cmd = command_queue.get_nowait()
        assert source == "socket"
        assert cmd == "1: hello world"

    def test_single_command_via_raw_socket(self, socket_server, temp_socket_path, command_queue):
        """Test receiving a command via raw socket connection."""
        assert socket_server.start()

        # Connect and send directly
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall(b"status\n")
        sock.close()

        time.sleep(0.1)

        source, cmd = command_queue.get_nowait()
        assert cmd == "status"


class TestSocketServerMultipleCommands:
    """Tests for multiple commands."""

    def test_100_rapid_commands_ordered(self, socket_server, temp_socket_path, command_queue):
        """Test that 100 rapid commands are all received in order."""
        assert socket_server.start()
        num_commands = 100

        # Send commands rapidly via single connection
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        for i in range(num_commands):
            sock.sendall(f"cmd{i}\n".encode())
        sock.close()

        # Wait for all to be processed
        time.sleep(0.5)

        # Verify all received in order
        received = []
        while not command_queue.empty():
            _, cmd = command_queue.get_nowait()
            received.append(cmd)

        assert len(received) == num_commands
        for i, cmd in enumerate(received):
            assert cmd == f"cmd{i}", f"Command {i} was '{cmd}', expected 'cmd{i}'"

    def test_multiple_lines_single_send(self, socket_server, temp_socket_path, command_queue):
        """Test multiple lines sent in a single send."""
        assert socket_server.start()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall(b"line1\nline2\nline3\n")
        sock.close()

        time.sleep(0.1)

        received = []
        while not command_queue.empty():
            _, cmd = command_queue.get_nowait()
            received.append(cmd)

        assert received == ["line1", "line2", "line3"]


class TestSocketServerConcurrentClients:
    """Tests for concurrent client connections."""

    def test_5_concurrent_clients(self, socket_server, temp_socket_path, command_queue):
        """Test 5 concurrent clients, all commands received."""
        assert socket_server.start()
        num_clients = 5
        commands_per_client = 20
        expected_total = num_clients * commands_per_client

        def client_thread(client_id):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(temp_socket_path)
            for i in range(commands_per_client):
                sock.sendall(f"c{client_id}-{i}\n".encode())
                time.sleep(0.01)  # Small delay to interleave
            sock.close()

        # Start all clients
        threads = []
        for i in range(num_clients):
            t = threading.Thread(target=client_thread, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all clients to finish
        for t in threads:
            t.join(timeout=5.0)

        # Wait for processing
        time.sleep(0.5)

        # Verify all received
        received = []
        while not command_queue.empty():
            _, cmd = command_queue.get_nowait()
            received.append(cmd)

        assert len(received) == expected_total

        # Verify each client's commands were all received
        client_counts = {i: 0 for i in range(num_clients)}
        for cmd in received:
            client_id = int(cmd.split("-")[0][1:])
            client_counts[client_id] += 1

        for client_id, count in client_counts.items():
            assert count == commands_per_client, f"Client {client_id} sent {count}, expected {commands_per_client}"

    def test_client_count_tracking(self, socket_server, temp_socket_path, command_queue):
        """Test that client count is tracked correctly."""
        assert socket_server.start()
        assert socket_server.client_count == 0

        # Connect a client
        sock1 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock1.connect(temp_socket_path)
        time.sleep(0.2)  # Wait for accept
        assert socket_server.client_count == 1

        # Connect another
        sock2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock2.connect(temp_socket_path)
        time.sleep(0.2)
        assert socket_server.client_count == 2

        # Disconnect one
        sock1.close()
        time.sleep(0.2)
        assert socket_server.client_count == 1

        sock2.close()
        time.sleep(0.2)
        assert socket_server.client_count == 0


class TestSocketServerClientDisconnect:
    """Tests for client disconnect handling."""

    def test_client_disconnect_doesnt_crash(self, socket_server, temp_socket_path, command_queue):
        """Test that client disconnecting doesn't crash the server."""
        assert socket_server.start()
        time.sleep(0.1)  # Give server time to fully start accepting

        # Connect and immediately disconnect
        for _ in range(10):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(temp_socket_path)
            sock.close()
            time.sleep(0.02)  # Small delay between rapid connections

        time.sleep(0.5)

        # Server should still be running
        assert socket_server.is_running

        # Should still accept new connections
        assert send_command(temp_socket_path, "test after disconnect")
        time.sleep(0.1)
        _, cmd = command_queue.get_nowait()
        assert cmd == "test after disconnect"

    def test_client_disconnect_mid_partial_line(self, socket_server, temp_socket_path, command_queue):
        """Test client disconnecting mid-command (no newline)."""
        assert socket_server.start()

        # Send partial line then disconnect
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall(b"partial without newline")
        sock.close()

        time.sleep(0.2)

        # Server should still be running
        assert socket_server.is_running

        # Partial command should NOT be in queue (no newline = incomplete)
        assert command_queue.empty()

    def test_graceful_disconnect_after_command(self, socket_server, temp_socket_path, command_queue):
        """Test client sending command then disconnecting gracefully."""
        assert socket_server.start()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall(b"complete command\n")
        sock.close()

        time.sleep(0.1)

        _, cmd = command_queue.get_nowait()
        assert cmd == "complete command"


class TestSocketServerLargeCommands:
    """Tests for large command handling."""

    def test_large_command_8kb(self, socket_server, temp_socket_path, command_queue):
        """Test receiving a large command (8KB)."""
        assert socket_server.start()
        large_content = "x" * 8192  # 8KB

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall((large_content + "\n").encode())
        sock.close()

        time.sleep(0.2)

        _, cmd = command_queue.get_nowait()
        assert cmd == large_content
        assert len(cmd) == 8192

    def test_very_large_command_16kb(self, socket_server, temp_socket_path, command_queue):
        """Test receiving a very large command (16KB)."""
        assert socket_server.start()
        large_content = "y" * 16384  # 16KB

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall((large_content + "\n").encode())
        sock.close()

        time.sleep(0.3)

        _, cmd = command_queue.get_nowait()
        assert cmd == large_content


class TestSocketServerRestart:
    """Tests for server stop/start."""

    def test_server_restart(self, temp_socket_path, command_queue):
        """Test that server can be stopped and restarted."""
        server = SocketServer(temp_socket_path, command_queue)

        # First start
        assert server.start()
        assert send_command(temp_socket_path, "before restart")
        time.sleep(0.1)
        _, cmd1 = command_queue.get_nowait()
        assert cmd1 == "before restart"

        # Stop
        server.stop()
        assert not server.is_running

        # Start again
        assert server.start()
        assert send_command(temp_socket_path, "after restart")
        time.sleep(0.1)
        _, cmd2 = command_queue.get_nowait()
        assert cmd2 == "after restart"

        server.stop()

    def test_stale_socket_removed(self, temp_socket_path, command_queue):
        """Test that stale socket file is removed on start."""
        # Create a stale socket file (not a real socket, just a file)
        os.makedirs(os.path.dirname(temp_socket_path), exist_ok=True)
        with open(temp_socket_path, 'w') as f:
            f.write("stale")

        server = SocketServer(temp_socket_path, command_queue)
        # Should succeed by removing the stale file
        assert server.start()
        assert server.is_running

        server.stop()


class TestSocketServerEdgeCases:
    """Edge case tests."""

    def test_empty_lines_skipped(self, socket_server, temp_socket_path, command_queue):
        """Test that empty lines are skipped."""
        assert socket_server.start()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall(b"\n\nactual\n\n\n")
        sock.close()

        time.sleep(0.1)

        received = []
        while not command_queue.empty():
            _, cmd = command_queue.get_nowait()
            received.append(cmd)

        assert received == ["actual"]

    def test_whitespace_stripped(self, socket_server, temp_socket_path, command_queue):
        """Test that whitespace is stripped from commands."""
        assert socket_server.start()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall(b"  spaces  \n\ttabs\t\n")
        sock.close()

        time.sleep(0.1)

        received = []
        while not command_queue.empty():
            _, cmd = command_queue.get_nowait()
            received.append(cmd)

        assert received == ["spaces", "tabs"]

    def test_unicode_commands(self, socket_server, temp_socket_path, command_queue):
        """Test handling of unicode commands."""
        assert socket_server.start()

        # Test with actual unicode characters
        unicode_cmd = "1: hello \u4e16\u754c"  # "hello world" in Chinese
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)
        sock.sendall((unicode_cmd + "\n").encode("utf-8"))
        sock.close()

        time.sleep(0.1)

        _, cmd = command_queue.get_nowait()
        assert cmd == unicode_cmd

    def test_custom_source_name(self, temp_socket_path, command_queue):
        """Test custom source name in queue."""
        server = SocketServer(temp_socket_path, command_queue, source_name="voice")
        assert server.start()

        send_command(temp_socket_path, "test")
        time.sleep(0.1)

        source, _ = command_queue.get_nowait()
        assert source == "voice"

        server.stop()


class TestSocketServerStress:
    """Stress tests."""

    def test_rapid_connect_disconnect(self, socket_server, temp_socket_path, command_queue):
        """Test rapid connect/disconnect cycles."""
        assert socket_server.start()

        def connect_disconnect(n):
            for _ in range(n):
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    sock.connect(temp_socket_path)
                    sock.sendall(b"ping\n")
                    sock.close()
                except Exception:
                    pass
                time.sleep(0.01)

        # 10 threads, 10 connections each
        threads = []
        for _ in range(10):
            t = threading.Thread(target=connect_disconnect, args=(10,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10.0)

        time.sleep(0.5)

        # Server should still be running
        assert socket_server.is_running

        # Should have received many pings
        received_count = 0
        while not command_queue.empty():
            command_queue.get_nowait()
            received_count += 1

        # At least some should have gotten through
        assert received_count > 50  # Expect most of 100 to succeed

    def test_sustained_load(self, socket_server, temp_socket_path, command_queue):
        """Test sustained load over time."""
        assert socket_server.start()

        stop_flag = threading.Event()
        sent_count = [0]

        def sender():
            while not stop_flag.is_set():
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    sock.connect(temp_socket_path)
                    for _ in range(5):
                        sock.sendall(b"load\n")
                        sent_count[0] += 1
                    sock.close()
                except Exception:
                    pass
                time.sleep(0.05)

        # 3 senders for 2 seconds
        threads = []
        for _ in range(3):
            t = threading.Thread(target=sender)
            threads.append(t)
            t.start()

        time.sleep(2.0)
        stop_flag.set()

        for t in threads:
            t.join(timeout=2.0)

        time.sleep(0.5)

        # Count received
        received_count = 0
        while not command_queue.empty():
            command_queue.get_nowait()
            received_count += 1

        # Should have received most of what was sent
        assert received_count >= sent_count[0] * 0.9, f"Received {received_count} of {sent_count[0]} sent"


class TestSendCommandHelper:
    """Tests for the send_command helper function."""

    def test_send_command_success(self, socket_server, temp_socket_path, command_queue):
        """Test send_command returns True on success."""
        assert socket_server.start()
        assert send_command(temp_socket_path, "test")

    def test_send_command_no_server(self, temp_socket_path):
        """Test send_command returns False when no server."""
        assert not send_command(temp_socket_path, "test", timeout=0.5)

    def test_send_command_adds_newline(self, socket_server, temp_socket_path, command_queue):
        """Test send_command adds newline to command."""
        assert socket_server.start()
        assert send_command(temp_socket_path, "no newline")
        time.sleep(0.1)

        _, cmd = command_queue.get_nowait()
        assert cmd == "no newline"  # Received correctly, newline was added


class TestSocketServerPartialReads:
    """Tests for partial read handling."""

    def test_partial_line_buffered(self, socket_server, temp_socket_path, command_queue):
        """Test that partial lines are buffered until complete."""
        assert socket_server.start()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)

        # Send partial line
        sock.sendall(b"partial")
        time.sleep(0.2)

        # Should not be in queue yet
        assert command_queue.empty()

        # Complete the line
        sock.sendall(b" complete\n")
        time.sleep(0.1)

        _, cmd = command_queue.get_nowait()
        assert cmd == "partial complete"

        sock.close()

    def test_mixed_complete_and_partial(self, socket_server, temp_socket_path, command_queue):
        """Test mix of complete and partial lines."""
        assert socket_server.start()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(temp_socket_path)

        # Complete + partial
        sock.sendall(b"complete1\ncomplete2\npart")
        time.sleep(0.2)

        # Should have first two
        received = []
        while not command_queue.empty():
            _, cmd = command_queue.get_nowait()
            received.append(cmd)
        assert received == ["complete1", "complete2"]

        # Complete the partial
        sock.sendall(b"ial3\n")
        time.sleep(0.1)

        _, cmd = command_queue.get_nowait()
        assert cmd == "partial3"

        sock.close()
