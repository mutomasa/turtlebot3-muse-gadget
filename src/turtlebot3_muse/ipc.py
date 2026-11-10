"""Newline-delimited JSON request/response over a Unix domain socket.

Request:  {"op": "<name>", ...}\\n
Response: {"ok": true, "result": {...}}\\n  or  {"ok": false, "error": "..."}\\n
"""

from __future__ import annotations

import json
import os
import socket
import socketserver
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAX_MESSAGE_BYTES = 1 << 20
SOCKET_FILE_MODE_UMASK = 0o177  # socket created as 0600
PROBE_TIMEOUT_S = 0.5

App = Callable[[dict[str, Any]], dict[str, Any]]


class IpcError(RuntimeError):
    """Protocol or socket setup failure."""


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"


def decode(line: bytes) -> dict[str, Any]:
    if not line.strip():
        raise IpcError("empty message")
    try:
        message = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise IpcError(f"invalid JSON: {exc}") from exc
    if not isinstance(message, dict):
        raise IpcError("message must be a JSON object")
    return message


def dispatch(app: App, line: bytes) -> dict[str, Any]:
    """Run ``app`` on a raw request line and wrap the outcome in the response envelope."""
    try:
        return {"ok": True, "result": app(decode(line))}
    except Exception as exc:  # noqa: BLE001 - every failure becomes an error response
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline(MAX_MESSAGE_BYTES)
        self.wfile.write(encode(dispatch(self.server.app, line)))


class UnixJsonServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, path: Path, app: App) -> None:
        self.app = app
        super().__init__(str(path), _Handler)


def _is_live(path: Path) -> bool:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(PROBE_TIMEOUT_S)
        try:
            probe.connect(str(path))
        except OSError:
            return False
    return True


def _remove_stale_socket(path: Path) -> None:
    if not path.exists():
        return
    if not stat.S_ISSOCK(path.stat().st_mode):
        raise IpcError(f"{path} exists and is not a socket")
    if _is_live(path):
        raise IpcError(f"another server is already listening on {path}")
    path.unlink()


def create_server(path: Path, app: App) -> UnixJsonServer:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _remove_stale_socket(path)
    old_umask = os.umask(SOCKET_FILE_MODE_UMASK)
    try:
        return UnixJsonServer(path, app)
    finally:
        os.umask(old_umask)


def _read_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if chunk.endswith(b"\n") or total > MAX_MESSAGE_BYTES:
            break
    return b"".join(chunks)


def request(path: Path, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """Send one request and return the response envelope. Raises OSError / IpcError."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        sock.connect(str(path))
        sock.sendall(encode(payload))
        return decode(_read_line(sock))
