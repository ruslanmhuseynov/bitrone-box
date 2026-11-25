"""Обводит логотип Bitrone (frontend/logo.png) в контуры для 3D-модели и наклеек.

Результат — logo_paths.json: {"mark": [...], "word": [...]}, каждый контур — список
точек [x, y] в миллиметрах условного масштаба (высота знака = 1.0, y вверх).
Контуры с отверстиями — правило заливки even-odd.

Запуск (нужны opencv-python-headless, numpy, pillow):
    python box/stand/mini/trace_logo.py
"""
import json
import os

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "..", "..", "..", "frontend", "logo.png")


def contours(mask, eps):
    cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        if cv2.contourArea(c) < 40:
            continue
        a = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(float)
        if len(a) >= 3:
            out.append(a)
    return out


def norm(polys, top, bottom, left):
    """Пиксели → единицы, где высота области = 1, y вверх, левый край = 0."""
    h = float(bottom - top)
    return [[[round((x - left) / h, 5), round((bottom - y) / h, 5)] for x, y in p] for p in polys]


def main():
    img = np.asarray(Image.open(SRC).convert("RGB")).astype(int)
    ink = (765 - img.sum(axis=2)) > 120          # всё, что заметно темнее белого
    ink = ink.astype(np.uint8) * 255
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    rows = np.where(ink.max(axis=1) > 0)[0]
    # три полосы: знак, слово BITRONE, слоган — разделены пустыми строками
    gaps = np.where(np.diff(rows) > 8)[0]
    bands = np.split(rows, gaps + 1)
    mark_rows, word_rows = bands[0], bands[1]

    def band(rows_):
        t, b = rows_.min(), rows_.max() + 1
        m = np.zeros_like(ink)
        m[t:b] = ink[t:b]
        cols = np.where(m.max(axis=0) > 0)[0]
        return m, t, b, cols.min(), cols.max() + 1

    mm, mt, mb, ml, mr = band(mark_rows)
    wm, wt, wb, wl, wr = band(word_rows)
    data = {
        "mark": norm(contours(mm, 1.2), mt, mb, ml),
        "mark_aspect": round((mr - ml) / (mb - mt), 4),
        "word": norm(contours(wm, 1.0), wt, wb, wl),
        "word_aspect": round((wr - wl) / (wb - wt), 4),
    }
    out = os.path.join(ROOT, "logo_paths.json")
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print("mark: %d contours, aspect %.3f" % (len(data["mark"]), data["mark_aspect"]))
    print("word: %d contours, aspect %.3f" % (len(data["word"]), data["word_aspect"]))
    print("->", out)


if __name__ == "__main__":
    main()
