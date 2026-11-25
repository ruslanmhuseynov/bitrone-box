"""Bitrone Box — мини-консоль под Waveshare RP2040-GEEK (вариант B).

Клин 90×48 мм: GEEK лежит в кармане на наклонной грани (экран вверх, утоплен на 2 мм),
его USB-штекер входит в угловой переходник USB-A 90° в кармане справа; переходник
вставляется сзади, его штекер торчит назад — туда надевается обычный удлинитель к мини-ПК.
Спереди — выгравированный логотип Bitrone, в дне — 2 гнезда под магниты 10×2 мм.

Запуск (нужны manifold3d, numpy; для превью — matplotlib):
    python box/stand/mini/build_console.py            # STL
    python box/stand/mini/build_console.py --preview  # + картинки PNG
Размеры GEEK и переходника — в PARAMS; перед печатью измерьте свои штангенциркулем.
"""
import argparse
import json
import math
import os
import struct

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold

HERE = os.path.dirname(os.path.abspath(__file__))

PARAMS = {
    # корпус
    "L": 90.0,            # длина (поперёк стола)
    "D": 48.0,            # глубина
    "hf": 16.0,           # высота спереди
    "hb": 34.0,           # высота сзади
    "r": 6.0,             # скругление углов
    # RP2040-GEEK (без штекера)
    "geek_l": 61.5, "geek_w": 25.5, "geek_t": 9.6,
    "fit": 0.4,           # зазор посадки
    "recess": 2.0,        # насколько экран утоплен ниже грани
    "left_wall": 3.0,
    # угловой переходник USB-A «папа–мама» 90°
    "adp_l": 22.0,        # от торца GEEK до конца переходника
    "adp_w": 17.0,        # ширина
    "adp_t": 10.0,        # толщина
    # рамка поверх GEEK: закрывает белый корпус, видно только экран (измерьте положение экрана)
    "bezel_t": 1.6,
    "screen_x": 4.0,      # от левого края GEEK (сторона без USB) до окна экрана
    "screen_l": 27.0, "screen_w": 15.5,
    "screen_dy": 0.0,     # смещение окна поперёк GEEK (+ — назад)
    # логотип на передней грани
    "logo_depth": 0.8,
    "mark_h": 11.0,
    "word_h": 6.0,
    # магниты в дне
    "magnet_d": 10.3, "magnet_h": 2.2,
}


def ang(p):
    return math.degrees(math.atan2(p["hb"] - p["hf"], p["D"]))


def slope_len(p):
    return math.hypot(p["D"], p["hb"] - p["hf"])


def on_slope(m, p):
    """Из системы наклонной грани (x — вдоль, y — вверх по склону, z — наружу) в мировую."""
    return m.rotate((ang(p), 0, 0)).translate((0, 0, p["hf"]))


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def body(p):
    prof = CrossSection([np.array([[0, 0], [p["D"], 0], [p["D"], p["hb"]], [0, p["hf"]]])])
    wedge = prof.extrude(p["L"]).rotate((90, 0, 90))       # (u,v,w) -> (w,u,v)
    foot = CrossSection.square((p["L"] - 2 * p["r"], p["D"] - 2 * p["r"])) \
        .translate((p["r"], p["r"])).offset(p["r"], JoinType.Round, circular_segments=48)
    return wedge ^ foot.extrude(p["hb"] + 1)


def logo(p):
    with open(os.path.join(HERE, "logo_paths.json")) as f:
        d = json.load(f)
    mark = CrossSection([np.array(c) for c in d["mark"]], FillRule.EvenOdd).scale((p["mark_h"], p["mark_h"]))
    word = CrossSection([np.array(c) for c in d["word"]], FillRule.EvenOdd).scale((p["word_h"], p["word_h"]))
    mw, ww, gap = p["mark_h"] * d["mark_aspect"], p["word_h"] * d["word_aspect"], 3.5
    x0 = (p["L"] - (mw + gap + ww)) / 2
    zc = p["hf"] / 2
    mark = mark.translate((x0, zc - p["mark_h"] / 2))
    word = word.translate((x0 + mw + gap, zc - p["word_h"] / 2))
    cut = (mark + word).extrude(p["logo_depth"] + 1)       # в плоскости XY, толщина по Z
    # XY -> XZ (буквы на передней грани y=0), гравировка вглубь корпуса
    return cut.rotate((90, 0, 0)).translate((0, p["logo_depth"], 0))


