
"""
I2C Bus Scanner for 2026 Board

Code skeleton generated with GitHub Copilot (Claude Haiku 4.5).
Pin configuration corrected and hardware-tested by Jeffrey McCormick in CPTR480 Lab 1.

Usage:
  1. Upload this script to your Pico via MicroPico
  2. Run it in the REPL (Ctrl+Enter or F5)
  3. Check the output for I2C addresses found (0x60=Si5351a, 0x3C/0x3D=OLED, etc.)

This scans I2C bus 0 and prints all detected device addresses in hex and decimal.
"""

import machine

# I2C scan on pins GP16 (SCL) and GP17 (SDA)
i2c = machine.I2C(0, scl=machine.Pin(13), sda=machine.Pin(12))
devices = i2c.scan()

print("I2C Devices Found:")
if devices:
    for addr in devices:
        print(f"  0x{addr:02X} (decimal: {addr})")
else:
    print("  No devices found")
