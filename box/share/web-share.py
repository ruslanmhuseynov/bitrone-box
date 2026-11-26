#!/usr/bin/env python3
"""Bitrone Box — временный веб-доступ к папке для скачивания.

Отдаёт файлы из папки по простому пути (http://IP:PORT/файл). Через заданное
время сам выключается И удаляет восстановленные данные (папку CLEAN).

Использование:  web-share.py <папка> <порт> <секунд> [папка_для_удаления]
"""
import shutil
import sys
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

DIR, PORT, SECS = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
CLEAN = sys.argv[4] if len(sys.argv) > 4 else ""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIR, **k)

    def log_message(self, fmt, *a):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % a))


def main():
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    threading.Timer(SECS, httpd.shutdown).start()
    sys.stderr.write("web-share: 0.0.0.0:%d на %dс, папка %s\n" % (PORT, SECS, DIR))
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        if CLEAN:
            try:
                shutil.rmtree(CLEAN)
                sys.stderr.write("web-share: удалены данные %s\n" % CLEAN)
            except OSError as e:
                sys.stderr.write("web-share: не удалил %s: %s\n" % (CLEAN, e))
        sys.stderr.write("web-share: остановлен\n")


if __name__ == "__main__":
    main()
