import machine
import time
import struct
import framebuf
from micropython import const

# --- DRIVER ST7789 ---
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
        self.write_cmd(ST7789_MADCTL)
        self.write_data(bytearray([0xC0])) # Rotacion 180
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

btn_up    = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
btn_down  = machine.Pin(1, machine.Pin.IN, machine.Pin.PULL_UP)
btn_left  = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
btn_right = machine.Pin(3, machine.Pin.IN, machine.Pin.PULL_UP)
btn_sel   = machine.Pin(4, machine.Pin.IN, machine.Pin.PULL_UP)

# --- CORRECCION DE COLORES (Byte Swap) ---
def swap_bytes(color):
    return ((color & 0xFF) << 8) | ((color >> 8) & 0xFF)

# Definimos los colores YA invertidos para que framebuf los guarde 
# en el orden que la pantalla espera recibir.
BLACK = swap_bytes(0x0000)
WHITE = swap_bytes(0xFFFF)
BLUE  = swap_bytes(0x001F)
RED   = swap_bytes(0xF800)
GREEN = swap_bytes(0x07E0)
GRAY  = swap_bytes(0x8410)
DARK_CMD = swap_bytes(0x4208)

# --- CONFIGURACION TECLADO ---
KEYBOARD_LAYOUT = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L", "N"], 
    ["Z", "X", "C", "V", "B", "N", "M"],                 
    ["SPC", "DEL", "CLR", "ENTER"]                       
]

KEY_W = 24  
KEY_H = 30  
K_START_Y = 140 

cursor_row = 1 
cursor_col = 0
message = ""

# Buffer de Video
buffer = bytearray(240 * 320 * 2)
fbuf = framebuf.FrameBuffer(buffer, 240, 320, framebuf.RGB565)

def draw_multiline_text(text, x, y, color, max_lines=12):
    # framebuf no soporta \n nativamente, hay que hacerlo manual
    lines = text.split('\n')
    
    # Si hay mas lineas de las que caben, mostramos las ultimas
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
        
    for i, line in enumerate(lines):
        fbuf.text(line, x, y + (i * 10), color)
        
    return len(lines) # Retornamos cuantas lineas dibujamos para saber donde poner el cursor

def draw_interface():
    fbuf.fill(BLACK)
    
    # --- AREA DE TEXTO ---
    fbuf.rect(0, 0, 240, 135, BLUE, True) 
    fbuf.rect(5, 5, 230, 125, WHITE, False) 
    
    # Dibujar mensaje multilinea
    lines_drawn = draw_multiline_text(message, 10, 10, WHITE)
    
    # Cursor parpadeante (al final de la ultima linea)
    if (time.ticks_ms() // 500) % 2 == 0:
        # Calcular posicion Y basado en lineas
        cursor_y = 10 + ((lines_drawn - 1) * 10)
        if cursor_y < 10: cursor_y = 10
        
        # Calcular posicion X basado en la longitud de la ultima linea
        lines = message.split('\n')
        last_line = lines[-1] if lines else ""
        cursor_x = 10 + (len(last_line) * 8)
        
        # Dibujar guion bajo
        fbuf.line(cursor_x, cursor_y + 8, cursor_x + 8, cursor_y + 8, WHITE)

    # --- TECLADO ---
    y_pos = K_START_Y
    for r_idx, row in enumerate(KEYBOARD_LAYOUT):
        row_len = len(row)
        x_offset = 0
        
        # Centrar fila Z
        if r_idx == 3: 
            x_offset = (240 - (row_len * KEY_W)) // 2 
        
        current_key_w = KEY_W
        if r_idx == 4:
            current_key_w = 240 // 4 

        for c_idx, char in enumerate(row):
            x_pos = x_offset + (c_idx * current_key_w)
            is_selected = (r_idx == cursor_row and c_idx == cursor_col)
            
            bg_color = GRAY
            if is_selected:
                bg_color = GREEN
            elif r_idx == 4: 
                bg_color = DARK_CMD
            
            fbuf.rect(x_pos + 1, y_pos + 1, current_key_w - 2, KEY_H - 2, bg_color, True)
            
            text_x = x_pos + (current_key_w // 2) - 4
            text_y = y_pos + (KEY_H // 2) - 4
            fbuf.text(char, text_x, text_y, WHITE)
            
        y_pos += KEY_H

    display.show_buffer(buffer)

def handle_input():
    global cursor_row, cursor_col, message
    
    time.sleep(0.05) 
    
    if btn_up.value() == 0:
        cursor_row -= 1
        if cursor_row < 0: cursor_row = len(KEYBOARD_LAYOUT) - 1
        cursor_col = min(cursor_col, len(KEYBOARD_LAYOUT[cursor_row]) - 1)
        return True
        
    if btn_down.value() == 0:
        cursor_row += 1
        if cursor_row >= len(KEYBOARD_LAYOUT): cursor_row = 0
        cursor_col = min(cursor_col, len(KEYBOARD_LAYOUT[cursor_row]) - 1)
        return True
        
    if btn_left.value() == 0:
        cursor_col -= 1
        if cursor_col < 0: 
            cursor_col = len(KEYBOARD_LAYOUT[cursor_row]) - 1
        return True
        
    if btn_right.value() == 0:
        cursor_col += 1
        if cursor_col >= len(KEYBOARD_LAYOUT[cursor_row]):
            cursor_col = 0 
        return True
        
    if btn_sel.value() == 0:
        char = KEYBOARD_LAYOUT[cursor_row][cursor_col]
        
        if char == "SPC":
            message += " "
        elif char == "DEL":
            if len(message) > 0:
                message = message[:-1]
        elif char == "CLR":
            message = ""
        elif char == "ENTER":
            # Agregamos salto de linea
            message += "\n"
        else:
            message += char
            
        time.sleep(0.2) 
        return True
        
    return False

# --- LOOP ---
draw_interface() 

while True:
    if handle_input():
        draw_interface()
    
    # Refresco periodico para el cursor parpadeante (cada 500ms aprox)
    if (time.ticks_ms() % 500) < 50:
         draw_interface()
         
    time.sleep(0.01)
