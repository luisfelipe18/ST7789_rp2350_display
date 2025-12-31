import machine
import time
import struct
import framebuf
from micropython import const

# --- Configuración del Driver ST7789 (Igual que antes, con mejoras para buffer) ---
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
        self.write_data(bytearray([0x55])) # 16-bit color
        self.write_cmd(ST7789_MADCTL)
        # self.write_data(bytearray([0x00])) # Orientación Vertical (Portrait)
        self.write_data(bytearray([0xC0])) # Orientación (0xC0 = Portrait Invertido / 180 grados)
        # self.write_data(bytearray([0x80])) # Espejo Vertical
        # self.write_data(bytearray([0x40])) # Orientación Espejo Horizontal.
        self.write_cmd(ST7789_INVON)
        self.write_cmd(ST7789_NORON)
        self.write_cmd(ST7789_DISPON)

    def set_window(self, x0, y0, x1, y1):
        self.write_cmd(ST7789_CASET)
        self.write_data(struct.pack(">HH", x0, x1))
        self.write_cmd(ST7789_RASET)
        self.write_data(struct.pack(">HH", y0, y1))
        self.write_cmd(ST7789_RAMWR)

    # Función nueva para enviar un buffer completo a pantalla
    def show_buffer(self, buffer):
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(buffer)
        self.cs.value(1)

# --- Configuración de Hardware ---

# Pantalla
spi = machine.SPI(1, baudrate=40_000_000, polarity=1, phase=1, sck=machine.Pin(10), mosi=machine.Pin(11))
display = ST7789(spi, 240, 320, machine.Pin(12), machine.Pin(8), machine.Pin(9), machine.Pin(13))

# Botones con Pull-UP (Se activan con valor 0 al presionar)
btn_char = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP) # Cambia letra
btn_next = machine.Pin(1, machine.Pin.IN, machine.Pin.PULL_UP) # Siguiente espacio

# --- Lógica de Texto ---

# Buffer de pantalla (En RAM del RP2350 caben 240x320x2 bytes = 153KB)
width = 240
height = 320
buffer = bytearray(width * height * 2)
# Creamos el objeto framebuf sobre ese array
fbuf = framebuf.FrameBuffer(buffer, width, height, framebuf.RGB565)

# Alfabeto disponible
chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789"
current_char_index = 0
message = ""

# Colores (RGB565)
WHITE = 0xFFFF
BLACK = 0x0000
GREEN = 0x07E0
RED   = 0xF800
BLUE  = 0x001F

print("Sistema listo. Escribe con los botones.")

last_char_press = 0
last_next_press = 0
debounce_time = 200 # ms

while True:
    now = time.ticks_ms()
    update_screen = False
    
    # Lógica Botón 1: Cambiar letra (GP0)
    if btn_char.value() == 0:
        if (now - last_char_press) > debounce_time:
            current_char_index += 1
            if current_char_index >= len(chars):
                current_char_index = 0
            last_char_press = now
            update_screen = True

    # Lógica Botón 2: Confirmar letra / Siguiente (GP1)
    if btn_next.value() == 0:
        if (now - last_next_press) > debounce_time:
            message += chars[current_char_index]
            # Opcional: Reiniciar a 'A' después de elegir? 
            # current_char_index = 0 
            last_next_press = now
            update_screen = True

    # Solo redibujamos si algo cambió para que sea fluido
    # (O la primera vez)
    if update_screen or (time.ticks_ms() % 1000) < 20: # Refresco forzado ocasional
        
        # 1. Limpiar pantalla (rellenar de negro)
        fbuf.fill(BLACK)
        
        # 2. Dibujar instrucciones y mensaje actual
        fbuf.text("TU MENSAJE:", 10, 10, GREEN)
        
        # Dibujar el mensaje acumulado
        # framebuf.text solo soporta caracteres básicos 8x8
        fbuf.text(message, 10, 30, WHITE)
        
        # Cursor visual (una linea debajo de donde iría la siguiente letra)
        cursor_x = 10 + (len(message) * 8)
        fbuf.line(cursor_x, 38, cursor_x + 8, 38, WHITE)
        
        # 3. Dibujar selector de caracteres (parte inferior)
        fbuf.rect(0, 200, 240, 50, BLUE, True) # Caja de fondo
        fbuf.text("SELECCIONAR:", 10, 210, WHITE)
        
        # Dibujar la letra actual en GRANDE (simulado dibujando pixeles o texto simple)
        # Como framebuf no tiene zoom, dibujamos la letra y un indicador
        char_str = f"[{chars[current_char_index]}]"
        fbuf.text(char_str, 100, 230, WHITE)
        
        # 4. Enviar a pantalla
        display.show_buffer(buffer)
