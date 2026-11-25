"""Bitrone Box — корпус под Raspberry Pi 4 + SSD 2.5" + экран LILYGO T-Display-S3.

Компоновка (снизу вверх): SSD 2.5" лежит на дне между рёбрами → съёмная полка на уступах
стенок → Raspberry Pi 4 на стойках полки, порты Ethernet/USB смотрят назад, питание USB-C
и micro-HDMI — в левую стенку. Экран T-Display-S3 (версия без корпуса, «Soldered Pin»)
стоит за окном в передней стенке и подключён к GPIO Pi четырьмя проводами
(5V, GND, TX, RX — без USB-кабеля внутри). SSD — через USB3-переходник короткой петлёй сзади.

Детали: tray (корпус-лоток), lid (крышка с вентиляцией и логотипом), shelf (полка под Pi),
logo_front / logo_lid (заливка логотипов вторым цветом), display_clip (прижим экрана).

    python box/enclosure/build_box.py --out box/enclosure/stl
    python box/enclosure/build_box.py --out /tmp/x --assembly     # + макеты Pi/SSD/экрана для рендеров
"""
import argparse
import json
import math
import os
import struct

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "..", "stand", "mini", "logo_paths.json")

P = {
    "W": 108.0, "D": 130.0, "H": 42.0,   # снаружи
    "r": 8.0,                              # скругление вертикальных рёбер
    "wall": 2.4, "floor": 2.4, "lid_t": 2.4,
    # SSD 2.5" (длина вдоль X)
    "ssd": (100.0, 69.85, 7.0), "ssd_y": 20.0,
    # полка
    "shelf_z": 12.0, "shelf_t": 2.0, "shelf_y0": 38.0,
    # Raspberry Pi 4
    "pi": (85.0, 56.0), "pi_standoff": 4.0,
    "pi_holes": ((3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)),
    # T-Display-S3 (плата без корпуса): плата, активная область экрана и её смещение на плате
    "disp_pcb": (62.0, 26.0, 1.6), "disp_win": (44.0, 24.0), "disp_win_dx": 4.0,
    "disp_z": 12.0,        # низ окна экрана над полом
    "disp_x": 10.0,        # левый край окна от левого края корпуса
    "logo_depth": 0.8,
}


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def rr(w, d, r, h, x=0.0, y=0.0):
    cs = CrossSection.square((w - 2 * r, d - 2 * r)).translate((r, r)) \
        .offset(r, JoinType.Round, circular_segments=48)
    return cs.extrude(h).translate((x, y, 0))


def logo_cs(kind, h):
    with open(LOGO) as f:
        d = json.load(f)
    cs = CrossSection([np.array(c) for c in d[kind]], FillRule.EvenOdd).scale((h, h))
    return cs, h * d[kind + "_aspect"]


def pi_origin(p):
    """Левый-передний угол платы Pi: длина вдоль +Y (Ethernet назад), ширина вдоль +X."""
    w = p["wall"]
    x = w + 1.0
    y = p["D"] - w - 1.0 - p["pi"][0]
    z = p["shelf_z"] + p["shelf_t"] + p["pi_standoff"]
    return x, y, z


def front_logo(p):
    """Знак и надпись справа от экрана на передней стенке (в плоскости XZ)."""
    mark, mw = logo_cs("mark", 13.0)
    word, ww = logo_cs("word", 4.2)
    wx = p["disp_x"] + p["disp_win"][0]
    right = p["W"] - 9.0
    cx = (wx + right) / 2
    z_top = p["disp_z"] + p["disp_win"][1]
    m = mark.translate((cx - mw / 2, z_top - 13.0))
    wd = word.translate((cx - ww / 2, p["disp_z"] + 0.5))
    cut = (m + wd).extrude(p["logo_depth"] + 1)
    return cut.rotate((90, 0, 0)).translate((0, p["logo_depth"], 0))


