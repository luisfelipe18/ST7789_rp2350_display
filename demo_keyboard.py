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

    def rotate(self, rotation):
        madctl_val = 0
        if rotation == 0:   # Portrait
            madctl_val = 0x00
            self.width, self.height = 240, 320
        elif rotation == 1: # Landscape
            madctl_val = 0x60
            self.width, self.height = 320, 240
        elif rotation == 2: # Portrait Inv
            madctl_val = 0xC0
            self.width, self.height = 240, 320
        elif rotation == 3: # Landscape Inv
            madctl_val = 0xA0
            self.width, self.height = 320, 240
            
        self.write_cmd(ST7789_MADCTL)
        self.write_data(bytearray([madctl_val]))

# --- HARDWARE ---
spi = machine.SPI(1, baudrate=40_000_000, polarity=1, phase=1, sck=machine.Pin(10), mosi=machine.Pin(11))
display = ST7789(spi, 240, 320, machine.Pin(12), machine.Pin(8), machine.Pin(9), machine.Pin(13))

btn_up    = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
btn_down  = machine.Pin(1, machine.Pin.IN, machine.Pin.PULL_UP)
btn_left  = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
btn_right = machine.Pin(3, machine.Pin.IN, machine.Pin.PULL_UP)
btn_sel   = machine.Pin(4, machine.Pin.IN, machine.Pin.PULL_UP)

# --- COLORES ---
def swap_bytes(color):
    return ((color & 0xFF) << 8) | ((color >> 8) & 0xFF)

BLACK = swap_bytes(0x0000)
WHITE = swap_bytes(0xFFFF)
BLUE  = swap_bytes(0x001F)
RED   = swap_bytes(0xF800)
GREEN = swap_bytes(0x07E0)
GRAY  = swap_bytes(0x8410)
DARK_CMD = swap_bytes(0x4208)
ORANGE = swap_bytes(0xFC00)
MAGENTA = swap_bytes(0xF81F)
CYAN = swap_bytes(0x07FF) 

# --- DEFINICION DE LAYOUTS ---

# Fila especial Z con Modificadores
# "z"..."m" son 7 letras. SHFT y EMOJ ocupan el resto.
ROW_Z_ALPHA = ["SHFT", "z", "x", "c", "v", "b", "n", "m", "EMOJ"]
ROW_Z_SYMB  = ["SHFT", "<", ">", "{", "}", "[", "]", "\\", "EMOJ"]

# Layout Alfanumérico
LAYOUT_ALPHA = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l", "n"], 
    ROW_Z_ALPHA # Fila 3 modificada
]

# Layout Símbolos
LAYOUT_SYMBOLS = [
    ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"],
    ["-", "_", "=", "+", "/", "?", "~", "`", "|", "."],
    [";", ":", "'", "\"", ",", "XD", ":)", ":(", "<3", ":D"],
    ROW_Z_SYMB  # Fila 3 modificada
]

# Fila de Comandos (Nueva petición)
CMD_ROW = ["SPC", "DEL", "CLR", "ENTER", "ROT"]

# Variables de Estado
is_shift = False    
is_emoji_mode = False 

KEY_W_BASE = 0 # Ancho base (1/10 de pantalla)
KEY_H = 0
K_START_Y = 0
fbuf = None 
buffer_raw = bytearray(320 * 240 * 2)

cursor_row = 1 
cursor_col = 0
message = ""
current_rotation = 2 

def update_layout_metrics():
    global KEY_W_BASE, KEY_H, K_START_Y, fbuf
    w = display.width
    h = display.height
    fbuf = framebuf.FrameBuffer(buffer_raw, w, h, framebuf.RGB565)
    
    KEY_W_BASE = w // 10 # Ancho estándar de una tecla (10 columnas)
    
    if h < 300: KEY_H = 25
    else: KEY_H = 30
    
    keyboard_total_height = KEY_H * 5 # 5 filas total
    K_START_Y = h - keyboard_total_height

display.rotate(current_rotation)
update_layout_metrics()

def get_char_for_display(base_char):
    if len(base_char) > 1: return base_char 
    if is_emoji_mode: return base_char 
    if is_shift: return base_char.upper()
    else: return base_char.lower()

def draw_multiline_text(text, x, y, color):
    lines = text.split('\n')
    available_height = K_START_Y - 10
    calculated_max_lines = available_height // 10
    if len(lines) > calculated_max_lines:
        lines = lines[-calculated_max_lines:]
    for i, line in enumerate(lines):
        fbuf.text(line, x, y + (i * 10), color)
    return len(lines) 

