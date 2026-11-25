# Bitrone Box — экран и световая полоса на подставке.
# Плата RP2040-Zero (MicroPython), питание и данные — один USB от мини-ПК.
# ПК (служба bitrone-box-status) раз в ~10 с шлёт строку JSON:
#   {"state":"ok","title":"BITRONE BX-0001",
#    "pages":[{"icon":"ok","big":"12 dəq","lines":["Son nüsxə: 14:32","Tam: Bazar 02:10"]}]}
# state: ok | busy | warn | alert | off — цвет полосы и вид экрана.
# Кнопка (по желанию) будит экран; в состоянии alert ещё и шлёт ПК "ACK".
import sys, time, json, select, framebuf
from machine import Pin, I2C
import neopixel
from oled import OLED

# ---- настройки железа ----
I2C_ID, SDA, SCL = 0, 4, 5
OLED_DRIVER = "sh1106"      # "ssd1306" для 0.96"
OLED_FLIP = False           # True, если экран стоит вверх ногами
LED_PIN, LED_COUNT = 6, 10
LED_MAX = 60                # яркость полосы 0..255 (60 — мягко, ток < 150 мА)
BUTTON_PIN = 7              # кнопка на GND; None — без кнопки
ONBOARD_LED = 16            # встроенный светодиод RP2040-Zero повторяет цвет

# ---- поведение ----
PAGE_SEC = 5                # смена страниц
OFFLINE_SEC = 120           # нет данных от ПК столько секунд — «ПК не отвечает»
SAVER_SEC = 0               # гасить экран через N с без событий (0 — не гасить)
SHIFT_SEC = 60              # сдвиг картинки на 1-2 px против выгорания
CONTRAST_DAY = 90

# Буквы, которых нет во встроенном шрифте framebuf (8x8, по строкам, бит 7 — левый)
GLYPHS = {
    "ə": b"\x00\x00\x78\x04\xfc\x84\x78\x00",
    "Ə": b"\x78\x04\x04\xfc\x84\x84\x78\x00",
    "ü": b"\x48\x00\x84\x84\x84\x8c\x74\x00",
    "Ü": b"\x48\x00\x84\x84\x84\x84\x78\x00",
    "ö": b"\x48\x00\x78\x84\x84\x84\x78\x00",
    "Ö": b"\x48\x00\x78\x84\x84\x84\x78\x00",
    "ş": b"\x00\x7c\x80\x78\x04\xf8\x10\x30",
    "Ş": b"\x78\x84\x80\x78\x04\xf8\x10\x30",
    "ç": b"\x00\x78\x84\x80\x84\x78\x10\x30",
    "Ç": b"\x78\x84\x80\x80\x84\x78\x10\x30",
    "ğ": b"\x48\x30\x7c\x84\x84\x7c\x04\x78",
    "Ğ": b"\x48\x30\x78\x80\x9c\x84\x78\x00",
    "ı": b"\x00\x00\x30\x10\x10\x10\x38\x00",
    "İ": b"\x10\x00\x38\x10\x10\x10\x38\x00",
    "°": b"\x30\x48\x30\x00\x00\x00\x00\x00",
}
_cell = bytearray(8)
_cellfb = framebuf.FrameBuffer(_cell, 8, 8, framebuf.MONO_HLSB)

COLORS = {"ok": (0, 255, 40), "busy": (30, 120, 255), "warn": (255, 120, 0),
          "alert": (255, 0, 0), "off": (0, 0, 0)}


def draw_char(fb, ch, x, y, scale):
    g = GLYPHS.get(ch)
    if g:
        _cell[:] = g
    else:
        _cellfb.fill(0)
        _cellfb.text(ch if ord(ch) < 128 else "?", 0, 0, 1)
    if scale == 1:
        fb.blit(_cellfb, x, y, 0)
        return
    for yy in range(8):
        row = _cell[yy]
        for xx in range(8):
            if row & (0x80 >> xx):
                fb.fill_rect(x + xx * scale, y + yy * scale, scale, scale, 1)


def draw_text(fb, s, x, y, scale=1):
    w = 8 * scale
    for ch in s:
        if x > 127:
            break
        if x > -w:
            draw_char(fb, ch, x, y, scale)
        x += w


def draw_icon(fb, name, x, y):
    L = fb.line
    if name == "ok":
        for d in (0, 1):
            L(x + 1, y + 8 + d, x + 5, y + 12 + d, 1)
            L(x + 5, y + 12 + d, x + 14, y + 3 + d, 1)
    elif name == "warn":
        L(x + 8, y + 1, x + 15, y + 14, 1); L(x + 15, y + 14, x + 1, y + 14, 1); L(x + 1, y + 14, x + 8, y + 1, 1)
        fb.vline(x + 8, y + 5, 5, 1); fb.pixel(x + 8, y + 12, 1)
    elif name == "alert":
        fb.fill_rect(x + 1, y + 1, 14, 14, 1)
        fb.fill_rect(x + 7, y + 3, 2, 7, 0); fb.fill_rect(x + 7, y + 11, 2, 2, 0)
    elif name == "busy":
        fb.vline(x + 8, y + 2, 12, 1); fb.vline(x + 7, y + 2, 12, 1)
        L(x + 7, y + 2, x + 2, y + 7, 1); L(x + 8, y + 2, x + 13, y + 7, 1)
    elif name == "offline":
        for d in (0, 1):
            L(x + 2 + d, y + 2, x + 13 + d, y + 13, 1); L(x + 13 + d, y + 2, x + 2 + d, y + 13, 1)


