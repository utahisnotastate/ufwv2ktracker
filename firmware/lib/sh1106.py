# Save this file as /lib/sh1106.py
# A MicroPython driver for the SH1106 OLED display
# Based on the official micropython-lib

from micropython import const
import time
import framebuf

# Register definitions
SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)


class SH1106(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc, rotate=0):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)

        # Add a 1-pixel column offset for SH1106
        self.page_offset = 2

        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.rotate = rotate
        self.init_display()

    def init_display(self):
        self.poweroff()
        self.write_cmd(SET_DISP_CLK_DIV)
        self.write_cmd(0x80)
        self.write_cmd(SET_MUX_RATIO)
        self.write_cmd(self.height - 1)
        self.write_cmd(SET_DISP_OFFSET)
        self.write_cmd(0x00)
        self.write_cmd(SET_DISP_START_LINE | 0x00)
        self.write_cmd(SET_CHARGE_PUMP)
        self.write_cmd(0x14 if self.external_vcc else 0x10)
        self.write_cmd(SET_MEM_ADDR)
        self.write_cmd(0x00)  # Horizontal addressing mode

        if self.rotate == 0:
            self.write_cmd(SET_SEG_REMAP | 0x01)  # Column 127 mapped to SEG0
            self.write_cmd(SET_COM_OUT_DIR | 0x08)  # Scan from COM[N-1] to COM0
        elif self.rotate == 180:
            self.write_cmd(SET_SEG_REMAP | 0x00)  # Column 0 mapped to SEG0
            self.write_cmd(SET_COM_OUT_DIR | 0x00)  # Scan from COM0 to COM[N-1]
        else:
            raise ValueError("rotate must be 0 or 180")

        self.write_cmd(SET_COM_PIN_CFG)
        self.write_cmd(0x12 if self.height == 64 else 0x02)
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(0xCF)
        self.write_cmd(SET_PRECHARGE)
        self.write_cmd(0xF1 if self.external_vcc else 0x22)
        self.write_cmd(SET_VCOM_DESEL)
        self.write_cmd(0x40)
        self.write_cmd(SET_ENTIRE_ON)  # output follows RAM
        self.write_cmd(SET_NORM_INV)  # not inverted
        self.fill(0)
        self.show()
        self.poweron()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def show(self):
        for page in range(self.pages):
            self.write_cmd(0xB0 + page)  # Set page address
            self.write_cmd(self.page_offset & 0x0F)  # Set lower column start
            self.write_cmd(0x10 | (self.page_offset >> 4))  # Set upper column start

            start = page * self.width
            end = start + self.width
            self.write_data(self.buffer[start:end])

    def write_cmd(self, cmd):
        raise NotImplementedError

    def write_data(self, buf):
        raise NotImplementedError


class SH1106_I2C(SH1106):
    def __init__(self, width, height, i2c, res=None, addr=0x3C, rotate=0, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)

        if res is not None:
            res.init(res.OUT, value=0)
            time.sleep_ms(1)
            res.value(1)

        super().__init__(width, height, external_vcc, rotate)

    def write_cmd(self, cmd):
        self.temp[0] = 0x00  # Co=0, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        data = bytearray(1 + len(buf))
        data[0] = 0x40  # Co=0, D/C#=1
        data[1:] = buf
        self.i2c.writeto(self.addr, data)