def lid_logo(p):
    mark, mw = logo_cs("mark", 26.0)
    word, ww = logo_cs("word", 5.0)
    cx, cy = 80.0, 70.0
    m = mark.translate((cx - mw / 2, cy - 4))
    wd = word.translate((cx - ww / 2, cy - 14))
    # крышка печатается верхом вниз → логотип на её наружной (верхней) грани, читается сверху
    top = p["H"]
    return (m + wd).extrude(p["logo_depth"] + 1).translate((0, 0, top - p["logo_depth"]))


def tray(p):
    W, D, H, w, f = p["W"], p["D"], p["H"], p["wall"], p["floor"]
    top = H - p["lid_t"]
    m = rr(W, D, p["r"], top) - rr(W - 2 * w, D - 2 * w, p["r"] - w, top, w, w).translate((0, 0, f))
    # угловые стойки под саморезы M3 крышки
    posts = Manifold()
    for (x, y) in ((w + 4.5, w + 4.5), (W - w - 4.5, w + 4.5), (w + 4.5, D - w - 4.5), (W - w - 4.5, D - w - 4.5)):
        posts += Manifold.cylinder(top - f, 4.2, circular_segments=32).translate((x, y, f))
        posts -= Manifold.cylinder(top, 1.3, circular_segments=24).translate((x, y, f + 4))
    m += posts
    # рёбра, держащие SSD
    sl, sw, sh = p["ssd"]
    y0 = p["ssd_y"]
    for y in (y0 - 2.0, y0 + sw):
        m += box(w + 6, w + 6 + sl - 12, y, y + 2.0, f, f + 4)
    m += box(w + 2 + sl, w + 4 + sl, y0 + 10, y0 + sw - 10, f, f + 3)      # упор справа
    # уступы под полку вдоль левой и правой стенок
    for x0, x1 in ((w, w + 3), (W - w - 3, W - w)):
        m += box(x0, x1, p["shelf_y0"], D - w - 9, f, p["shelf_z"])
    # --- вырезы ---
    px, py, pz = pi_origin(p)
    # задняя стенка: окно портов Ethernet + USB
    m -= box(px + 0.5, px + 55.5, D - w - 1, D + 1, pz + 0.8, pz + 17.6)
    # петля USB от SSD: щель снизу сзади справа
    m -= box(W - w - 30, W - w - 8, D - w - 1, D + 1, f + 1, f + 9)
    # левая стенка: USB-C питание + micro-HDMI
    m -= box(-1, w + 1, py + 4.5, py + 46.5, pz - 0.5, pz + 8.5)
    # правая стенка: вентиляция (горизонтальные щели)
    for i in range(5):
        z = 18 + i * 3.6
        m -= box(W - w - 1, W + 1, 50, D - 22, z, z + 1.8)
    # передняя стенка: окно экрана со скошенной фаской
    wx0, wz0 = p["disp_x"], p["disp_z"]
    ww, wh = p["disp_win"]
    win = box(wx0, wx0 + ww, -1, w + 1, wz0, wz0 + wh)
    chamfer = Manifold.hull(box(wx0, wx0 + ww, w - 0.2, w + 0.01, wz0, wz0 + wh) +
                            box(wx0 - 1.2, wx0 + ww + 1.2, -0.01, 0.01, wz0 - 1.2, wz0 + wh + 1.2))
    m -= win + chamfer
    m -= front_logo(p)
    # дно: гнёзда под резиновые ножки
    for (x, y) in ((14, 14), (W - 14, 14), (14, D - 14), (W - 14, D - 14)):
        m -= Manifold.cylinder(1.0, 6.2, circular_segments=32).translate((x, y, -0.01))
    # держатель платы экрана: пазы по бокам окна изнутри
    pw, ph, pt = p["disp_pcb"]
    pcb_x0 = wx0 - p["disp_win_dx"]
    for x0 in (pcb_x0 - 2.2, pcb_x0 + pw + 0.2):
        rail = box(x0, x0 + 2.0, w, w + 6.5, wz0 - 3, wz0 + ph - 2)
        rail -= box(x0 - 1, x0 + 3, w + 1.4, w + 1.4 + pt + 0.4, wz0 - 4, wz0 + ph)   # паз под край платы
        m += rail
    return m


