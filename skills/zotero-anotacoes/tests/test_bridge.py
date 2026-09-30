"""Transporte da extensão zotobs-bridge, contra um servidor HTTP falso (mesmo contrato)."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import zotero_native as zn  # noqa: E402

TOKEN = "segredo"


def make_handler(seen):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _auth(self):
            if self.headers.get("X-Zotobs-Token") != TOKEN:
                self._send(403, {"error": "token"})
                return False
            return True

        def do_GET(self):
            if self.path == "/zotobs/ping" and self._auth():
                self._send(200, {"ok": True, "version": "0.1.0", "zotero": "10.0.4"})

        def do_POST(self):
            if self.path == "/zotobs/import" and self._auth():
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append(body)
                keys = [i["key"] for i in body["items"]]
                self._send(200, {"criadas": keys[:1], "puladas": keys[1:], "falhas": []})

    return H


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    seen = []
    srv = HTTPServer(("127.0.0.1", 0), make_handler(seen))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(zn, "BRIDGE", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setattr(zn, "TOKEN_FILE", tmp_path / "bridge_token")
    yield seen
    srv.shutdown()


def test_ping_e_import(bridge):
    assert zn.bridge_ping(TOKEN)["version"] == "0.1.0"
    items = [{"key": "AAAAAAAA"}, {"key": "BBBBBBBB"}]
    res = zn.post_bridge(TOKEN, 1, "87BBKH34", items)
    assert res == {"criadas": ["AAAAAAAA"], "puladas": ["BBBBBBBB"], "falhas": []}
    assert bridge[0]["attachment"] == "87BBKH34" and bridge[0]["library"] == 1


def test_token_errado(bridge):
    with pytest.raises(zn.ApiError, match="403"):
        zn.bridge_ping("errado")


def test_extensao_fora_do_ar(monkeypatch):
    monkeypatch.setattr(zn, "BRIDGE", "http://127.0.0.1:9")
    with pytest.raises(zn.ApiError, match="inacessível"):
        zn.bridge_ping(TOKEN)


def test_token_criado_com_modo_600(bridge):
    assert zn.bridge_token() is None
    t = zn.bridge_token(create=True)
    assert len(t) >= 32 and zn.bridge_token() == t
    assert zn.TOKEN_FILE.stat().st_mode & 0o777 == 0o600