def draw_interface():
    fbuf.fill(BLACK)
    w = display.width
    
    active_grid = LAYOUT_SYMBOLS if is_emoji_mode else LAYOUT_ALPHA
    
    # Area Texto
    text_area_h = K_START_Y - 5
    fbuf.rect(0, 0, w, text_area_h, BLUE, True) 
    fbuf.rect(5, 5, w - 10, text_area_h - 10, WHITE, False) 
    lines_drawn = draw_multiline_text(message, 10, 10, WHITE)
    
    if (time.ticks_ms() // 500) % 2 == 0:
        cursor_y = 10 + ((lines_drawn - 1) * 10)
        if cursor_y < 10: cursor_y = 10
        lines = message.split('\n')
        last_line = lines[-1] if lines else ""
        cursor_x = 10 + (len(last_line) * 8)
        fbuf.line(cursor_x, cursor_y + 8, cursor_x + 8, cursor_y + 8, WHITE)

    # --- DIBUJAR TECLADO CON GEOMETRIA VARIABLE ---
    y_pos = K_START_Y
    full_layout = active_grid + [CMD_ROW]
    
    for r_idx, row in enumerate(full_layout):
        row_len = len(row)
        current_x = 0 # Acumulador de posición X
        
        for c_idx, char in enumerate(row):
            # --- CALCULO DE ANCHO DE TECLA ---
            this_key_w = KEY_W_BASE # Por defecto
            
            if r_idx == 3: # Fila Z (SHFT...EMOJ)
                # Tenemos 7 teclas normales y 2 anchas.
                # Ancho disponible para las 2 anchas = AnchoTotal - (7 * Base)
                width_for_specials = w - (7 * KEY_W_BASE)
                
                if c_idx == 0 or c_idx == (row_len - 1): # Primera o Ultima (SHFT/EMOJ)
                    this_key_w = width_for_specials // 2
                else:
                    this_key_w = KEY_W_BASE
            
            elif r_idx == 4: # Fila Comandos (5 botones)
                this_key_w = w // row_len
            
            # --- DIBUJADO ---
            is_selected = (r_idx == cursor_row and c_idx == cursor_col)
            
            bg_color = GRAY
            
            # Colores Lógicos
            if char == "SHFT":
                bg_color = MAGENTA if is_shift else DARK_CMD
            elif char == "EMOJ":
                bg_color = CYAN if is_emoji_mode else DARK_CMD
            elif char == "ROT":
                bg_color = ORANGE
            elif r_idx == 4: # Otros comandos
                bg_color = DARK_CMD

            if is_selected:
                bg_color = GREEN
            
            # Dibujar rectangulo en current_x
            fbuf.rect(current_x + 1, y_pos + 1, this_key_w - 2, KEY_H - 2, bg_color, True)
            
            display_text = get_char_for_display(char)
            
            # Centrado
            text_pixel_len = len(display_text) * 8
            text_x = current_x + (this_key_w // 2) - (text_pixel_len // 2)
            text_y = y_pos + (KEY_H // 2) - 4
            fbuf.text(display_text, text_x, text_y, WHITE)
            
            current_x += this_key_w # Avanzar X
            
        y_pos += KEY_H

    display.show_buffer(buffer_raw)

def handle_input():
    global cursor_row, cursor_col, message, is_shift, is_emoji_mode, current_rotation
    
    active_grid = LAYOUT_SYMBOLS if is_emoji_mode else LAYOUT_ALPHA
    full_layout = active_grid + [CMD_ROW]
    
    time.sleep(0.05) 
    
    if btn_up.value() == 0:
        cursor_row -= 1
        if cursor_row < 0: cursor_row = len(full_layout) - 1
        cursor_col = min(cursor_col, len(full_layout[cursor_row]) - 1)
        return True
        
    if btn_down.value() == 0:
        cursor_row += 1
        if cursor_row >= len(full_layout): cursor_row = 0
        cursor_col = min(cursor_col, len(full_layout[cursor_row]) - 1)
        return True
        
    if btn_left.value() == 0:
        cursor_col -= 1
        if cursor_col < 0: 
            cursor_col = len(full_layout[cursor_row]) - 1
        return True
        
    if btn_right.value() == 0:
        cursor_col += 1
        if cursor_col >= len(full_layout[cursor_row]):
            cursor_col = 0 
        return True
        
    if btn_sel.value() == 0:
        char_key = full_layout[cursor_row][cursor_col]
        
        if char_key == "SHFT":
            is_shift = not is_shift
        elif char_key == "EMOJ":
            is_emoji_mode = not is_emoji_mode
            cursor_row = 3 # Mantenerse en fila segura
            cursor_col = 8 # Ir al boton EMOJ (ahora a la derecha)
        elif char_key == "ROT":
            current_rotation += 1
            if current_rotation > 3: current_rotation = 0
            display.rotate(current_rotation)
            update_layout_metrics()
        elif char_key == "SPC":
            message += " "
        elif char_key == "DEL":
            if len(message) > 0: message = message[:-1]
        elif char_key == "CLR":
            message = ""
        elif char_key == "ENTER":
            message += "\n"
        else:
            message += get_char_for_display(char_key)
            
        time.sleep(0.2) 
        return True
        
    return False

# --- LOOP ---
draw_interface() 

while True:
    if handle_input():
        draw_interface()
    
    if (time.ticks_ms() % 500) < 50:
         draw_interface()
         
    time.sleep(0.01)
