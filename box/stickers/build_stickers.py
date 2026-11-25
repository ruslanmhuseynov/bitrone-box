"""Наклейки Bitrone Box для варианта A (GEEK прямо в USB мини-ПК, без подставки).

Делает SVG в реальном размере (мм) для печати на виниле с плоттерной резкой:
  geek_skin_<цвет>.svg — «скин» на верх RP2040-GEEK: закрывает белый корпус, окно над экраном
  pc_sticker_<цвет>.svg — наклейка на крышку мини-ПК
Слой «CUT» (пурпурная линия 0.1 мм) — контур резки для типографии, не печатается.
Логотип — векторные контуры из box/stand/mini/logo_paths.json.

    python box/stickers/build_stickers.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "..", "stand", "mini", "logo_paths.json")

# RP2040-GEEK: верхняя грань и экран (измерьте свой экземпляр и поправьте)
GEEK = {"w": 61.0, "h": 25.0, "r": 2.0, "screen_x": 4.0, "screen_w": 27.0, "screen_h": 15.5, "screen_dy": 0.0}

THEMES = {
    "graphite": {"bg": "#1F2126", "mark": "#5BD455", "word": "#FFFFFF", "sub": "#9AA3B2"},
    "navy": {"bg": "#13254A", "mark": "#FFFFFF", "word": "#FFFFFF", "sub": "#9FB0CF"},
    "white": {"bg": "#F4F6F9", "mark": "#0F2C6B", "word": "#0F2C6B", "sub": "#5A6E93"},
}

with open(LOGO) as f:
    L = json.load(f)


def path_d(polys, x, y, h):
    """Контуры логотипа (высота 1, y вверх) → SVG path в мм: левый нижний угол (x, y+h)."""
    parts = []
    for poly in polys:
        pts = ["%.3f,%.3f" % (x + px * h, y + h - py * h) for px, py in poly]
        parts.append("M" + " L".join(pts) + " Z")
    return " ".join(parts)


def svg(w, h, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" viewBox="0 0 %s %s">\n'
            '%s\n</svg>\n' % (w, h, w, h, body))


def rrect(x, y, w, h, r):
    return ("M%.2f,%.2f h%.2f a%.2f,%.2f 0 0 1 %.2f,%.2f v%.2f a%.2f,%.2f 0 0 1 %.2f,%.2f h%.2f "
            "a%.2f,%.2f 0 0 1 %.2f,%.2f v%.2f a%.2f,%.2f 0 0 1 %.2f,%.2f Z" %
            (x + r, y, w - 2 * r, r, r, r, r, h - 2 * r, r, r, -r, r, -(w - 2 * r),
             r, r, -r, -r, -(h - 2 * r), r, r, r, -r))


def geek_skin(t):
    g = GEEK
    m = 1.0          # поле вокруг, чтобы показать контур резки
    W, H = g["w"] + 2 * m, g["h"] + 2 * m
    sx = m + g["screen_x"]
    sy = m + (g["h"] - g["screen_h"]) / 2 + g["screen_dy"]
    outer = rrect(m, m, g["w"], g["h"], g["r"])
    win = rrect(sx, sy, g["screen_w"], g["screen_h"], 1.0)
    # правая часть: знак + BITRONE + подпись
    zx = sx + g["screen_w"] + 3.0
    zw = m + g["w"] - 2.5 - zx
    mark_h = 8.0
    mark_w = mark_h * L["mark_aspect"]
    word_h = min(3.2, zw / L["word_aspect"])
    word_w = word_h * L["word_aspect"]
    cx = zx + zw / 2
    top = m + (g["h"] - (mark_h + 2.0 + word_h + 1.6 + 2.2)) / 2
    body = [
        '<g id="PRINT">',
        '<path fill="%s" fill-rule="evenodd" d="%s %s"/>' % (t["bg"], outer, win),
        '<path fill="%s" fill-rule="evenodd" d="%s"/>' % (t["mark"], path_d(L["mark"], cx - mark_w / 2, top, mark_h)),
        '<path fill="%s" fill-rule="evenodd" d="%s"/>' % (t["word"], path_d(L["word"], cx - word_w / 2, top + mark_h + 2.0, word_h)),
        '<text x="%.2f" y="%.2f" font-family="Arial, Helvetica, sans-serif" font-size="2.2" font-weight="700" '
        'letter-spacing="0.5" text-anchor="middle" fill="%s">BOX · SOC</text>' % (cx, top + mark_h + 2.0 + word_h + 1.6 + 1.9, t["sub"]),
        '</g>',
        '<g id="CUT" fill="none" stroke="#FF00FF" stroke-width="0.1"><path d="%s"/><path d="%s"/></g>' % (outer, win),
    ]
    return svg(round(W, 2), round(H, 2), "\n".join(body))


def pc_sticker(t):
    W, H, r = 80.0, 50.0, 4.0
    m = 1.0
    outer = rrect(m, m, W, H, r)
    mark_h = 16.0
    mark_w = mark_h * L["mark_aspect"]
    word_h = 5.2
    word_w = word_h * L["word_aspect"]
    x0 = m + 6.0
    body = [
        '<g id="PRINT">',
        '<path fill="%s" d="%s"/>' % (t["bg"], outer),
        '<path fill="%s" fill-rule="evenodd" d="%s"/>' % (t["mark"], path_d(L["mark"], x0, m + 6.0, mark_h)),
        '<path fill="%s" fill-rule="evenodd" d="%s"/>' % (t["word"], path_d(L["word"], x0 + mark_w + 4.0, m + 6.0 + (mark_h - word_h) / 2 - 2.2, word_h)),
        '<text x="%.2f" y="%.2f" font-family="Arial, Helvetica, sans-serif" font-size="3.4" font-weight="700" '
        'letter-spacing="1.2" fill="%s">BOX · SOC</text>' % (x0 + mark_w + 4.0, m + 6.0 + (mark_h + word_h) / 2 + 2.6, t["sub"]),
        '<text x="%.2f" y="%.2f" font-family="Arial, Helvetica, sans-serif" font-size="3.6" fill="%s">'
        'Bu kompüter Bitrone SOC tərəfindən qorunur</text>' % (x0, m + 31.5, t["word"]),
        '<rect x="%.2f" y="%.2f" width="%.2f" height="8" rx="4" fill="#E5484D"/>' % (x0, m + 35.5, W - 12.0),
        '<text x="%.2f" y="%.2f" font-family="Arial, Helvetica, sans-serif" font-size="3.1" font-weight="800" '
        'letter-spacing="0.3" text-anchor="middle" fill="#FFFFFF">SÖNDÜRMƏYİN · ÇIXARMAYIN</text>' % (m + W / 2, m + 40.6),
        '</g>',
        '<g id="CUT" fill="none" stroke="#FF00FF" stroke-width="0.1"><path d="%s"/></g>' % outer,
    ]
    return svg(W + 2 * m, H + 2 * m, "\n".join(body))


def main():
    out = os.path.join(HERE, "svg")
    os.makedirs(out, exist_ok=True)
    for name, t in THEMES.items():
        for kind, fn in (("geek_skin", geek_skin), ("pc_sticker", pc_sticker)):
            p = os.path.join(out, "%s_%s.svg" % (kind, name))
            with open(p, "w", encoding="utf-8") as f:
                f.write(fn(t))
            print(p)


if __name__ == "__main__":
    main()
