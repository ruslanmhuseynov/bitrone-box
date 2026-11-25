# Bitrone Box — экран статуса на LILYGO T-Display-S3 (1.9", 320x170, MicroPython).
# Питание и данные — один кабель USB-C от мини-ПК. Служба bitrone-box-status на ПК
# раз в ~10 с шлёт строку JSON (тот же протокол, что для OLED/GEEK):
#   {"state":"ok","title":"BITRONE BX-0001",
#    "pages":[{"icon":"ok","big":"12 dəq","lines":["Son nüsxə: 14:32","Tam: Bazar 02:10"]}]}
# state: ok | busy | warn | alert | off — цвет шапки/фона и иконка.
# Кнопки: нижняя (GPIO14) — разбудить экран, в alert — подтвердить (шлёт ПК "ACK");
#         верхняя (GPIO0, BOOT) — следующая страница.
import sys, time, json, select, framebuf
from machine import Pin
from lcd import LCD, rgb

ORIENTATION = "landscape"   # landscape | landscape_flip | portrait | portrait_flip
PAGE_SEC = 6
OFFLINE_SEC = 120           # нет данных от ПК — «Kompüter cavab vermir»
DIM_SEC = 0                 # приглушать подсветку через N с без событий (0 — нет)
BRIGHT, DIM = 170, 25

BG = rgb(10, 20, 40)
FG = rgb(234, 240, 251)
MUTE = rgb(133, 152, 190)
DARK = rgb(10, 20, 40)
TRACK = rgb(34, 52, 92)
COL = {"ok": rgb(91, 212, 85), "busy": rgb(59, 158, 255), "warn": rgb(245, 166, 35),
       "alert": rgb(229, 72, 77), "off": rgb(90, 110, 147)}
WORD = {"ok": "QORUNUR", "busy": "NÜSXƏ GƏLİR", "warn": "DİQQƏT", "alert": "HÜCUM", "off": ""}

# Буквы, которых нет во встроенном шрифте framebuf (8x8, по строкам, бит 7 — левый)
GLYPHS = {
    "ə": b"\x00\x00\x78\x04\xfc\x84\x78\x00", "Ə": b"\x78\x04\x04\xfc\x84\x84\x78\x00",
    "ü": b"\x48\x00\x84\x84\x84\x8c\x74\x00", "Ü": b"\x48\x00\x84\x84\x84\x84\x78\x00",
    "ö": b"\x48\x00\x78\x84\x84\x84\x78\x00", "Ö": b"\x48\x00\x78\x84\x84\x84\x78\x00",
    "ş": b"\x00\x7c\x80\x78\x04\xf8\x10\x30", "Ş": b"\x78\x84\x80\x78\x04\xf8\x10\x30",
    "ç": b"\x00\x78\x84\x80\x84\x78\x10\x30", "Ç": b"\x78\x84\x80\x80\x84\x78\x10\x30",
    "ğ": b"\x48\x30\x7c\x84\x84\x7c\x04\x78", "Ğ": b"\x48\x30\x78\x80\x9c\x84\x78\x00",
    "ı": b"\x00\x00\x30\x10\x10\x10\x38\x00", "İ": b"\x10\x00\x38\x10\x10\x10\x38\x00",
    "°": b"\x30\x48\x30\x00\x00\x00\x00\x00", "✓": b"\x00\x01\x02\x04\x88\x50\x20\x00",
}
_cell = bytearray(8)
_cellfb = framebuf.FrameBuffer(_cell, 8, 8, framebuf.MONO_HLSB)


def draw_char(fb, ch, x, y, s, c):
    g = GLYPHS.get(ch)
    if g:
        _cell[:] = g
    else:
        _cellfb.fill(0)
        _cellfb.text(ch if ord(ch) < 128 else "?", 0, 0, 1)
    for yy in range(8):
        row = _cell[yy]
        if not row:
            continue
        xx = 0
        while xx < 8:                       # сливаем соседние точки в одну полосу — быстрее
            if row & (0x80 >> xx):
                x2 = xx
                while x2 + 1 < 8 and row & (0x80 >> (x2 + 1)):
                    x2 += 1
                fb.fill_rect(x + xx * s, y + yy * s, (x2 - xx + 1) * s, s, c)
                xx = x2 + 1
            else:
                xx += 1


def draw_text(fb, t, x, y, s, c, maxw=None):
    w = 8 * s
    lim = fb.width if maxw is None else x + maxw
    for ch in t:
        if x + w > lim + w // 2:
            break
        draw_char(fb, ch, x, y, s, c)
        x += w


