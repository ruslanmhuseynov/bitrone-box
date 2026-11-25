# Драйвер OLED 128x64 по I2C: SH1106 (1.3") и SSD1306 (0.96").
# Оба понимают постраничную адресацию; отличаются сдвигом колонок и накачкой.
import framebuf


class OLED(framebuf.FrameBuffer):
    def __init__(self, i2c, addr=0x3C, driver="sh1106", flip=False, contrast=60):
        self.i2c, self.addr = i2c, addr
        self.width, self.height = 128, 64
        self.col = 2 if driver == "sh1106" else 0
        self.buf = bytearray(self.width * self.height // 8)
        super().__init__(self.buf, self.width, self.height, framebuf.MONO_VLSB)
        seq = [0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40]
        seq += [0x8D, 0x14, 0x20, 0x02] if driver == "ssd1306" else [0xAD, 0x8B]
        seq += [0xA0 if flip else 0xA1, 0xC0 if flip else 0xC8,
                0xDA, 0x12, 0x81, contrast, 0xD9, 0x22, 0xDB, 0x35, 0xA4, 0xA6, 0xAF]
        for c in seq:
            self.cmd(c)
        self.fill(0)
        self.show()

    def cmd(self, c):
        self.i2c.writeto(self.addr, bytes((0x00, c)))

    def contrast(self, v):
        self.cmd(0x81)
        self.cmd(v)

    def power(self, on):
        self.cmd(0xAF if on else 0xAE)

    def show(self):
        mv = memoryview(self.buf)
        for page in range(8):
            self.cmd(0xB0 + page)
            self.cmd(self.col & 0x0F)
            self.cmd(0x10 | (self.col >> 4))
            self.i2c.writevto(self.addr, (b"\x40", mv[page * 128:(page + 1) * 128]))
