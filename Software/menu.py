import machine
import time

try:
    from si5351 import Si5351
    from ssd1306 import SSD1306_I2C
    from rotary_encoder import QuadratureEncoder, ButtonHandler
except ImportError:
    # If the modules are located in the Bringup folders during testing
    import sys
    sys.path.append('Bringup')
    sys.path.append('Bringup/Load_files')
    from ssd1306 import SSD1306_I2C
    from rotary_encoder import QuadratureEncoder, ButtonHandler

# I2C setup for OLED
I2C_SDA = 12 
I2C_SCL = 13
I2C_FREQ = 400_000

# Encoder Setup
ENC_A = 20          #18 for test Intro to CAD board
ENC_B = 21          #17
ENC_BUTTON = 22     #5

# ENC_A = 18          #18 for test Intro to CAD board
# ENC_B = 17          #17
# ENC_BUTTON = 5     #5

class Menu:
    """
    A class to represent and render a generic selectable menu on the OLED.
    """
    def __init__(self, title, options):
        self.title = title
        self.options = options
        self.selected_idx = 0
        self.scroll_offset = 0
        self.max_visible = 4 # Number of items that fit below the title

    def next(self):
        if self.options:
            self.selected_idx = (self.selected_idx + 1) % len(self.options)
            self._adjust_scroll()

    def prev(self):
        if self.options:
            self.selected_idx = (self.selected_idx - 1) % len(self.options)
            self._adjust_scroll()
            
    def _adjust_scroll(self):
        if self.selected_idx < self.scroll_offset:
            self.scroll_offset = self.selected_idx
        elif self.selected_idx >= self.scroll_offset + self.max_visible:
            self.scroll_offset = self.selected_idx - self.max_visible + 1

    def get_selected(self):
        if self.options:
            return self.options[self.selected_idx]
        return None

    def draw(self, oled):
        oled.text(self.title, 0, 0, 1)
        oled.hline(0, 10, 128, 1)
        y = 15
        
        if not self.options:
            oled.text("  (Empty)", 0, y, 1)
            return

        visible_options = self.options[self.scroll_offset : self.scroll_offset + self.max_visible]
        for i, opt in enumerate(visible_options):
            actual_idx = self.scroll_offset + i
            prefix = ">" if actual_idx == self.selected_idx else " "
            # Display strings. Truncate if too long (128px width / 8px per char = 16 chars max)
            text_str = f"{prefix} {opt}"[:16]
            oled.text(text_str, 0, y, 1)
            y += 12


from ui.page import NavStack
from ui.menu_page import MenuPage, MenuItem
from ui.freq_pages import AddFreqPage, FreqListPage


class SDRApp:
    """
    The main application class that ties together hardware interfaces 
    and handles navigation via a page stack.
    """
    def __init__(self):
        self._init_hardware()
        
        # Sorted array holding the saved frequencies
        self.freqs = [] 
        
        # Add frequency properties
        self.current_freq_input = 1000000 # Default to 1MHz
        self.step_size = 1000 # 1kHz steps
        
        self.last_counter = self.encoder.counter

        self.nav_stack = NavStack(self)
        root = MenuPage("Main Menu\n", [
            MenuItem("Add Frequency", page_factory=lambda app: AddFreqPage()),
            MenuItem("Remove Freq", page_factory=lambda app: FreqListPage("remove")),
            MenuItem("Listen Freq", page_factory=lambda app: FreqListPage("listen")),
        ], show_back=False)
        self.nav_stack.push(root)

    def _init_hardware(self):
        self.i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
        devices = self.i2c.scan()
        if not devices:
            raise RuntimeError("No I2C devices found")
        self.oled_addr = 0x3C if 0x3C in devices else devices[0]
        self.oled = SSD1306_I2C(128, 64, self.i2c, addr=self.oled_addr)
        
        self.encoder = QuadratureEncoder(pin_a=ENC_A, pin_b=ENC_B, ppr=1)
        self.button = ButtonHandler(pin=ENC_BUTTON, name="Center Click")

    def run(self):
        self.update_display()
        while True:
            self.handle_input()
            time.sleep_ms(50)

    def handle_input(self):
        current_counter = self.encoder.counter
        diff = current_counter - self.last_counter
        self.last_counter = current_counter

        self.button.update()
        clicked, long_press = self.button.get_events()

        if long_press and self.nav_stack.can_pop():
            self.nav_stack.pop()
            self.update_display()
            return

        if diff != 0 or clicked:
            self.nav_stack.current.handle_input(self, diff, clicked, False)
            self.update_display()

    def update_display(self):
        """Render the current page to the OLED."""
        self.oled.fill(0)
        self.nav_stack.current.draw(self.oled)
        self.oled.show()

if __name__ == "__main__":
    app = SDRApp()
    app.run()