def text_w(t, s):
    return len(t) * 8 * s


def draw_icon(fb, name, x, y, k, c):
    """Иконка в квадрате 16k×16k."""
    def L(x1, y1, x2, y2):
        for d in range(k + 1):
            fb.line(x + x1 * k + d, y + y1 * k, x + x2 * k + d, y + y2 * k, c)
            fb.line(x + x1 * k, y + y1 * k + d, x + x2 * k, y + y2 * k + d, c)
    if name == "ok":
        L(1, 8, 5, 12); L(5, 12, 14, 3)
    elif name == "warn":
        L(8, 1, 15, 14); L(15, 14, 1, 14); L(1, 14, 8, 1)
        fb.fill_rect(x + 7 * k + k // 2, y + 5 * k, k, 5 * k, c)
        fb.fill_rect(x + 7 * k + k // 2, y + 11 * k, k, k, c)
    elif name == "alert":
        fb.fill_rect(x + k, y + k, 14 * k, 14 * k, c)
        fb.fill_rect(x + 7 * k, y + 3 * k, 2 * k, 7 * k, DARK)
        fb.fill_rect(x + 7 * k, y + 11 * k, 2 * k, 2 * k, DARK)
    elif name == "busy":
        fb.fill_rect(x + 7 * k, y + 3 * k, 2 * k, 11 * k, c)
        L(7, 2, 2, 7); L(8, 2, 13, 7)
    elif name == "offline":
        L(2, 2, 13, 13); L(13, 2, 2, 13)


class Box:
    def __init__(self):
        self.lcd = LCD(ORIENTATION)
        self.W, self.H = self.lcd.width, self.lcd.height
        self.portrait = self.H > self.W
        self.key = Pin(14, Pin.IN, Pin.PULL_UP)
        self.boot_key = Pin(0, Pin.IN, Pin.PULL_UP)
        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN)
        self.rx = bytearray()
        self.msg = None
        self.last_rx = None
        self.t0 = time.ticks_ms()
        self.last_event = self.t0
        self.prev = (1, 1)
        self.prev_state = None
        self.page_i = 0
        self.page_t = self.t0
        self.drawn = None
        self.bright = BRIGHT

    # ---- приём от ПК ----
    def read_serial(self):
        while self.poll.poll(0):
            b = sys.stdin.buffer.read(1)
            if not b:
                break
            if b == b"\n":
                self.handle(bytes(self.rx))
                self.rx = bytearray()
            elif b != b"\r" and len(self.rx) < 4096:
                self.rx += b

    def handle(self, raw):
        try:
            m = json.loads(raw.decode())
        except Exception:
            return
        if not isinstance(m, dict):
            return
        if m.get("cmd") == "ping":
            print("PONG")
            return
        self.msg = m
        self.last_rx = time.ticks_ms()
        if m.get("contrast") is not None:
            self.bright = max(20, min(255, int(m["contrast"]) * 2))
        if m.get("state") != self.prev_state:
            self.prev_state = m.get("state")
            self.wake()

    def wake(self):
        self.last_event = time.ticks_ms()

    def current(self):
        now = time.ticks_ms()
        off = [{"icon": "offline", "big": "PC ?", "lines": ["Kompüter cavab", "vermir"]}]
        if self.msg is None:
            if time.ticks_diff(now, self.t0) > OFFLINE_SEC * 1000:
                return "warn", "BITRONE BOX", off
            return "busy", "BITRONE BOX", [{"icon": "busy", "big": "Start", "lines": ["Gözləyir..."]}]
        title = self.msg.get("title", "BITRONE BOX")
        if time.ticks_diff(now, self.last_rx) > OFFLINE_SEC * 1000:
            return "warn", title, off
        return self.msg.get("state", "ok"), title, self.msg.get("pages") or [{}]

    # ---- кнопки ----
    def buttons(self, state):
        k, b = self.key.value(), self.boot_key.value()
        if k == 0 and self.prev[0] == 1:
            self.wake()
            if state == "alert":
                print("ACK")
        if b == 0 and self.prev[1] == 1:
            self.wake()
            self.page_i += 1
            self.page_t = time.ticks_ms()
            self.drawn = None
        self.prev = (k, b)

    # ---- отрисовка ----
    def header(self, state, title, color):
        fb = self.lcd
        fb.fill_rect(0, 0, self.W, 28, color)
        if self.portrait:
            draw_text(fb, "BITRONE", (self.W - text_w("BITRONE", 2)) // 2, 6, 2, DARK)
        else:
            draw_text(fb, title[:12], 8, 6, 2, DARK)
            w = WORD.get(state, "")
            if w:
                draw_text(fb, w, self.W - 8 - text_w(w, 1), 10, 1, DARK)

    def dots(self, n, i, color, y):
        if n < 2:
            return
        x = (self.W - (n * 12 - 4)) // 2
        for k in range(n):
            if k == i:
                self.lcd.fill_rect(x + k * 12, y, 8, 8, color)
            else:
                self.lcd.rect(x + k * 12, y, 8, 8, TRACK)

    def render(self, state, title, pages, blink, tick):
        fb = self.lcd
        n = len(pages)
        page = pages[self.page_i % n]
        color = COL.get(state, COL["off"])
        alert = state == "alert"
        bg = (COL["alert"] if blink else DARK) if alert else BG
        fg = FG
        fb.fill(bg)
        if not alert:
            self.header(state, title, color)
        icon = page.get("icon")
        icol = FG if alert else (COL.get(icon, color) if icon in COL else color)
        if icon == "offline":
            icol = COL["warn"]
        big = page.get("big") or ""
        lines = list(page.get("lines") or [])
        if self.portrait:
            unit = ""
            if " " in big:
                big, unit = big.split(" ", 1)
            y = 40 if not alert else 16
            if icon:
                draw_icon(fb, icon, (self.W - 48) // 2, y, 3, icol)
                y += 58
            if big:
                s = 6 if len(big) <= 3 else (4 if len(big) <= 5 else 3)
                draw_text(fb, big, (self.W - text_w(big, s)) // 2, y, s, fg)
                y += 8 * s + 6
            if unit:
                draw_text(fb, unit, (self.W - text_w(unit, 2)) // 2, y, 2, fg)
                y += 26
            y += 8
            for t in lines[:4]:
                if len(t) > 10:
                    s = 1
                else:
                    s = 2
                draw_text(fb, t, max(2, (self.W - text_w(t, s)) // 2), y, s, MUTE if not alert else FG)
                y += 8 * s + 8
            self.dots(n, self.page_i % n, color, self.H - 14)
        else:
            top = 4 if alert else 36
            if big:
                x = 10
                if icon:
                    draw_icon(fb, icon, 10, top + 4, 3, icol)
                    x = 70
                s = 5 if text_w(big, 5) <= self.W - x - 6 else 4
                draw_text(fb, big, x, top + 4 + (48 - 8 * s) // 2, s, fg)
                y = top + 62
            else:
                y = top + 6
            for t in lines[:4 if not big else 2]:
                if text_w(t, 2) <= self.W - 20:
                    draw_text(fb, t, 10, y, 2, MUTE if not alert else FG)
                    y += 24
                else:   # длинная строка — бегущая
                    span = text_w(t, 2) - (self.W - 20)
                    off = (tick * 4) % (span + 120)
                    off = max(0, min(span, off - 60))
                    draw_text(fb, t, 10 - off, y, 2, MUTE if not alert else FG, maxw=self.W)
                    y += 24
            self.dots(n, self.page_i % n, color, self.H - 12)
        if state == "busy":           # бегущая полоска приёма копии
            w = 60
            x = (tick * 12) % (self.W + w) - w
            fb.fill_rect(max(0, x), self.H - 3, w, 3, COL["busy"])
        fb.show()

    def run(self):
        tick = 0
        while True:
            self.read_serial()
            state, title, pages = self.current()
            self.buttons(state)
            now = time.ticks_ms()
            if time.ticks_diff(now, self.page_t) > PAGE_SEC * 1000:
                self.page_i += 1
                self.page_t = now
            blink = (tick // 5) % 2 == 0
            long_line = any(len(t) * 16 > self.W - 20 for p in pages for t in (p.get("lines") or []))
            key = (state, title, json.dumps(pages), self.page_i % len(pages),
                   blink if state == "alert" else 0)
            if key != self.drawn or state == "busy" or long_line:
                self.render(state, title, pages, blink, tick)
                self.drawn = key
            want = DIM if (DIM_SEC and state in ("ok", "busy") and
                           time.ticks_diff(now, self.last_event) > DIM_SEC * 1000) else self.bright
            self.lcd.backlight(want)
            tick += 1
            time.sleep_ms(100)


Box().run()
