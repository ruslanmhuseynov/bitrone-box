#!/usr/bin/env python3
"""Bitrone Box: служба статуса для экрана и полосы на подставке.

Смотрит в папку хранилищ restic (rest-server) и раз в N секунд отправляет
на плату RP2040 по USB строку JSON (см. box/firmware/main.py).

Ключ шифрования не нужен: каждая копия restic — новый файл в <repo>/snapshots/,
время последней копии = время самого свежего файла там.
Раскладка хранилищ в REPO_ROOT (по имени папки):
  full*      — еженедельные полные копии
  остальные  — ежечасные копии изменений
Идёт запись (в <repo>/locks/ есть файлы) → состояние busy.

Только стандартная библиотека Python 3.8+.
"""
import argparse
import glob
import json
import os
import select
import shutil
import sys
try:
    import termios
except ImportError:      # Windows — только для тестов, на коробке Linux
    termios = None
import time
from datetime import datetime

DEFAULTS = {
    "REPO_ROOT": "/srv/restic",
    "SERIAL": "auto",
    "SN": "BX-0001",
    "CLIENT": "",
    "SOURCE": "",              # что копируется у клиента, напр. D:\1C\Buh — только для показа
    "LANG": "az",              # az | en
    "WARN_HOURS": "2",         # нет копии изменений дольше — warn
    "FULL_WARN_DAYS": "8",     # нет полной копии дольше — warn
    "DISK_WARN_PCT": "85",
    "INTERVAL": "10",
    "STATE_DIR": "/var/lib/bitrone-box",
    "STATUS_JSON": "/run/bitrone-box/status.json",
    "SMART_DEVICE": "",        # напр. /dev/sda; пусто — не проверять
    "CONTRAST": "90",
    "HEALTH_ROOT": "/srv/bitrone/health",  # папка с <server>.json «жизнедеятельности»
    "SAFE_TOP_PCT": "5",   # безопасный отступ сверху/снизу под overscan монитора (%)
    "SAFE_SIDE_PCT": "3",  # безопасный отступ по бокам (%)
}

TEXT = {
    "az": {
        "min": "dəq", "hour": "saat", "day": "gün", "now": "indi",
        "last": "Son nüsxə", "full": "Tam", "none": "yoxdur", "never": "Nüsxə yoxdur",
        "no_backup": "Nüsxə gəlmir", "notified": "Bitrone xəbərdar",
        "busy": "Nüsxə gəlir...", "disk": "Disk", "free": "boş", "smart_ok": "Sağlamlıq: OK",
        "smart_bad": "DİSK XƏTASI!", "folder": "Qovluq:", "client": "Müştəri:",
        "full_old": "Tam nüsxə köhnə",
        "days": ["B.e.", "Ç.a.", "Çər.", "C.a.", "Cümə", "Şənbə", "Bazar"],
    },
    "en": {
        "min": "min", "hour": "h", "day": "d", "now": "now",
        "last": "Last", "full": "Full", "none": "none", "never": "No backups",
        "no_backup": "No new backups", "notified": "Bitrone notified",
        "busy": "Receiving...", "disk": "Disk", "free": "free", "smart_ok": "Health: OK",
        "smart_bad": "DISK FAILING!", "folder": "Folder:", "client": "Client:",
        "full_old": "Full backup old",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },
}


def load_config(path):
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in DEFAULTS:
        if os.environ.get("BOX_" + k):
            cfg[k] = os.environ["BOX_" + k]
    return cfg


# ---------- чтение «жизнедеятельности» серверов ----------

