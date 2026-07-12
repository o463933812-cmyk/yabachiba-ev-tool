from __future__ import annotations

import hashlib
import html
import os
import secrets
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("YABACHIBA_HOST", "127.0.0.1")
PORT = int(os.environ.get("YABACHIBA_PORT") or os.environ.get("PORT") or "8790")
APP_PASSWORD = os.environ.get("YABACHIBA_PASSWORD", "").strip()
AUTH_COOKIE_NAME = "yabachiba_auth"
AUTH_COOKIE_VALUE = secrets.token_urlsafe(32)
AUTH_COOKIE = f"{AUTH_COOKIE_NAME}={AUTH_COOKIE_VALUE}"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30
APP_VERSION = "2026-07-12-ten-cherry-latest-model-v1"
INDEX_GZ = "yabachiba_tool_index.html.gz"
INDEX_SIZE = 9522347
INDEX_SHA256 = "e8c5f1dde9140c75171035fd3939cac8a99c2c2212321f2d50e7948565b064ea"
_cached_index: bytes | None = None


def load_index() -> bytes:
    global _cached_index
    if _cached_index is not None:
        return _cached_index
    data = (ROOT / INDEX_GZ).read_bytes()
    if len(data) != INDEX_SIZE:
        raise RuntimeError(f"index size mismatch: {len(data)} != {INDEX_SIZE}")
    actual = hashlib.sha256(data).hexdigest()
    if actual != INDEX_SHA256:
        raise RuntimeError(f"index sha mismatch: {actual}")
    _cached_index = data
    return data


def page(title: str, body: str, status: HTTPStatus = HTTPStatus.OK):
    data = f"""<!doctype html><html lang=ja><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><body style="font-family:system-ui,sans-serif;max-width:560px;margin:40px auto;line-height:1.7">{body}</body></html>""".encode("utf-8")
    return status, [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(data)))], data


class Handler(BaseHTTPRequestHandler):
    server_version = "YabachibaEV/1.0"

    def log_message(self, fmt, *args):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.client_address[0]} {fmt % args}")

    def authed(self) -> bool:
        if not APP_PASSWORD:
            return True
        return f"{AUTH_COOKIE_NAME}={AUTH_COOKIE_VALUE}" in (self.headers.get("Cookie") or "")

    def send_blob(self, status: HTTPStatus, headers: list[tuple[str, str]], body: bytes, head_only: bool = False):
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def redirect(self, location: str):
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def login_page(self, message: str = ""):
        title = "L\u30e4\u30d0\u30c1\u30d0 \u671f\u5f85\u5024\u30c4\u30fc\u30eb \u30ed\u30b0\u30a4\u30f3"
        heading = "L\u30e4\u30d0\u30c1\u30d0 \u671f\u5f85\u5024\u30c4\u30fc\u30eb"
        password_label = "\u30d1\u30b9\u30ef\u30fc\u30c9"
        login_label = "\u30ed\u30b0\u30a4\u30f3"
        msg = f"<p style='color:#b00020'>{html.escape(message)}</p>" if message else ""
        return page(title, f"""
<h1>{heading}</h1>
{msg}
<div style="border:1px solid #ff3d55;background:#fff1f2;color:#a40018;font-size:13px;line-height:1.5;font-weight:800;padding:8px;margin:0 0 10px">本ツールは購入者限定です。無断転載・コピー・再配布（URL・パスワード共有、画面内容・算出結果の共有を含む）は禁止しています。発見した場合は、販売停止・法的措置を含む対応を行う場合があります。</div>
<form method=post action=/login>
  <label>{password_label}<br><input name=password type=password autofocus style="font-size:18px;padding:8px;width:100%"></label>
  <button style="margin-top:16px;font-size:18px;padding:8px 16px">{login_label}</button>
</form>
""")

    def serve_index(self, head_only: bool = False):
        body = load_index()
        self.send_blob(HTTPStatus.OK, [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Encoding", "gzip"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store, max-age=0, must-revalidate"),
            ("X-App-Version", APP_VERSION),
        ], body, head_only=head_only)

    def do_HEAD(self):
        path = urlsplit(self.path).path or "/"
        if path in ("/", "/index.html"):
            if not self.authed():
                status, headers, body = self.login_page()
                self.send_blob(status, headers, body, head_only=True)
            else:
                self.serve_index(head_only=True)
        elif path == "/healthz":
            self.send_blob(HTTPStatus.OK, [("Content-Type", "text/plain"), ("Content-Length", "2")], b"ok", head_only=True)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self):
        path = urlsplit(self.path).path or "/"
        if path == "/healthz":
            self.send_blob(HTTPStatus.OK, [("Content-Type", "text/plain"), ("Content-Length", "2")], b"ok")
            return
        if path == "/login":
            if self.authed():
                self.redirect("/")
            else:
                status, headers, body = self.login_page()
                self.send_blob(status, headers, body)
            return
        if path not in ("/", "/index.html"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.authed():
            status, headers, body = self.login_page()
            self.send_blob(status, headers, body)
            return
        self.serve_index()

    def do_POST(self):
        path = urlsplit(self.path).path or "/"
        if path != "/login":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length") or "0")
        params = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        if (params.get("password") or [""])[0] != APP_PASSWORD:
            status, headers, body = self.login_page("\u30d1\u30b9\u30ef\u30fc\u30c9\u304c\u9055\u3044\u307e\u3059\u3002")
            self.send_blob(status, headers, body)
            return
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"{AUTH_COOKIE}; Path=/; HttpOnly; SameSite=Lax; Max-Age={COOKIE_MAX_AGE}")
        self.end_headers()


def main():
    load_index()
    print(f"Yabachiba EV tool server {APP_VERSION} serving on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