def lid(p):
    W, D, w = p["W"], p["D"], p["wall"]
    z0 = p["H"] - p["lid_t"]
    m = rr(W, D, p["r"], p["lid_t"]).translate((0, 0, z0))
    m += rr(W - 2 * w - 0.6, D - 2 * w - 0.6, p["r"] - w, 2.0, w + 0.3, w + 0.3).translate((0, 0, z0 - 2.0)) \
        - rr(W - 2 * w - 4.6, D - 2 * w - 4.6, p["r"] - w - 2, 2.2, w + 2.3, w + 2.3).translate((0, 0, z0 - 2.1))
    for (x, y) in ((w + 4.5, w + 4.5), (W - w - 4.5, w + 4.5), (w + 4.5, D - w - 4.5), (W - w - 4.5, D - w - 4.5)):
        m -= Manifold.cylinder(10, 1.7, circular_segments=24).translate((x, y, z0 - 3))
        m -= Manifold.cylinder(2, 3.2, circular_segments=24).translate((x, y, p["H"] - 1.2))
        m -= Manifold.cylinder(3, 5.5, circular_segments=24).translate((x, y, z0 - 2.5))   # место под стойку
    # вентиляция над процессором Pi: косые щели под углом знака Bitrone
    px, py, pz = pi_origin(p)
    slots = Manifold()
    for i in range(9):
        s = box(-1.0, 1.0, -22, 22, z0 - 3, p["H"] + 1).rotate((0, 0, -38)).translate((px + 8 + i * 5.4, py + 48, 0))
        slots += s
    region = box(px + 4, px + 52, py + 22, py + 76, z0 - 4, p["H"] + 2)
    m -= slots ^ region
    m -= lid_logo(p)
    return m


def shelf(p):
    W, D, w = p["W"], p["D"], p["wall"]
    z = p["shelf_z"]
    m = box(w + 0.3, W - w - 0.3, p["shelf_y0"], D - w - 9.3, z, z + p["shelf_t"])
    px, py, pz = pi_origin(p)
    # вентиляция полки
    for i in range(6):
        m -= box(px + 10, px + 46, py + 14 + i * 9, py + 18 + i * 9, z - 1, z + 3)
    for hx, hy in p["pi_holes"]:
        # отверстие платы: hx — вдоль длины (Y), hy — поперёк (X)
        x, y = px + hy, py + hx
        m += Manifold.cylinder(p["pi_standoff"], 3.0, circular_segments=24).translate((x, y, z + p["shelf_t"]))
        m -= Manifold.cylinder(p["pi_standoff"] + 3, 1.15, circular_segments=16).translate((x, y, z - 0.5))
    # винты полки в уступы
    for x in (w + 1.5, W - w - 1.5):
        for y in (p["shelf_y0"] + 8, D - w - 18):
            m -= Manifold.cylinder(5, 1.1, circular_segments=16).translate((x, y, z - 1))
    return m


def logo_inlays(p):
    t = tray(p)
    full = rr(p["W"], p["D"], p["r"], p["H"])
    front = front_logo(p) ^ full
    top = lid_logo(p) ^ full
    return front, top