def model(p):
    m = body(p)
    S = slope_len(p)
    yc = S / 2
    gl, gw, gt = p["geek_l"] + p["fit"], p["geek_w"] + p["fit"], p["geek_t"] + 0.3
    x0 = p["left_wall"]
    x1 = x0 + gl
    floor = -(p["recess"] + gt)
    # карман GEEK (открыт сверху)
    pocket = box(x0, x1, yc - gw / 2, yc + gw / 2, floor, 10)
    # полукруглая выемка у переднего края кармана — поддеть GEEK пальцем
    finger = Manifold.cylinder(30, 8, circular_segments=48).translate((x0 + gl * 0.35, yc - gw / 2, floor + 3))
    # карман переходника: на оси штекера GEEK, сквозной назад (переходник вставляется сзади)
    axis = -(p["recess"] + p["geek_t"] / 2)
    adp = box(x1 - 0.5, x1 + p["adp_l"], yc - p["adp_w"] / 2, S + 40,
              axis - p["adp_t"] / 2, axis + p["adp_t"] / 2)
    m = m - on_slope(pocket + finger + adp, p)
    m = m - logo(p)
    for x in (p["L"] * 0.28, p["L"] * 0.72):
        m = m - Manifold.cylinder(p["magnet_h"] + 0.01, p["magnet_d"] / 2, circular_segments=40) \
            .translate((x, p["D"] / 2, -0.01))
    return m


def assembly(p):
    """Макеты GEEK и переходника на своих местах — только для картинок, не печатать."""
    S = slope_len(p)
    yc = S / 2
    x0 = p["left_wall"] + p["fit"] / 2
    gl, gw, gt = p["geek_l"], p["geek_w"], p["geek_t"]
    top = -p["recess"] - 0.15
    geek = box(x0, x0 + gl, yc - gw / 2, yc + gw / 2, top - gt, top)
    screen = box(x0 + 4, x0 + 30, yc - 7.5, yc + 7.5, top - 0.2, top + 0.05)
    header = box(x0 + 4, x0 + 30, yc + 5.0, yc + 7.5, top - 0.1, top + 0.1)
    axis = -(p["recess"] + gt / 2)
    x1 = x0 + gl
    adp = box(x1, x1 + p["adp_l"] - 1, yc - p["adp_w"] / 2 + 0.3, yc + p["adp_w"] / 2 - 0.3,
              axis - p["adp_t"] / 2 + 0.3, axis + p["adp_t"] / 2 - 0.3)
    plug = box(x1 + p["adp_l"] - 16, x1 + p["adp_l"] - 4, yc + p["adp_w"] / 2 - 0.3, S + 12,
               axis - 2.3, axis + 2.3)
    cable = box(x1 + p["adp_l"] - 17, x1 + p["adp_l"] - 3, S + 12, S + 40, axis - 4.5, axis + 4.5)
    return {k: on_slope(v, p) for k, v in
            {"geek": geek, "screen": screen, "header": header, "adapter": adp, "plug": plug, "cable": cable}.items()}


