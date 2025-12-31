import machine
import time
import struct
import framebuf
from micropython import const

# --- DRIVER MINIMO ST7789 ---
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
        self.write_data(bytearray([0x55]))
        
        # Mantenemos la rotación que te funcionó (0xC0)
        self.write_cmd(ST7789_MADCTL)
        self.write_data(bytearray([0xC0])) 
        
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
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(buffer)
        self.cs.value(1)

# --- HARDWARE ---
spi = machine.SPI(1, baudrate=40_000_000, polarity=1, phase=1, sck=machine.Pin(10), mosi=machine.Pin(11))
display = ST7789(spi, 240, 320, machine.Pin(12), machine.Pin(8), machine.Pin(9), machine.Pin(13))

# --- DEFINICIÓN DE COLORES TEÓRICOS ---
# RGB565: 5 bits Rojo, 6 bits Verde, 5 bits Azul
RED_DEF   = 0xF800  # 11111 000000 00000
GREEN_DEF = 0x07E0  # 00000 111111 00000
BLUE_DEF  = 0x001F  # 00000 000000 11111
BLACK     = 0x0000
WHITE     = 0xFFFF

# --- DIBUJADO ---
buffer = bytearray(240 * 320 * 2)
fbuf = framebuf.FrameBuffer(buffer, 240, 320, framebuf.RGB565)

fbuf.fill(BLACK)

# Escribimos el nombre del color usando el valor hexadecimal que DEBERÍA ser ese color
fbuf.text("TEST DE COLOR", 60, 20, WHITE)

fbuf.rect(40, 60, 160, 30, RED_DEF, True)
fbuf.text("ROJO (0xF800)", 50, 70, BLACK)

fbuf.rect(40, 110, 160, 30, GREEN_DEF, True)
fbuf.text("VERDE (0x07E0)", 50, 120, BLACK)

fbuf.rect(40, 160, 160, 30, BLUE_DEF, True)
fbuf.text("AZUL (0x001F)", 50, 170, WHITE)

display.show_buffer(buffer)
