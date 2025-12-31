# Guía de Integración: Waveshare RP2350-Zero + Display LCD GMT020-02 (ST7789)

Este documento detalla la configuración de hardware y software necesaria para controlar el módulo de pantalla TFT GMT020-02 (Driver ST7789V, 240x320) utilizando MicroPython en un **Waveshare RP2350-Zero**.

## 📋 Especificaciones
* **MCU:** RP2350 (Waveshare Zero)
* **Display:** 2.0 inch TFT (GMT020-02)
* **Driver:** ST7789V
* **Protocolo:** SPI (Hardware SPI1)
* **Voltaje Lógico:** 3.3V

## 🔌 Conexiones (Wiring)

La configuración utiliza el bus **SPI1** del RP2350 para maximizar la velocidad de transferencia.

| Pin Display (GMT020) | Pin RP2350-Zero | Función MicroPython | Descripción |
| :--- | :--- | :--- | :--- |
| **VCC** | **3V3** | Power | Alimentación 3.3V |
| **GND** | **GND** | GND | Tierra común |
| **SCL / SCK** | **GP10** | SPI1 SCK | Reloj del bus SPI |
| **SDA / MOSI** | **GP11** | SPI1 TX | Envío de datos (Master Out) |
| **RES / RST** | **GP12** | GPIO | Reset físico del display |
| **DC / RS** | **GP8** | GPIO | Selección Dato/Comando |
| **CS** | **GP9** | SPI1 CS | Chip Select (Activo bajo) |
| **BLK** | **GP13** | GPIO | Control de Backlight (High = On) |

> **Nota:** El pin `BLK` también puede conectarse directamente a 3V3 si no se requiere controlar el apagado de la pantalla por software.

## 💻 Código Fuente (`main.py`)

Este script incluye una clase "Mini-Driver" embebida para el ST7789, eliminando la necesidad de subir librerías externas al sistema de archivos del microcontrolador.

### Características del código:
* Inicialización optimizada para paneles IPS.
* Baudrate de SPI configurado a **40MHz**.
* Formato de color: **RGB565**.

```python
import machine
import time
import struct
from micropython import const

# --- Definiciones de Comandos ST7789 ---
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

        # Estado inicial de pines
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
        # Secuencia de Reset Hardware
        self.reset.value(1)
        time.sleep_ms(50)
        self.reset.value(0)
        time.sleep_ms(50)
        self.reset.value(1)
        time.sleep_ms(150)

        # Inicialización de Software
        self.write_cmd(ST7789_SWRESET)
        time.sleep_ms(150)
        self.write_cmd(ST7789_SLPOUT)
        time.sleep_ms(255)
        
        # Color mode 16-bit (565)
        self.write_cmd(ST7789_COLMOD)
        self.write_data(bytearray([0x55]))
        
        # Orientación (0x00 = Portrait standard)
        self.write_cmd(ST7789_MADCTL)
        self.write_data(bytearray([0x00])) 

        self.write_cmd(ST7789_INVON) # Inversión de color (necesario para muchos IPS)
        self.write_cmd(ST7789_NORON)
        self.write_cmd(ST7789_DISPON)

    def set_window(self, x0, y0, x1, y1):
        self.write_cmd(ST7789_CASET)
        self.write_data(struct.pack(">HH", x0, x1))
        self.write_cmd(ST7789_RASET)
        self.write_data(struct.pack(">HH", y0, y1))
        self.write_cmd(ST7789_RAMWR)

    def fill(self, color):
        # Rellena la pantalla completa con un color RGB565
        chunk_size = 1024
        buffer = struct.pack(">H", color) * chunk_size
        
        self.set_window(0, 0, self.width - 1, self.height - 1)
        
        pixels_remaining = self.width * self.height
        
        self.dc.value(1)
        self.cs.value(0)
        while pixels_remaining > 0:
            if pixels_remaining < chunk_size:
                self.spi.write(buffer[:pixels_remaining * 2])
                pixels_remaining = 0
            else:
                self.spi.write(buffer)
                pixels_remaining -= chunk_size
        self.cs.value(1)

# --- Configuración Principal ---

# Definición de Pines (Mapeo RP2350-Zero)
spi = machine.SPI(1, baudrate=40_000_000, polarity=1, phase=1, sck=machine.Pin(10), mosi=machine.Pin(11))
cs = machine.Pin(9)
dc = machine.Pin(8)
rst = machine.Pin(12)
blk = machine.Pin(13)

# Instancia del Driver
display = ST7789(spi, 240, 320, rst, dc, cs, blk)

# Colores de Ejemplo (Formato Hex RGB565)
RED   = 0xF800
GREEN = 0x07E0
BLUE  = 0x001F
WHITE = 0xFFFF
BLACK = 0x0000

# Loop de Prueba
print("Iniciando prueba de pantalla...")
while True:
    display.fill(RED)
    time.sleep(1)
    
    display.fill(GREEN)
    time.sleep(1)
    
    display.fill(BLUE)
    time.sleep(1)
