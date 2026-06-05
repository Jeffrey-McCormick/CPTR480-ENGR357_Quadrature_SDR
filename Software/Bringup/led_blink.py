"""
Red LED Blink Test

Code generated with GitHub Copilot (Claude Haiku 4.5).
Pin configuration verified and hardware-tested by Jeffrey McCormick.

Usage:
  1. Upload this script to your YD-RP2040 via MicroPico
  2. Run it in the REPL (Ctrl+Enter or F5)
  3. Observe the LED on GPIO5 blinking

Blinks an LED with a 0.5-second interval.
"""

from machine import Pin
import time

# Initialize GPIO5 as output
led = Pin(5, Pin.OUT)

# Blink the LED
while True:
    led.on()
    time.sleep(0.5)
    led.off()
    time.sleep(0.5)
