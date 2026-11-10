import socket
import threading
from pathlib import Path

import pytest

from turtlebot3_muse.ipc import IpcError, create_server, decode, dispatch, request


@pytest.fixture
def sock_dir():
    # AF_UNIX paths are limited to ~107 bytes; pytest's tmp_path can be longer.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tbm-") as d:
        yield Path(d)


@pytest.fixture
def serve(sock_dir):
    servers = []

    def _serve(app):
        path = sock_dir / "run" / "bridge.sock"
        server = create_server(path, app)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return path

    yield _serve
    for server in servers:
        server.shutdown()
        server.server_close()


def echo(req):
    return {"echo": req}


def test_roundtrip(serve):
    path = serve(echo)
    assert request(path, {"op": "ping"}, 1.0) == {"ok": True, "result": {"echo": {"op": "ping"}}}


def test_socket_permissions_are_private(serve):
    path = serve(echo)
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_app_exception_becomes_error_response(serve):
    def broken(_req):
        raise ValueError("bad op")

    response = request(serve(broken), {"op": "x"}, 1.0)
    assert response["ok"] is False and "bad op" in response["error"]


@pytest.mark.parametrize("line", [b"", b"{bad", b"[1]"])
def test_dispatch_rejects_invalid_requests(line):
    assert dispatch(echo, line)["ok"] is False


def test_decode_rejects_non_object():
    with pytest.raises(IpcError):
        decode(b"[1, 2]")


def test_stale_socket_is_replaced(sock_dir):
    path = sock_dir / "stale.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(path))
    s.close()  # socket file remains but nobody listens
    server = create_server(path, echo)
    server.server_close()


def test_refuses_to_steal_live_socket(serve):
    path = serve(echo)
    with pytest.raises(IpcError, match="already listening"):
        create_server(path, echo)


def test_refuses_non_socket_file(sock_dir):
    path = sock_dir / "file.sock"
    path.write_text("x")
    with pytest.raises(IpcError, match="not a socket"):
        create_server(path, echo)


def test_request_times_out_on_silent_server(sock_dir):
    path = sock_dir / "silent.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        listener.listen(1)
        with pytest.raises(TimeoutError):
            request(path, {"op": "ping"}, 0.2)


def test_request_missing_socket_raises_oserror(sock_dir):
    with pytest.raises(OSError):
        request(sock_dir / "missing.sock", {"op": "ping"}, 0.2)
