from machine import I2C, Pin
import time

class Si5351:
    def __init__(self, i2c, address=0x60):
        self.i2c = i2c
        self.address = address
        self.crystal_freq = 24576000  # Adjusted crystal frequency (24.576 MHz)

    def write_register(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value]))

    def read_register(self, reg):
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]

    def initialize(self):
        # Power down all outputs
        for i in range(16, 24):
            self.write_register(i, 0x80)

        # Disable all outputs
        self.write_register(3, 0xFF)

        # Reset PLLs
        self.write_register(177, 0xAC)

    def configure_plla(self, mult, num=0, denom=1):
        # Configure PLLA with multiplier and fractional values
        p1 = 128 * mult + int(128 * num / denom) - 512
        p2 = 128 * num - denom * int(128 * num / denom)
        p3 = denom

        self.write_register(26, (p3 >> 8) & 0xFF)
        self.write_register(27, p3 & 0xFF)
        self.write_register(28, (p1 >> 16) & 0x03)
        self.write_register(29, (p1 >> 8) & 0xFF)
        self.write_register(30, p1 & 0xFF)
        self.write_register(31, (p2 >> 16) & 0x0F)
        self.write_register(32, (p2 >> 8) & 0xFF)
        self.write_register(33, p2 & 0xFF)
        
    def configure_pllb(self, mult, num=0, denom=1):
        # Configure PLLB with multiplier and fractional values
        p1 = 128 * mult + int(128 * num / denom) - 512
        p2 = 128 * num - denom * int(128 * num / denom)
        p3 = denom

        self.write_register(34, (p3 >> 8) & 0xFF)
        self.write_register(35, p3 & 0xFF)
        self.write_register(36, (p1 >> 16) & 0x03)
        self.write_register(37, (p1 >> 8) & 0xFF)
        self.write_register(38, p1 & 0xFF)
        self.write_register(39, (p2 >> 16) & 0x0F)
        self.write_register(40, (p2 >> 8) & 0xFF)
        self.write_register(41, p2 & 0xFF)

    def configure_clk0(self, ms_div, num=0, denom=1):
        # Configure MultiSynth divider for CLK0
        p1 = 128 * ms_div + int(128 * num / denom) - 512
        p2 = 128 * num - denom * int(128 * num / denom)
        p3 = denom

        self.write_register(42, (p3 >> 8) & 0xFF)
        self.write_register(43, p3 & 0xFF)
        self.write_register(44, (p1 >> 16) & 0x03)
        self.write_register(45, (p1 >> 8) & 0xFF)
        self.write_register(46, p1 & 0xFF)
        self.write_register(47, (p2 >> 16) & 0x0F)
        self.write_register(48, (p2 >> 8) & 0xFF)
        self.write_register(49, p2 & 0xFF)
        
    def configure_clk1(self, ms_div, num=0, denom=1):
        # Configure MultiSynth divider for CLK1
        p1 = 128 * ms_div + int(128 * num / denom) - 512
        p2 = 128 * num - denom * int(128 * num / denom)
        p3 = denom

        self.write_register(50, (p3 >> 8) & 0xFF)
        self.write_register(51, p3 & 0xFF)
        self.write_register(52, (p1 >> 16) & 0x03)
        self.write_register(53, (p1 >> 8) & 0xFF)
        self.write_register(54, p1 & 0xFF)
        self.write_register(55, (p2 >> 16) & 0x0F)
        self.write_register(56, (p2 >> 8) & 0xFF)
        self.write_register(57, p2 & 0xFF)

    def configure_clk2(self, ms_div, num=0, denom=1):
        # Configure MultiSynth divider for CLK2
        p1 = 128 * ms_div + int(128 * num / denom) - 512
        p2 = 128 * num - denom * int(128 * num / denom)
        p3 = denom

        self.write_register(58, (p3 >> 8) & 0xFF)
        self.write_register(59, p3 & 0xFF)
        self.write_register(60, (p1 >> 16) & 0x03)
        self.write_register(61, (p1 >> 8) & 0xFF)
        self.write_register(62, p1 & 0xFF)
        self.write_register(63, (p2 >> 16) & 0x0F)
        self.write_register(64, (p2 >> 8) & 0xFF)
        self.write_register(65, p2 & 0xFF)

    def enable_output(self, clk0=True, clk1=True, clk2=True):
        # Register 3: 0 is ENABLED, 1 is DISABLED
        mask = 0xFF
        if clk0: mask &= ~(1 << 0)
        if clk1: mask &= ~(1 << 1)
        if clk2: mask &= ~(1 << 2)
        
        # Set drive strength and source (0x4F: 8mA, PLLA source, MultiSynth source)
        self.write_register(16, 0x4F) # CLK0
        self.write_register(17, 0x4F) # CLK1
        self.write_register(18, 0x4F) # CLK2
        
        # Apply the enable mask
        self.write_register(3, mask)
        
        # CRITICAL: Reset PLLs after configuration to lock the new frequency
        self.write_register(177, 0xAC)

        
    def set_phase(self, clk, phase_value):
        """
        clk: 0 for CLK0, 1 for CLK1
        phase_value: The calculated offset value (0-127)
        """
        # Phase registers: CLK0=165, CLK1=166, CLK2=167
        reg = 165 + clk
        # The phase offset is a 7-bit value
        self.write_register(reg, phase_value & 0x7F)

    def set_freq(self, clk, freq):
        """
        Sets a specific clock to the requested frequency using a fractional divider.
        This provides arbitrary frequency output, but quadrature phase offset will not work.
        """
        # Force an arbitrary PLL frequency (e.g. from pll_mult = 36 -> 884.736 MHz)
        pll_mult = 36
        actual_pll_freq = self.crystal_freq * pll_mult
        self.configure_plla(pll_mult)
        
        # Calculate fractional MultiSynth divider
        divider = actual_pll_freq / freq
        ms_div = int(divider)
        denom = 1000000
        num = int((divider - ms_div) * denom)
        
        if clk == 0:
            self.configure_clk0(ms_div, num, denom)
        elif clk == 1:
            self.configure_clk1(ms_div, num, denom)
        elif clk == 2:
            self.configure_clk2(ms_div, num, denom)
            
        self.write_register(177, 0xAC)

    def set_quadrature(self, target_freq):
        """
        Sets CLK0 and CLK1 to the same frequency with a 90-degree phase offset.
        Dynamically adjusts the PLL (with fractional multipliers if needed) to ensure
        the MultiSynth divider remains an integer, satisfying the hardware phase offset requirement.
        """
        crystal_freq = self.crystal_freq
        
        # 1. Try to find a pure integer configuration first (VCO in 600-900 MHz)
        for div in range(8, 901):
            vco_freq = target_freq * div
            if 600000000 <= vco_freq <= 900000000:
                if vco_freq % crystal_freq == 0:
                    pll_mult = vco_freq // crystal_freq
                    if 15 <= pll_mult <= 90:
                        self.configure_plla(pll_mult)
                        self._apply_quadrature_config(div)
                        return
        
        # 2. Fall back to fractional PLL configuration with integer divider
        for div in range(8, 901):
            vco_freq = target_freq * div
            if 600000000 <= vco_freq <= 900000000:
                pll_mult_exact = vco_freq / crystal_freq
                pll_mult = int(pll_mult_exact)
                if 15 <= pll_mult <= 90:
                    denom = 1000000
                    num = int((pll_mult_exact - pll_mult) * denom)
                    self.configure_plla(pll_mult, num, denom)
                    self._apply_quadrature_config(div)
                    return
                    
        raise ValueError("Could not find suitable PLL parameters for requested quadrature frequency")

    def _apply_quadrature_config(self, div):
        # Configure MultiSynths (Set to Integer Mode)
        self.configure_clk0(div, num=0, denom=1)
        self.configure_clk1(div, num=0, denom=1)
        
        # Set Phase Offset
        self.set_phase(0, 0)
        self.set_phase(1, div)
        
        # CRITICAL: Reset PLL to sync the phase registers
        self.write_register(177, 0xAC)
        self.enable_output(clk0=True, clk1=True, clk2=False)

# Correct Example usage for 10 MHz
if __name__ == "__main__":
    i2c = I2C(0, scl=Pin(13), sda=Pin(12))
    si5351 = Si5351(i2c)
    si5351.initialize()
    # 10 MHz is 10,000,000
    si5351.set_quadrature(10000000)

