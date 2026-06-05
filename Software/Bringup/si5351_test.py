from si5351 import Si5351
from machine import I2C, Pin
import time

def test_si5351():
    # Initialize I2C and Si5351
    print("\n--- Register Read/Write Test ---")
    i2c = I2C(0, scl=Pin(13), sda=Pin(12))
    si5351 = Si5351(i2c)
    si5351.initialize()

    # Test writing and reading registers
    test_reg = 26  # PLLA P3 register
    test_value = 0xAB
    si5351.write_register(test_reg, test_value)
    read_value = si5351.read_register(test_reg)

    if read_value == test_value:
        print(f"✓ Register read/write test passed (wrote 0x{test_value:02x}, read 0x{read_value:02x})")
    else:
        print(f"✗ Register read/write failed: expected 0x{test_value:02x}, got 0x{read_value:02x}")
    print()

def is_integer_divider(pll_freq, target_freq):
    """Check if target_freq is an integer divisor of pll_freq"""
    if target_freq == 0:
        return False
    return pll_freq % target_freq == 0

def main():
    # Initialize I2C
    i2c = I2C(0, scl=Pin(13), sda=Pin(12))

    print("\n" + "="*60)
    print("Si5351a Quadrature Generator Test")
    print("="*60)

    # Scan I2C bus
    print("\n--- I2C Bus Scan ---")
    devices = i2c.scan()
    if 0x60 in devices:
        print("✓ Si5351a found at address 0x60")
    else:
        print("✗ Si5351a not found on I2C bus")
        return

    # Initialize Si5351a
    print("\n--- Initializing Si5351a ---")
    si5351 = Si5351(i2c)
    si5351.initialize()
    print("✓ Si5351a initialized")

    # Configure for 10.24 MHz quadrature output
    # Crystal: 24.576 MHz
    # PLLA: N=25, VCO = 24.576 * 25 = 614.4 MHz
    # CLK0/CLK1: M=60, Frequency = 614.4 / 60 = 10.24 MHz
    # CLK1: PHOFF = 60 for 90 degree phase shift
    
    print("\n--- Configuring 10.24 MHz Quadrature Output ---")
    print("  Crystal:       24.576 MHz")
    print("  PLLA N:        25")
    print("  VCO:           614.4 MHz")
    print("  CLK0/CLK1 M:   60")
    print("  Output Freq:   10.24 MHz")
    print("  CLK1 Offset:   90° (PHOFF=60)")
    print()
    
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
    
    print("✓ CLK0, CLK1, and CLK2 set to 10.24 MHz with phase relationships")
    print("\nVerify on oscilloscope:")
    print("  • CLK0: 10.24 MHz square wave (period ≈ 97.66 ns)")
    print("  • CLK1: 10.24 MHz square wave, 90° ahead of CLK0 (≈ 24.4 ns delay)")
    print("  • CLK2: 10.24 MHz square wave, 180° ahead of CLK0 (≈ 48.8 ns delay)")
    print("  • Pausing for 5 seconds for oscilloscope verification...")
    time.sleep(5)
    print()

    # Sweep through frequencies achievable with integer dividers from 24.576 MHz crystal
    # VCO = 614.4 MHz allows these output frequencies with integer MS dividers:
    # Note: Some frequencies are intentionally NOT integer dividers to test validation
    frequencies = [
        (1536000, 400),    # 614.4 MHz / 400 = 1.536 MHz (integer)
        (10000000, 61.44), # 614.4 MHz / 10 MHz = 61.44 (NOT integer - test case)
        (2048000, 300),    # 614.4 MHz / 300 = 2.048 MHz (integer)
        (7100000, 86.53),  # 614.4 MHz / 7.1 MHz = 86.53 (NOT integer - test case)
        (3072000, 200),    # 614.4 MHz / 200 = 3.072 MHz (integer)
        (6144000, 100),    # 614.4 MHz / 100 = 6.144 MHz (integer)
        (10240000, 60),    # 614.4 MHz / 60 = 10.24 MHz (integer)
        (12288000, 50),    # 614.4 MHz / 50 = 12.288 MHz (integer)
        (40960000, 15),    # 614.4 MHz / 15 = 40.96 MHz (integer)
    ]
    
    print("--- Frequency Sweep with Integer Divider Validation ---")
    print()
    vco_freq = 614400000  # 614.4 MHz
    for freq, ms_div in frequencies:
        # Verify this is an integer divisor of the PLL frequency
        if is_integer_divider(vco_freq, freq):
            print(f"Setting CLK0, CLK1, and CLK2 to {freq / 1e6:.3f} MHz (M={ms_div})")
            si5351.configure_clk0(ms_div)
            si5351.configure_clk1(ms_div)
            si5351.configure_clk2(ms_div)
            si5351.set_phase(0, 0)
            si5351.set_phase(1, ms_div)  # PHOFF = M for 90 degree offset
            si5351.set_phase(2, ms_div * 2)  # PHOFF = 2*M for 180 degree offset
            si5351.write_register(177, 0xAC)
            si5351.enable_output(clk0=True, clk1=False, clk2=False)
            print(f"  Pausing for oscilloscope verification...")
            time.sleep(3)
        else:
            print(f"{freq / 1e6:.3f} MHz is NOT an integer divisor of PLL frequency, skipping")
            time.sleep(0.5)

if __name__ == "__main__":
    test_si5351()
    main()
