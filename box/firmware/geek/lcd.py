# Драйвер экрана RP2040-GEEK: ST7789, 1.14" 240x135 IPS, SPI1.
# Пины (по схеме Waveshare / CircuitPython): SCK GP10, MOSI GP11, CS GP9, DC GP8, RST GP12, подсветка GP25.
import time
import framebuf
from machine import Pin, SPI, PWM

# Положение картинки: (MADCTL, сдвиг X, сдвиг Y). Если изображение вверх ногами —
# ставьте ROTATE = 180 в main.py; если сдвинуто на пиксель — поправьте сдвиг.
MODES = {0: (0x70, 40, 53), 180: (0xA0, 40, 52)}


def rgb(r, g, b):
    """Цвет RGB565 с перестановкой байт (framebuf хранит little-endian, ST7789 ждёт big-endian)."""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


class LCD(framebuf.FrameBuffer):
    def __init__(self, rotate=0, bgr=False):
        self.width, self.height = 240, 135
        self.buf = bytearray(self.width * self.height * 2)
        super().__init__(self.buf, self.width, self.height, framebuf.RGB565)
        self.spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(10), mosi=Pin(11))
        self.cs = Pin(9, Pin.OUT, value=1)
        self.dc = Pin(8, Pin.OUT, value=1)
        self.rst = Pin(12, Pin.OUT, value=1)
        self.bl = PWM(Pin(25))
        self.bl.freq(1000)
        madctl, self.xo, self.yo = MODES.get(rotate, MODES[0])
        if bgr:
            madctl |= 0x08
        self.rst(0); time.sleep_ms(20); self.rst(1); time.sleep_ms(120)
        self.cmd(0x01); time.sleep_ms(150)          # программный сброс
        self.cmd(0x11); time.sleep_ms(120)          # выход из сна
        self.cmd(0x3A, b"\x55")                      # 16 бит на пиксель
        self.cmd(0x36, bytes((madctl,)))
        self.cmd(0x21)                               # инверсия — нужна для IPS-панели
        self.cmd(0x13)
        self.cmd(0x29); time.sleep_ms(20)            # экран включён
        self.fill(0)
        self.show()
        self.backlight(160)

    def cmd(self, c, data=None):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes((c,)))
        if data:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def backlight(self, v):
        """Яркость подсветки 0..255."""
        v = max(0, min(255, int(v)))
        self.bl.duty_u16(v * 257)

    def show(self):
        x0, y0 = self.xo, self.yo
        x1, y1 = x0 + self.width - 1, y0 + self.height - 1
        self.cmd(0x2A, bytes((x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)))
        self.cmd(0x2B, bytes((y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)))
        self.cs(0)
        self.dc(0)
        self.spi.write(b"\x2C")
        self.dc(1)
        self.spi.write(self.buf)
        self.cs(1)