def assembly(p):
    px, py, pz = pi_origin(p)
    sl, sw, sh = p["ssd"]
    w, f = p["wall"], p["floor"]
    parts = {}
    parts["ssd"] = box(w + 2, w + 2 + sl, p["ssd_y"], p["ssd_y"] + sw, f, f + sh)
    pcb = box(px, px + p["pi"][1], py, py + p["pi"][0], pz, pz + 1.4)
    parts["pi"] = pcb
    parts["pi_ports"] = (box(px + 2, px + 15, py + 66, py + 87, pz + 1.4, pz + 17)       # USB2
                         + box(px + 20, px + 33, py + 66, py + 87, pz + 1.4, pz + 17)    # USB3
                         + box(px + 38, px + 54, py + 64, py + 87, pz + 1.4, pz + 14.9)  # Ethernet
                         + box(px - 1, px + 3, py + 7.6, py + 15, pz + 1.4, pz + 4.6)     # USB-C
                         + box(px - 1, px + 7, py + 22.5, py + 30, pz + 1.4, pz + 4.4)
                         + box(px - 1, px + 7, py + 36, py + 43.5, pz + 1.4, pz + 4.4))
    parts["pi_cpu"] = box(px + 22, px + 36, py + 25, py + 39, pz + 1.4, pz + 9)        # радиатор
    parts["gpio"] = box(px + 51, px + 56, py + 7, py + 58, pz + 1.4, pz + 10)
    wx0, wz0 = p["disp_x"], p["disp_z"]
    pw, ph, pt = p["disp_pcb"]
    parts["disp_pcb"] = box(wx0 - p["disp_win_dx"], wx0 - p["disp_win_dx"] + pw, w + 1.4, w + 1.4 + pt,
                            wz0 - 1, wz0 - 1 + ph)
    sx0, sz0 = wx0, wz0
    parts["screen"] = box(sx0, sx0 + p["disp_win"][0], w + 1.0, w + 1.4, sz0, sz0 + p["disp_win"][1])
    parts["screen_header"] = box(sx0, sx0 + p["disp_win"][0], w + 0.95, w + 1.0, sz0 + p["disp_win"][1] - 4.0,
                                 sz0 + p["disp_win"][1])
    parts["screen_check"] = (box(sx0 + 3, sx0 + 6, w + 0.95, w + 1.0, sz0 + 8, sz0 + 13)
                             + box(sx0 + 10, sx0 + 30, w + 0.95, w + 1.0, sz0 + 8, sz0 + 14))
    parts["usb_loop"] = (box(p["W"] - w - 26, p["W"] - w - 12, p["D"] - 1, p["D"] + 14, f + 3, f + 7)
                         + box(px + 22, px + 31, p["D"] - 1, p["D"] + 14, pz + 6, pz + 10)
                         + box(px + 22, p["W"] - w - 12, p["D"] + 10, p["D"] + 14, f + 3, pz + 10))
    return parts


def write_stl(m, path):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    t = np.asarray(mesh.tri_verts)
    with open(path, "wb") as fh:
        fh.write(b"Bitrone Box enclosure".ljust(80, b" "))
        fh.write(struct.pack("<I", len(t)))
        for a, b, c in t:
            pa, pb, pc = v[a], v[b], v[c]
            n = np.cross(pb - pa, pc - pa)
            ln = np.linalg.norm(n)
            n = n / ln if ln else n
            fh.write(struct.pack("<12fH", *n, *pa, *pb, *pc, 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "stl"))
    ap.add_argument("--assembly", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    p = P
    t, l, s = tray(p), lid(p), shelf(p)
    lf, lt = logo_inlays(p)
    items = {"bitrone_box_tray": t, "bitrone_box_lid": l, "bitrone_box_shelf": s,
             "bitrone_box_logo_front": lf, "bitrone_box_logo_lid": lt}
    for name, m in items.items():
        write_stl(m, os.path.join(args.out, name + ".stl"))
        print("%-26s %6.1f cm3  genus %d" % (name, m.volume() / 1000, m.genus()))
    if args.assembly:
        for k, m in assembly(p).items():
            write_stl(m, os.path.join(args.out, "asm_%s.stl" % k))
        print("assembly written")


if __name__ == "__main__":
    main()
