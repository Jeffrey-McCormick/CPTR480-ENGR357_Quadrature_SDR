import machine
import time
import sys

try:
    from si5351 import Si5351
    from ssd1306 import SSD1306_I2C
    from rotary_encoder import QuadratureEncoder, ButtonHandler
except ImportError:
    # If the modules are located in the Bringup folders during testing
    sys.path.append('Bringup')
    sys.path.append('Bringup/Load_files')
    from si5351 import Si5351
    from ssd1306 import SSD1306_I2C
    from rotary_encoder import QuadratureEncoder, ButtonHandler

sys.path.append('ui')
sys.path.append('player')

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

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


from page import NavStack
from menu_page import MenuPage, MenuItem
from freq_pages import AddFreqPage, FreqListPage
from music_pages import MusicListPage, PlaybackPage
from screen_mode_page import ScreenModePage
from PlaybackController import PlaybackController


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
        self.current_listen_freq = None
        
        self.last_counter = self.encoder.counter

        self.nav_stack = NavStack(self)
        
        radio_menu = MenuPage("Radio\n", [
            MenuItem("Add Frequency", page_factory=lambda app: AddFreqPage()),
            MenuItem("Remove Freq", page_factory=lambda app: FreqListPage("remove")),
            MenuItem("Listen Freq", page_factory=lambda app: FreqListPage("listen")),
        ], show_back=True)

        root = MenuPage("FrohnePod\n", [
            MenuItem("Radio", page_factory=lambda app: radio_menu),
            MenuItem("Music Player", page_factory=lambda app: MusicListPage()),
            MenuItem("Screen Mode", page_factory=lambda app: ScreenModePage()),
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

        # Initialize Si5351
        self.si5351 = None
        if 0x60 in devices:
            try:
                self.si5351 = Si5351(self.i2c)
                self.si5351.initialize()
                print("Si5351 initialized.")
            except Exception as e:
                print("Warning: failed to initialize Si5351:", e)
        else:
            print("Warning: Si5351 not found on I2C bus")

        # Initialize Playback Controller
        self.playback_controller = PlaybackController()
        try:
            self.playback_controller.initialize()
            print("Playback controller initialized.")
        except Exception as e:
            print("Warning: failed to initialize playback controller:", e)

    def tune_to(self, freq):
        """
        Tunes the Si5351 to 4 times the target listen frequency.
        """
        self.current_listen_freq = freq
        if not self.si5351:
            print("Si5351 not initialized, cannot tune.")
            return

        target_freq = 4 * freq
        print(f"Tuning Si5351 to LO = {target_freq} Hz (Listen Freq = {freq} Hz)...")
        
        try:
            self.si5351.set_quadrature(target_freq)
            print(f"Successfully tuned Si5351 to quadrature LO: {target_freq} Hz")
        except Exception as e:
            print("Error tuning Si5351:", e)

    async def run(self):
        self.update_display()
        while True:
            self.handle_input()
            await asyncio.sleep_ms(50)

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
    asyncio.run(app.run())
