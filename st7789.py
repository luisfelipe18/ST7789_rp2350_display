# st7789.py - Controlador de pantalla para Waveshare RP2350-Zero
import machine
import time
import struct
from micropython import const

# Comandos ST7789
ST7789_SWRESET = const(0x01)
ST7789_SLPOUT  = const(0x11)
ST7789_NORON   = const(0x13)
ST7789_INVON   = const(0x21)
ST7789_DISPON  = const(0x29)
ST7789_CASET   = const(0x2A)
ST7789_RASET   = const(0x2B)
ST7789_RAMWR   = const(0x2C)
ST7789_MADCTL  = const(0x36)
ST7789_COLMOD  = const(0x3A)

class ST7789:
    def __init__(self, spi, width, height, reset, dc, cs, backlight=None):
        self.width = width
        self.height = height
        self.spi = spi
        self.reset = reset
        self.dc = dc
        self.cs = cs
        self.backlight = backlight
        self.cs.init(machine.Pin.OUT, value=1)
        self.dc.init(machine.Pin.OUT, value=0)
        self.reset.init(machine.Pin.OUT, value=1)
        if self.backlight:
            self.backlight.init(machine.Pin.OUT, value=1)
        self.init_display()

    def write_cmd(self, cmd):
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytearray([cmd]))
        self.cs.value(1)

    def write_data(self, data):
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(data)
        self.cs.value(1)

    def init_display(self):
        self.reset.value(1)
        time.sleep_ms(50)
        self.reset.value(0)
        time.sleep_ms(50)
        self.reset.value(1)
        time.sleep_ms(150)
        self.write_cmd(ST7789_SWRESET)
        time.sleep_ms(150)
        self.write_cmd(ST7789_SLPOUT)
        time.sleep_ms(255)
        self.write_cmd(ST7789_COLMOD)
        self.write_data(bytearray([0x55])) # 16-bit RGB565
        self.write_cmd(ST7789_INVON)
        self.write_cmd(ST7789_NORON)
        self.write_cmd(ST7789_DISPON)
        
    def set_window(self, x0, y0, x1, y1):
        self.write_cmd(ST7789_CASET)
        self.write_data(struct.pack(">HH", x0, x1))
        self.write_cmd(ST7789_RASET)
        self.write_data(struct.pack(">HH", y0, y1))
        self.write_cmd(ST7789_RAMWR)

    def show_buffer(self, buffer):
        # Envia el buffer completo a la pantalla
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(buffer)
        self.cs.value(1)

    def rotate(self, rotation):
        # 0:Portrait, 1:Land, 2:PortInv, 3:LandInv
        madctl_val = 0
        if rotation == 0:   madctl_val = 0x00; self.width, self.height = 240, 320
        elif rotation == 1: madctl_val = 0x60; self.width, self.height = 320, 240
        elif rotation == 2: madctl_val = 0xC0; self.width, self.height = 240, 320
        elif rotation == 3: madctl_val = 0xA0; self.width, self.height = 320, 240
        self.write_cmd(ST7789_MADCTL)
        self.write_data(bytearray([madctl_val]))