def load_health(root):
    """Читает health.json по каждому серверу из HEALTH_ROOT.

    Возвращает список словарей (по одному на сервер), отсортированный по имени.
    Файл кладёт collect-health.* на сервере (или через Wazuh). Коробке важны
    только значения — она ничего не исполняет. Битый/отсутствующий файл пропускаем.
    """
    out = []
    if not root or not os.path.isdir(root):
        return out
    for path in sorted(glob.glob(os.path.join(root, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                d.setdefault("name", os.path.splitext(os.path.basename(path))[0])
                out.append(d)
        except Exception as e:
            print("health %s: %s" % (path, e), file=sys.stderr, flush=True)
    out.sort(key=lambda d: d.get("name", ""))
    return out


# ---------- чтение хранилищ ----------

def find_repos(root):
    """Папки restic-хранилищ (есть файл config и папка snapshots) на глубине до 3."""
    repos = []
    for depth in range(0, 4):
        pattern = os.path.join(root, *(["*"] * depth))
        for d in glob.glob(pattern):
            if os.path.isdir(os.path.join(d, "snapshots")) and os.path.isfile(os.path.join(d, "config")):
                repos.append(d)
    return sorted(set(repos))


def repo_kind(path, root):
    name = os.path.relpath(path, root).replace("\\", "/").lower()
    last = name.rsplit("/", 1)[-1]
    if last.startswith("full"):
        return "full"
    return "main"


def newest_mtime(d):
    best = None
    try:
        with os.scandir(d) as it:
            for e in it:
                if e.is_file():
                    m = e.stat().st_mtime
                    best = m if best is None or m > best else best
    except FileNotFoundError:
        pass
    return best


def has_files(d):
    try:
        with os.scandir(d) as it:
            return any(e.is_file() for e in it)
    except FileNotFoundError:
        return False


def scan(root):
    out = {"main": None, "full": None, "busy": False, "repos": 0}
    for r in find_repos(root):
        out["repos"] += 1
        kind = repo_kind(r, root)
        m = newest_mtime(os.path.join(r, "snapshots"))
        if m and (out[kind] is None or m > out[kind]):
            out[kind] = m
        if has_files(os.path.join(r, "locks")):
            out["busy"] = True
    return out


def smart_ok(device, state_dir):
    """Итог SMART из файла, который раз в час пишет root-таймер bitrone-box-smart
    (smartctl требует прав root, а служба экрана работает без них)."""
    if not device:
        return None
    path = os.path.join(state_dir, "smart.txt")
    try:
        if time.time() - os.path.getmtime(path) > 3 * 3600:
            return None
        with open(path, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError:
        return None
    if "FAILED" in txt:
        return False
    if "PASSED" in txt or ": OK" in txt:
        return True
    return None


# ---------- форматирование ----------

def ago(sec, t):
    if sec < 60:
        return t["now"]
    if sec < 3600:
        return "%d %s" % (sec // 60, t["min"])
    if sec < 86400:
        s = "%d %s" % (sec // 3600, t["hour"])
    else:
        s = "%d %s" % (sec // 86400, t["day"])
    return s if len(s) <= 6 else s.replace(" ", "")


def when(ts, now, t):
    d = datetime.fromtimestamp(ts)
    if now - ts < 6 * 86400:
        if d.date() == datetime.fromtimestamp(now).date():
            return d.strftime("%H:%M")
        return "%s %s" % (t["days"][d.weekday()], d.strftime("%H:%M"))
    return d.strftime("%d.%m %H:%M")


def gb(n):
    return "%d" % round(n / 1e9)


def build(cfg, info, disk, smart, now):
    t = TEXT.get(cfg["LANG"], TEXT["az"])
    title = ("BITRONE " + cfg["SN"])[:16]
    warn_h = float(cfg["WARN_HOURS"])
    pages, state, reasons = [], "ok", []

    main = info["main"]
    if main is None:
        if state == "ok":
            state = "warn"
        reasons.append("no_backups")
        pages.append({"icon": "warn", "big": "---", "lines": [t["never"], t["notified"]]})
    else:
        age = now - main
        late = age > warn_h * 3600
        if late:
            if state == "ok":
                state = "warn"
            reasons.append("late")
        icon = "warn" if late else ("busy" if info["busy"] else "ok")
        lines = ["%s: %s" % (t["last"], when(main, now, t))]
        if late:
            lines.append(t["no_backup"])
        elif info["full"]:
            lines.append("%s: %s" % (t["full"], when(info["full"], now, t)))
        if info["busy"]:
            lines = [t["busy"]] + lines[:1]
        pages.append({"icon": icon, "big": ago(age, t), "lines": lines})

    full = info["full"]
    if main is not None and full is not None and now - full > float(cfg["FULL_WARN_DAYS"]) * 86400:
        if state == "ok":
            state = "warn"
        reasons.append("full_old")
        pages.append({"icon": "warn", "big": t["full"][:6],
                      "lines": [t["full_old"], when(full, now, t) if full else t["none"]]})

    if disk:
        pct = round(disk.used * 100 / disk.total) if disk.total else 0
        bad_disk = pct >= int(cfg["DISK_WARN_PCT"])
        if bad_disk or smart is False:
            if state == "ok":
                state = "warn"
            reasons.append("disk")
        lines = ["%s/%s GB" % (gb(disk.used), gb(disk.total)), "%s GB %s" % (gb(disk.free), t["free"])]
        if smart is True:
            lines = [lines[0], t["smart_ok"]]
        elif smart is False:
            lines = [lines[0], t["smart_bad"]]
        pages.append({"icon": "warn" if (bad_disk or smart is False) else "ok",
                      "big": "%d%%" % pct, "lines": [t["disk"] + ": " + lines[0], lines[1]]})

    if cfg["SOURCE"] or cfg["CLIENT"]:
        lines = []
        if cfg["CLIENT"]:
            lines += [t["client"], cfg["CLIENT"]]
        if cfg["SOURCE"]:
            lines += [t["folder"], cfg["SOURCE"]]
        pages.append({"lines": lines[:4]})

    if state == "ok" and info["busy"]:
        state = "busy"
    msg = {"state": state, "title": title, "pages": pages, "contrast": int(cfg["CONTRAST"])}
    status = {
        "sn": cfg["SN"], "client": cfg["CLIENT"], "state": state, "reasons": reasons,
        "last_backup": main, "last_full": full, "busy": info["busy"],
        "repos": info["repos"],
        "disk_used_pct": round(disk.used * 100 / disk.total) if disk and disk.total else None,
        "smart_ok": smart, "updated": now,
    }
    return msg, status


# ---------- последовательный порт ----------

def find_serial(setting):
    if setting and setting != "auto":
        return setting
    for pat in ("/dev/serial/by-id/*MicroPython*", "/dev/serial/by-id/*RP2*", "/dev/ttyACM*"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return None


class Serial:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        a = termios.tcgetattr(self.fd)
        a[0] = 0                                    # iflag
        a[1] = 0                                    # oflag
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        a[3] = 0                                    # lflag: без эха и канонического режима
        a[4] = a[5] = termios.B115200
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        self.buf = b""

    def send(self, obj):
        data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        view = memoryview(data)
        deadline = time.time() + 3
        while view:
            try:
                n = os.write(self.fd, view)
                view = view[n:]
            except BlockingIOError:
                if time.time() > deadline:
                    raise TimeoutError("serial write timeout")
                select.select([], [self.fd], [], 0.2)

    def lines(self):
        out = []
        while True:
            try:
                chunk = os.read(self.fd, 256)
            except BlockingIOError:
                break
            if not chunk:
                break
            self.buf += chunk
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            out.append(line.strip().decode(errors="replace"))
        self.buf = self.buf[-512:]
        return out

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


def write_status(path, status):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as e:
        print("status.json: %s" % e, file=sys.stderr)


def snapshot(cfg, smart, now=None):
    now = now or time.time()
    info = scan(cfg["REPO_ROOT"])
    try:
        disk = shutil.disk_usage(cfg["REPO_ROOT"])
    except OSError:
        disk = None
    return build(cfg, info, disk, smart, now)


def main():
    ap = argparse.ArgumentParser(description="Bitrone Box status → OLED/LED stand")
    ap.add_argument("-c", "--config", default="/etc/bitrone-box/box.conf")
    ap.add_argument("--once", action="store_true", help="напечатать сообщение и выйти")
    args = ap.parse_args()
    cfg = load_config(args.config)

    if args.once:
        msg, status = snapshot(cfg, smart_ok(cfg["SMART_DEVICE"], cfg["STATE_DIR"]))
        print(json.dumps(msg, ensure_ascii=False, indent=1))
        print(json.dumps(status, ensure_ascii=False, indent=1))
        return

    interval = max(2, int(cfg["INTERVAL"]))
    ser, smart, smart_at = None, None, 0
    while True:
        now = time.time()
        if now - smart_at > 600:
            smart, smart_at = smart_ok(cfg["SMART_DEVICE"], cfg["STATE_DIR"]), now
        msg, status = snapshot(cfg, smart, now)
        write_status(cfg["STATUS_JSON"], status)
        try:
            if ser is None:
                path = find_serial(cfg["SERIAL"])
                if path:
                    ser = Serial(path)
                    print("serial: %s" % path, flush=True)
            if ser:
                ser.lines()  # сбросить вход платы (кнопка подтверждения больше не используется)
                ser.send(msg)
        except (OSError, TimeoutError) as e:
            print("serial: %s" % e, file=sys.stderr, flush=True)
            if ser:
                ser.close()
            ser = None
        time.sleep(interval)


if __name__ == "__main__":
    main()