def bezel(p, placed=True):
    """Рамка в утопленную часть кармана над GEEK, окно — над экраном."""
    S = slope_len(p)
    yc = S / 2
    x0 = p["left_wall"] + 0.15
    gl, gw = p["geek_l"] + p["fit"] - 0.3, p["geek_w"] + p["fit"] - 0.3
    top = -p["recess"] + p["bezel_t"]
    plate = box(x0, x0 + gl, yc - gw / 2, yc + gw / 2, -p["recess"], top)
    wx = p["left_wall"] + p["fit"] / 2 + p["screen_x"]
    win = box(wx, wx + p["screen_l"], yc - p["screen_w"] / 2 + p["screen_dy"],
              yc + p["screen_w"] / 2 + p["screen_dy"], -5, 5)
    # маленький щит Bitrone на рамке справа от экрана
    with open(os.path.join(HERE, "logo_paths.json")) as f:
        d = json.load(f)
    mh = 9.0
    mark = CrossSection([np.array(c) for c in d["mark"]], FillRule.EvenOdd).scale((mh, mh))
    mx = wx + p["screen_l"] + (x0 + gl - wx - p["screen_l"] - mh * d["mark_aspect"]) / 2
    emb = mark.translate((mx, yc - mh / 2)).extrude(0.6).translate((0, 0, top - 0.01))
    part = plate - win + emb
    if placed:
        return on_slope(part, p)
    return part.translate((-x0, -(yc - gw / 2), p["recess"]))   # плашмя на столе — для печати


def logo_inlay(p):
    """Заливка гравировки логотипа — второй цвет при печати (или не печатать и закрасить)."""
    return logo(p) ^ body(p)


def write_stl(m, path):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    t = np.asarray(mesh.tri_verts)
    with open(path, "wb") as f:
        f.write(b"Bitrone mini console".ljust(80, b" "))
        f.write(struct.pack("<I", len(t)))
        for a, b, c in t:
            pa, pb, pc = v[a], v[b], v[c]
            n = np.cross(pb - pa, pc - pa)
            ln = np.linalg.norm(n)
            n = n / ln if ln else n
            f.write(struct.pack("<12fH", *n, *pa, *pb, *pc, 0))
    return len(t)


def preview(m, path, elev, azim, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    t = np.asarray(mesh.tri_verts)
    tris = v[t]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    light = np.array([-0.4, -0.7, 0.8])
    light /= np.linalg.norm(light)
    k = np.clip(n @ light, 0, 1) * 0.65 + 0.3
    base = np.array([0.10, 0.20, 0.42])
    cols = np.clip(base[None, :] * k[:, None] * 1.6, 0, 1)
    fig = plt.figure(figsize=(8, 6), facecolor="#0A1428")
    ax = fig.add_subplot(111, projection="3d", facecolor="#0A1428")
    ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none"))
    mn, mx = v.min(0), v.max(0)
    c = (mn + mx) / 2
    r = (mx - mn).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, color="#EAF0FB")
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="#0A1428")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--assembly", action="store_true", help="макеты GEEK/переходника для рендера")
    args = ap.parse_args()
    p = PARAMS
    m = model(p)
    stl = os.path.join(args.out, "bitrone_mini_console.stl")
    n = write_stl(m, stl)
    write_stl(bezel(p, placed=False), os.path.join(args.out, "bitrone_mini_bezel.stl"))
    if args.assembly:
        write_stl(bezel(p), os.path.join(args.out, "asm_bezel_placed.stl"))
    write_stl(logo_inlay(p), os.path.join(args.out, "bitrone_mini_logo_inlay.stl"))
    print("bezel: %.1f cm3, logo inlay: %.2f cm3" % (bezel(p).volume() / 1000, logo_inlay(p).volume() / 1000))
    vol = m.volume() / 1000.0
    print("STL: %s (%d triangles)" % (stl, n))
    print("solid volume %.1f cm3; angle %.1f deg; genus %d" % (vol, ang(p), m.genus()))
    bb = m.bounding_box()
    print("bbox", [round(x, 1) for x in bb])
    if args.assembly:
        for k, part in assembly(p).items():
            write_stl(part, os.path.join(args.out, "asm_%s.stl" % k))
        print("assembly STLs written (for renders only)")
    if args.preview:
        preview(m, os.path.join(args.out, "preview_front.png"), 22, -60, "Bitrone mini console")
        preview(m, os.path.join(args.out, "preview_back.png"), 25, 125, "back: adapter slot")
        preview(m, os.path.join(args.out, "preview_bottom.png"), -60, -70, "bottom: magnets")
        preview(m, os.path.join(args.out, "preview_logo.png"), 4, -90, "front: logo")


if __name__ == "__main__":
    main()
