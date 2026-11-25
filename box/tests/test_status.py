import json
import os
import sys
import time
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "status"))
import bitrone_box_status as bs  # noqa: E402

Disk = namedtuple("Disk", "total used free")
NOW = time.time()


def make_repo(root, name, snap_ages=(), lock=False):
    r = root / name
    (r / "snapshots").mkdir(parents=True)
    (r / "locks").mkdir()
    (r / "config").write_text("x")
    for i, age in enumerate(snap_ages):
        f = r / "snapshots" / ("%064x" % i)
        f.write_text("s")
        os.utime(f, (NOW - age, NOW - age))
    if lock:
        (r / "locks" / "abc").write_text("l")
    return r


def cfg(root, **kw):
    c = dict(bs.DEFAULTS, REPO_ROOT=str(root), STATE_DIR=str(root / "_state"))
    c.update(kw)
    return c


def run(c, disk=Disk(500e9, 100e9, 400e9), smart=None):
    info = bs.scan(c["REPO_ROOT"])
    return bs.build(c, info, disk, smart, NOW)


def test_ok_fresh_backup(tmp_path):
    make_repo(tmp_path, "client/main", [7200, 720])
    make_repo(tmp_path, "client/full-2026-W41", [3 * 86400])
    msg, st = run(cfg(tmp_path))
    assert msg["state"] == "ok"
    first = msg["pages"][0]
    assert first["icon"] == "ok" and first["big"] == "12 dəq"
    assert first["lines"][0].startswith("Son nüsxə: ")
    assert first["lines"][1].startswith("Tam: ")
    assert st["repos"] == 2 and st["reasons"] == []


def test_late_backup_warns(tmp_path):
    make_repo(tmp_path, "main", [3 * 3600 + 60])
    make_repo(tmp_path, "full", [86400])
    msg, st = run(cfg(tmp_path))
    assert msg["state"] == "warn" and "late" in st["reasons"]
    assert msg["pages"][0]["big"] == "3 saat"
    assert "Nüsxə gəlmir" in msg["pages"][0]["lines"]


def test_big_text_fits_screen(tmp_path):
    make_repo(tmp_path, "main", [23 * 3600])
    msg, _ = run(cfg(tmp_path))
    assert len(msg["pages"][0]["big"]) <= 6


def test_no_backups_yet(tmp_path):
    (tmp_path / "empty").mkdir()
    msg, st = run(cfg(tmp_path))
    assert msg["state"] == "warn" and "no_backups" in st["reasons"]
    assert msg["pages"][0]["lines"][0] == "Nüsxə yoxdur"


def test_busy_when_locked(tmp_path):
    make_repo(tmp_path, "main", [600], lock=True)
    make_repo(tmp_path, "full-1", [86400])
    msg, _ = run(cfg(tmp_path))
    assert msg["state"] == "busy" and msg["pages"][0]["icon"] == "busy"


def test_full_too_old_and_disk(tmp_path):
    make_repo(tmp_path, "main", [600])
    make_repo(tmp_path, "full", [10 * 86400])
    msg, st = run(cfg(tmp_path), disk=Disk(500e9, 450e9, 50e9), smart=False)
    assert msg["state"] == "warn"
    assert "full_old" in st["reasons"] and "disk" in st["reasons"]
    disk_page = [p for p in msg["pages"] if p.get("big") == "90%"][0]
    assert "DİSK XƏTASI!" in disk_page["lines"]


def test_folder_page_and_english(tmp_path):
    make_repo(tmp_path, "main", [600])
    make_repo(tmp_path, "full", [86400])
    msg, _ = run(cfg(tmp_path, LANG="en", CLIENT="INCHMARK", SOURCE=r"D:\1C\Buh"))
    assert msg["pages"][0]["big"] == "10 min"
    assert msg["pages"][-1]["lines"] == ["Client:", "INCHMARK", "Folder:", r"D:\1C\Buh"]
    # строка для платы — одна строка JSON в UTF-8
    line = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
    assert "\n" not in line and len(line.encode()) < 2048


def test_config_file(tmp_path):
    p = tmp_path / "box.conf"
    p.write_text("# c\nSN=BX-0007\nSOURCE=D:\\1C\\Buh\nLANG=en\n", encoding="utf-8")
    c = bs.load_config(str(p))
    assert c["SN"] == "BX-0007" and c["SOURCE"] == "D:\\1C\\Buh" and c["LANG"] == "en"


def test_smart_file(tmp_path):
    d = tmp_path / "st"
    d.mkdir()
    (d / "smart.txt").write_text("SMART overall-health self-assessment test result: PASSED")
    assert bs.smart_ok("/dev/sda", str(d)) is True
    (d / "smart.txt").write_text("... FAILED!")
    assert bs.smart_ok("/dev/sda", str(d)) is False
    assert bs.smart_ok("", str(d)) is None