class Box:
    def __init__(self):
        self.oled = OLED(I2C(I2C_ID, sda=Pin(SDA), scl=Pin(SCL), freq=400000),
                         driver=OLED_DRIVER, flip=OLED_FLIP, contrast=CONTRAST_DAY)
        self.np = neopixel.NeoPixel(Pin(LED_PIN), LED_COUNT)
        self.onboard = neopixel.NeoPixel(Pin(ONBOARD_LED), 1) if ONBOARD_LED is not None else None
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP) if BUTTON_PIN is not None else None
        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN)
        self.rx = bytearray()
        self.msg = None
        self.last_rx = None
        self.boot = time.ticks_ms()
        self.last_event = self.boot
        self.screen_on = True
        self.btn_prev = 1
        self.prev_state = None

    # ---- приём строк от ПК ----
    def read_serial(self):
        while self.poll.poll(0):
            b = sys.stdin.buffer.read(1)
            if not b:
                break
            if b == b"\n":
                self.handle(bytes(self.rx))
                self.rx = bytearray()
            elif b != b"\r" and len(self.rx) < 2048:
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
            self.oled.contrast(int(m["contrast"]))
        if m.get("state") != self.prev_state:
            self.prev_state = m.get("state")
            self.wake()

    def wake(self):
        self.last_event = time.ticks_ms()
        if not self.screen_on:
            self.oled.power(True)
            self.screen_on = True

    # ---- текущее состояние ----
    def current(self):
        now = time.ticks_ms()
        if self.msg is None:
            if time.ticks_diff(now, self.boot) > OFFLINE_SEC * 1000:
                return "warn", "BITRONE BOX", [{"icon": "offline", "big": "PC ?", "lines": ["Kompüter cavab", "vermir"]}]
            return "busy", "BITRONE BOX", [{"icon": "busy", "big": "Start", "lines": ["Gözləyir..."]}]
        if time.ticks_diff(now, self.last_rx) > OFFLINE_SEC * 1000:
            return "warn", self.msg.get("title", "BITRONE BOX"), [
                {"icon": "offline", "big": "PC ?", "lines": ["Kompüter cavab", "vermir"]}]
        return self.msg.get("state", "ok"), self.msg.get("title", "BITRONE BOX"), self.msg.get("pages") or [{}]

    # ---- экран ----
    def render(self, title, page, tick):
        fb = self.oled
        fb.fill(0)
        sec = time.ticks_diff(time.ticks_ms(), self.boot) // 1000
        k = (sec // SHIFT_SEC) % 4
        ox, oy = (0, 1, 1, 0)[k], (0, 0, 1, 1)[k]
        draw_text(fb, title[:16], ox, oy)
        fb.hline(ox, oy + 10, 126, 1)
        lines = list(page.get("lines") or [])
        if page.get("big"):
            draw_icon(fb, page.get("icon"), ox, oy + 15)
            draw_text(fb, page["big"][:6], ox + 20, oy + 15, 2)
            ys = (oy + 38, oy + 50)
        else:
            ys = (oy + 16, oy + 28, oy + 40, oy + 52)
        for y, s in zip(ys, lines):
            if len(s) > 16:     # бегущая строка для длинных путей
                span = (len(s) - 15) * 8
                off = (tick * 2) % (span + 64)
                off = max(0, min(span, off - 32))
                draw_text(fb, s, ox - off, y)
            else:
                draw_text(fb, s, ox, y)
        fb.show()

    # ---- полоса ----
    def leds(self, state, tick):
        r, g, b = COLORS.get(state, COLORS["off"])
        n = LED_COUNT
        out = []
        for i in range(n):
            if state == "busy":           # бегущий огонёк с хвостом
                d = (tick // 2 - i) % n
                k = (255, 90, 25)[d] if d < 3 else 0
            elif state == "alert":        # частое мигание
                k = 255 if (tick // 4) % 2 == 0 else 0
            elif state == "warn":         # медленное «дыхание»
                p = tick % 60
                k = 40 + (215 * (p if p < 30 else 60 - p)) // 30
            else:
                k = 255
            s = k * LED_MAX // 255
            out.append((r * s // 255, g * s // 255, b * s // 255))
        for i, c in enumerate(out):
            self.np[i] = c
        self.np.write()
        if self.onboard:
            self.onboard[0] = out[0]
            self.onboard.write()

    def button(self, state):
        if not self.btn:
            return
        v = self.btn.value()
        if v == 0 and self.btn_prev == 1:
            self.wake()
            if state == "alert":
                print("ACK")
        self.btn_prev = v

    def run(self):
        tick = 0
        page_i, page_t = 0, time.ticks_ms()
        while True:
            self.read_serial()
            state, title, pages = self.current()
            self.button(state)
            if time.ticks_diff(time.ticks_ms(), page_t) > PAGE_SEC * 1000:
                page_i, page_t = page_i + 1, time.ticks_ms()
            page = pages[page_i % len(pages)]
            if state == "alert":
                self.oled.cmd(0xA7 if (tick // 10) % 2 == 0 else 0xA6)   # экран мигает инверсией
                self.wake()
            elif tick % 20 == 0:
                self.oled.cmd(0xA6)
            if SAVER_SEC and state in ("ok", "busy") and \
                    time.ticks_diff(time.ticks_ms(), self.last_event) > SAVER_SEC * 1000:
                if self.screen_on:
                    self.oled.power(False)
                    self.screen_on = False
            elif tick % 5 == 0 and self.screen_on:
                self.render(title, page, tick // 5)
            self.leds(state, tick)
            tick += 1
            time.sleep_ms(50)


Box().run()
