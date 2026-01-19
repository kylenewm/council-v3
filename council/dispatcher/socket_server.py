#!/usr/bin/env python3
"""
Unix domain socket server for receiving commands.

Replaces FIFO with a more robust socket-based approach:
- select() works correctly with sockets
- Each connection is independent (no EOF weirdness)
- Can detect if dispatcher is down (connection refused)
- Could add bidirectional responses later

Usage:
    server = SocketServer("/path/to/socket", command_queue)
    server.start()
    # ... server runs in background thread
    server.stop()
"""

import os
import queue
import select
import socket
import threading
import time
from pathlib import Path
from typing import Optional


class SocketServer:
    """Unix domain socket server for receiving commands.

    Thread-safe: runs accept loop in background thread,
    puts commands into a queue that can be consumed by main thread.
    """

    def __init__(
        self,
        socket_path: str,
        command_queue: queue.Queue,
        source_name: str = "socket",
    ):
        """Initialize the socket server.

        Args:
            socket_path: Path for the Unix domain socket
            command_queue: Thread-safe queue for commands (tuples of (source, command))
            source_name: Source identifier for commands in queue (default: "socket")
        """
        self.socket_path = socket_path
        self.command_queue = command_queue
        self.source_name = source_name
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._clients: list[socket.socket] = []
        self._client_buffers: dict[socket.socket, bytes] = {}
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Start the server in a background thread.

        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            return True

        # Remove stale socket file
        socket_file = Path(self.socket_path)
        if socket_file.exists():
            try:
                # Try to connect - if it fails, socket is stale
                test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    test_sock.connect(self.socket_path)
                    test_sock.close()
                    # Connection succeeded - another server is running
                    print(f"[SOCKET] Another server already running at {self.socket_path}")
                    return False
                except (ConnectionRefusedError, FileNotFoundError):
                    # Socket is stale, remove it
                    socket_file.unlink()
            except Exception as e:
                print(f"[SOCKET] Error checking stale socket: {e}")
                try:
                    socket_file.unlink()
                except Exception:
                    pass

        # Create socket directory if needed
        socket_file.parent.mkdir(parents=True, exist_ok=True)

        # Create and bind socket
        try:
            self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(self.socket_path)
            self._server_socket.listen(5)
            self._server_socket.setblocking(False)
        except Exception as e:
            print(f"[SOCKET] Failed to create socket: {e}")
            if self._server_socket:
                self._server_socket.close()
                self._server_socket = None
            return False

        # Start accept loop in background thread
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

        print(f"[SOCKET] Listening on {self.socket_path}")
        return True

    def stop(self):
        """Stop the server and cleanup."""
        self._running = False

        # Close all client connections
        with self._lock:
            for client in self._clients:
                try:
                    client.close()
                except Exception:
                    pass
            self._clients.clear()
            self._client_buffers.clear()

        # Close server socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        # Remove socket file
        try:
            Path(self.socket_path).unlink()
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[SOCKET] Error removing socket file: {e}")

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

        print("[SOCKET] Stopped")

    def _accept_loop(self):
        """Accept connections and read commands.

        Runs in background thread. Uses select() for efficient polling.
        """
        while self._running:
            try:
                # Build list of sockets to watch
                read_list = [self._server_socket]
                with self._lock:
                    read_list.extend(self._clients)

                # Wait for activity (0.5s timeout for shutdown responsiveness)
                try:
                    readable, _, _ = select.select(read_list, [], [], 0.5)
                except (ValueError, OSError):
                    # Socket closed during select
                    if not self._running:
                        break
                    continue

                for sock in readable:
                    if sock is self._server_socket:
                        # Accept new connection
                        self._accept_client()
                    else:
                        # Read from existing client
                        self._read_client(sock)

            except Exception as e:
                if self._running:
                    print(f"[SOCKET] Accept loop error: {e}")
                    time.sleep(0.1)  # Avoid tight loop on persistent errors

    def _accept_client(self):
        """Accept a new client connection."""
        try:
            client, _ = self._server_socket.accept()
            client.setblocking(False)
            with self._lock:
                self._clients.append(client)
                self._client_buffers[client] = b""
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"[SOCKET] Accept error: {e}")

    def _read_client(self, client: socket.socket):
        """Read data from a client and extract complete lines."""
        try:
            data = client.recv(8192)  # 8KB buffer for large commands
            if not data:
                # Client disconnected
                self._remove_client(client)
                return

            with self._lock:
                self._client_buffers[client] += data

                # Extract complete lines
                while b"\n" in self._client_buffers[client]:
                    line, self._client_buffers[client] = self._client_buffers[client].split(b"\n", 1)
                    try:
                        decoded = line.decode("utf-8").strip()
                        if decoded:  # Skip empty lines
                            self.command_queue.put((self.source_name, decoded))
                    except UnicodeDecodeError:
                        pass  # Skip malformed data

        except BlockingIOError:
            pass  # No data available
        except (ConnectionResetError, BrokenPipeError):
            self._remove_client(client)
        except Exception as e:
            print(f"[SOCKET] Read error: {e}")
            self._remove_client(client)

    def _remove_client(self, client: socket.socket):
        """Remove a client and cleanup."""
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)
            if client in self._client_buffers:
                del self._client_buffers[client]
        try:
            client.close()
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def client_count(self) -> int:
        """Get the number of connected clients."""
        with self._lock:
            return len(self._clients)


def send_command(socket_path: str, command: str, timeout: float = 5.0) -> bool:
    """Send a command to the dispatcher via socket.

    Utility function for testing and shell scripts.

    Args:
        socket_path: Path to the Unix domain socket
        command: Command to send (newline will be added)
        timeout: Connection timeout in seconds

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(socket_path)
        sock.sendall((command + "\n").encode("utf-8"))
        sock.close()
        return True
    except Exception as e:
        print(f"[SOCKET] Send error: {e}")
        return False
