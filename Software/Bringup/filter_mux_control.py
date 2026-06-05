"""
Analog Filter MUX Control (CTL1 & CTL2)

Code generated with GitHub Copilot (Claude Haiku 4.5).
Pin configuration and hardware tested by Jeffrey McCormick.

Usage:
  1. Upload this script to your YD-RP2040 via MicroPico
  2. Run it in the REPL (Ctrl+Enter or F5)
  3. Call select_channel(0-3) to select a MUX channel
  
Sets CTL1 (GPIO19) and CTL2 (GPIO18) for 4-channel analog MUX selection
of 1 of 4 filters to be used.
Filter selection:
  0: CTL1=LOW,  CTL2=LOW   (All pass filter)
  1: CTL1=HIGH, CTL2=LOW   (6 MHz - 16 MHz, 3rd Order, Series-First Bessel filter)
  2: CTL1=LOW,  CTL2=HIGH  (10 kHz - 2 MHz, 3rd Order, Butterworth filter)
  3: CTL1=HIGH, CTL2=HIGH  (External Filter - XFIL)
"""

from machine import Pin
import time

# Initialize control pins
CTL1 = Pin(19, Pin.OUT)  # CTL1 line
CTL2 = Pin(18, Pin.OUT)  # CTL2 line


def select_channel(channel):
    """
    Select a MUX channel (0-3).
    
    Filter selection:
    0: 00 (All pass filter)
    1: 01 (BPF)
    2: 10 (LPF)
    3: 11 (XFIL)
    """
    if channel == 0:
        CTL1.off()   # *** CTL1 set LOW ***
        CTL2.off()   # *** CTL2 set LOW ***
    elif channel == 1:
        CTL1.on()    # *** CTL1 set HIGH ***
        CTL2.off()   # *** CTL2 set LOW ***
    elif channel == 2:
        CTL1.off()   # *** CTL1 set LOW ***
        CTL2.on()    # *** CTL2 set HIGH ***
    elif channel == 3:
        CTL1.on()    # *** CTL1 set HIGH ***
        CTL2.on()    # *** CTL2 set HIGH ***
    else:
        print("Invalid channel. Use 0-3.")




# Example: Cycle through all channels
if __name__ == "__main__":
    select_channel(0)

