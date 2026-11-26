#!/usr/bin/env python3
"""Bitrone Box — приёмник health.json от серверов клиента.

Сервер (collect-health.ps1) шлёт сюда PUT /health/<Имя> с телом-JSON и заголовком
Authorization: Bearer <token>. Файл атомарно пишется в HEALTH_ROOT/<Имя>.json —
ровно туда, где его читает витрина (bitrone_box_status.load_health).

Только stdlib. Конфиг — /etc/bitrone-box/box.conf (HEALTH_ROOT, HEALTH_TOKEN, HEALTH_PORT).
"""
import hmac
import json
import os
import re
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG = "/etc/bitrone-box/box.conf"
DEFAULTS = {"HEALTH_ROOT": "/srv/bitrone/health", "HEALTH_PORT": "8080", "HEALTH_TOKEN": ""}
MAX_BODY = 1 << 20  # 1 МБ
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def load_config(path):
    cfg = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return cfg


CFG = load_config(CONFIG)
ROOT = CFG["HEALTH_ROOT"]
TOKEN = CFG.get("HEALTH_TOKEN", "")


def authorized(headers):
    if not TOKEN:
        return False  # не настроен токен → ничего не принимаем
    got = headers.get("Authorization", "")
    if not got.startswith("Bearer "):
        return False
    return hmac.compare_digest(got[7:].strip(), TOKEN)


class Handler(BaseHTTPRequestHandler):
    server_version = "BitroneHealth/1.0"

    def _send(self, code, msg=""):
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def _handle(self):
        m = re.match(r"^/health/([^/]+)$", self.path)
        if not m:
            return self._send(404, "not found")
        name = m.group(1)
        if not NAME_RE.match(name):
            return self._send(400, "bad name")
        if not authorized(self.headers):
            return self._send(401, "unauthorized")
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send(400, "bad length")
        if length <= 0 or length > MAX_BODY:
            return self._send(400, "bad length")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            return self._send(400, "bad json")
        try:
            os.makedirs(ROOT, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=ROOT, suffix=".tmp")
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            os.chmod(tmp, 0o644)  # витрина работает под другим пользователем — нужно чтение
            os.replace(tmp, os.path.join(ROOT, name + ".json"))
        except OSError as e:
            sys.stderr.write("write error: %s\n" % e)
            return self._send(500, "write error")
        self._send(204)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    if not TOKEN:
        sys.stderr.write("HEALTH_TOKEN не задан в %s — приёмник откажет всем\n" % CONFIG)
    port = int(CFG.get("HEALTH_PORT", "8080"))
    os.makedirs(ROOT, exist_ok=True)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write("Bitrone health receiver: 0.0.0.0:%d → %s\n" % (port, ROOT))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
