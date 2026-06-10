from menu import SDRApp
from si5351 import Si5351
from machine import I2C, Pin
import time

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import time
# Wait for hardware (OLED, SD Card, etc) to fully power up before initializing I2C/SPI
time.sleep(1.5)


print("Starting SDR Menu...")
app = SDRApp()
asyncio.run(app.run())