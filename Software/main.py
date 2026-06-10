from menu import SDRApp
from si5351 import Si5351
from si5351_test import is_integer_divider
from machine import I2C, Pin
import time

def configure_si5351():
    print("Initializing Si5351...")
    i2c = I2C(0, scl=Pin(13), sda=Pin(12))
    si5351 = Si5351(i2c)
    si5351.initialize()
    print("Si5351 initialized")

    si5351.configure_plla(25)
    print("✓ PLLA configured: N=25, VCO=614.4 MHz")
    
    si5351.configure_clk0(60)
    si5351.configure_clk1(60)
    si5351.configure_clk2(60)
    
    # Set phase offset for 90 degree shift: PHOFF = M = 60
    si5351.set_phase(0, 0)    # CLK0 at 0 degrees
    si5351.set_phase(1, 60)   # CLK1 at 90 degrees
    si5351.set_phase(2, 120)  # CLK2 at 180 degrees
    print("✓ Phase offset set: CLK0=0°, CLK1=90°, CLK2=180°")
    
    # Reset PLLs to lock in the configuration
    si5351.write_register(177, 0xAC)
    
    # Enable outputs
    si5351.enable_output(clk0=True, clk1=False, clk2=False)
    print("✓ Outputs enabled")
    
    time.sleep(0.5)  # Wait for PLLs to lock and outputs to stabilize
    
    # Check PLLA_LOL and PLLB_LOL status bits
    print("\n--- Checking PLL Lock Status ---")
    status = si5351.read_register(0)  # Register 0 contains PLL lock status
    plla_lol = status & 0x10
    pllb_lol = status & 0x20

    if plla_lol:
        print("⚠ PLLA lost lock")
    else:
        print("✓ PLLA locked")

    if pllb_lol:
        print("⚠ PLLB lost lock")
    else:
        print("✓ PLLB locked")
    time.sleep(5)
    print()
    frequency = (4096000, 150) 
    # Verify this is an integer divisor of the PLL frequency
    print(f"Setting CLK0, CLK1, and CLK2 to {frequency[0] / 1e6:.3f} MHz (M={frequency[1]})")
    si5351.configure_clk0(frequency[1])
    si5351.configure_clk1(frequency[1])
    si5351.configure_clk2(frequency[1])
    si5351.set_phase(0, 0)
    si5351.set_phase(1, frequency[1])  # PHOFF = M for 90 degree offset
    si5351.set_phase(2, frequency[1] * 2)  # PHOFF = 2*M for 180 degree offset
    si5351.write_register(177, 0xAC)
    si5351.enable_output(clk0=True, clk1=False, clk2=False)
    
if __name__ == "__main__":
    # configure_si5351()

    print("Starting SDR Menu...")
    app = SDRApp()
    app.run()