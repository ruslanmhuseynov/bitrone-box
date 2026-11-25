# Драйвер экрана LILYGO T-Display-S3: ST7789, 1.9" 170x320, 8-битная параллельная шина (i80).
# Стандартный MicroPython для ESP32-S3 не умеет i80, поэтому байты выдаём прямой записью
# в регистры GPIO из viper-функции (~50–100 мс на полный кадр — для экрана статуса достаточно).
# Пины по схеме LILYGO: D0..D7 = 39,40,41,42,45,46,47,48; WR 8, RD 9, DC 7, CS 6, RES 5,
# подсветка 38, питание экрана 15.
import time
import array
import framebuf
import micropython
from machine import Pin, PWM

DATA_PINS = (39, 40, 41, 42, 45, 46, 47, 48)   # все в банке GPIO32..48
PIN_WR, PIN_RD, PIN_DC, PIN_CS, PIN_RST, PIN_BL, PIN_PWR = 8, 9, 7, 6, 5, 38, 15

# регистры GPIO ESP32-S3
GPIO_OUT_W1TS, GPIO_OUT_W1TC = 0x60004008, 0x6000400C       # GPIO0..31
GPIO_OUT1_W1TS, GPIO_OUT1_W1TC = 0x60004014, 0x60004018     # GPIO32..53

# ориентация: (MADCTL, ширина, высота, сдвиг X, сдвиг Y) — панель 170 px в RAM 240 px контроллера
MODES = {
    "landscape": (0xA0, 320, 170, 0, 35),
    "landscape_flip": (0x60, 320, 170, 0, 35),
    "portrait": (0x00, 170, 320, 35, 0),
    "portrait_flip": (0xC0, 170, 320, 35, 0),
}


def rgb(r, g, b):
    """RGB565 с перестановкой байт: framebuf хранит little-endian, контроллер ждёт старший байт первым."""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


@micropython.viper
def _bus_write(data: ptr8, n: int, table: ptr32, regs: ptr32):
    s1 = ptr32(regs[0])     # OUT1_W1TS
    c1 = ptr32(regs[1])     # OUT1_W1TC
    s0 = ptr32(regs[2])     # OUT_W1TS
    c0 = ptr32(regs[3])     # OUT_W1TC
    dmask = regs[4]
    wr = regs[5]
    i = 0
    while i < n:
        v = table[data[i]]
        c1[0] = dmask ^ v   # гасим нулевые биты
        s1[0] = v           # ставим единичные
        c0[0] = wr          # строб WR: низкий...
        s0[0] = wr          # ...и высокий — контроллер защёлкивает байт
        i += 1


class LCD(framebuf.FrameBuffer):
    def __init__(self, mode="landscape", bgr=False):
        madctl, self.width, self.height, self.xo, self.yo = MODES.get(mode, MODES["landscape"])
        self.buf = bytearray(self.width * self.height * 2)
        super().__init__(self.buf, self.width, self.height, framebuf.RGB565)

        self.pwr = Pin(PIN_PWR, Pin.OUT, value=1)
        self.rd = Pin(PIN_RD, Pin.OUT, value=1)
        self.wr = Pin(PIN_WR, Pin.OUT, value=1)
        self.dc = Pin(PIN_DC, Pin.OUT, value=1)
        self.cs = Pin(PIN_CS, Pin.OUT, value=1)
        self.rst = Pin(PIN_RST, Pin.OUT, value=1)
        self.data = [Pin(p, Pin.OUT, value=0) for p in DATA_PINS]
        self.bl = PWM(Pin(PIN_BL), freq=2000)

        t = array.array("I", [0] * 256)
        for v in range(256):
            m = 0
            for i, p in enumerate(DATA_PINS):
                if v >> i & 1:
                    m |= 1 << (p - 32)
            t[v] = m
        self.table = t
        dmask = 0
        for p in DATA_PINS:
            dmask |= 1 << (p - 32)
        self.regs = array.array("I", [GPIO_OUT1_W1TS, GPIO_OUT1_W1TC, GPIO_OUT_W1TS, GPIO_OUT_W1TC,
                                      dmask, 1 << PIN_WR])

        if bgr:
            madctl |= 0x08
        self.rst(0); time.sleep_ms(20); self.rst(1); time.sleep_ms(120)
        self.cmd(0x01); time.sleep_ms(150)          # программный сброс
        self.cmd(0x11); time.sleep_ms(120)          # выход из сна
        self.cmd(0x3A, b"\x55")                      # 16 бит на пиксель
        self.cmd(0x36, bytes((madctl,)))
        self.cmd(0xB2, b"\x0c\x0c\x00\x33\x33")      # porch
        self.cmd(0xB7, b"\x35")                      # gate
        self.cmd(0xBB, b"\x19")                      # VCOM
        self.cmd(0xC2, b"\x01")
        self.cmd(0xC3, b"\x12")
        self.cmd(0xC4, b"\x20")
        self.cmd(0xC6, b"\x0f")                      # 60 Гц
        self.cmd(0xD0, b"\xa4\xa1")
        self.cmd(0x21)                               # инверсия — нужна для IPS
        self.cmd(0x13)
        self.cmd(0x29); time.sleep_ms(20)
        self.fill(0)
        self.show()
        self.backlight(170)

    def _write(self, b):
        _bus_write(b, len(b), self.table, self.regs)

    def cmd(self, c, data=None):
        self.cs(0)
        self.dc(0)
        self._write(bytes((c,)))
        if data:
            self.dc(1)
            self._write(data)
        self.cs(1)

    def backlight(self, v):
        """Яркость 0..255."""
        v = max(0, min(255, int(v)))
        self.bl.duty_u16(v * 257)

    def show(self):
        x0, y0 = self.xo, self.yo
        x1, y1 = x0 + self.width - 1, y0 + self.height - 1
        self.cmd(0x2A, bytes((x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)))
        self.cmd(0x2B, bytes((y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)))
        self.cs(0)
        self.dc(0)
        self._write(b"\x2c")
        self.dc(1)
        self._write(self.buf)
        self.cs(1)
