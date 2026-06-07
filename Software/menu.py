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


class SDRApp:
    """
    The main application class that ties together hardware interfaces 
    and handles the menu states and logic.
    """
    def __init__(self):
        self._init_hardware()
        
        # Sorted array holding the saved frequencies
        self.freqs = [] 
        
        # Setup Menus
        self.main_menu = Menu("Main Menu\n", [
            "Add Frequency",
            "Remove Freq",
            "Listen Freq"
        ])
        self.freq_menu = Menu("Select Freq\n", [])
        
        # State machine: "main", "add", "remove", "listen"
        self.state = "main"
        
        # Add frequency properties
        self.current_freq_input = 1000000 # Default to 1MHz
        self.step_size = 1000 # 1kHz steps
        
        self.last_counter = self.encoder.counter

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
        #Main loop
        self.update_display()
        while True:
            self.handle_input()
            time.sleep_ms(50)

    def handle_input(self):
        #Poll the encoder and button, and route the changes to the correct state
        current_counter = self.encoder.counter
        diff = current_counter - self.last_counter
        self.last_counter = current_counter
        
        clicked = self.button.get_click()
        
        # Only process if there is a change
        if diff != 0 or clicked:
            if self.state == "main":
                self.handle_main_menu(diff, clicked)
            elif self.state == "add":
                self.handle_add_freq(diff, clicked)
            elif self.state == "remove":
                self.handle_remove_freq(diff, clicked)
            elif self.state == "listen":
                self.handle_listen_freq(diff, clicked)
                
            self.update_display()

    def handle_main_menu(self, diff, clicked):
        if diff > 0:
            self.main_menu.next()
        elif diff < 0:
            self.main_menu.prev()
            
        if clicked:
            selected = self.main_menu.get_selected()
            if selected == "Add Frequency":
                self.state = "add"
                # Keep previously typed freq or reset? Here we keep it.
            elif selected == "Remove Freq":
                self.state = "remove"
                self.update_freq_menu("Remove Freq")
            elif selected == "Listen Freq":
                self.state = "listen"
                self.update_freq_menu("Listen Freq")

    def update_freq_menu(self, title):
        """Populate the dynamic frequency menu based on saved frequencies."""
        self.freq_menu.title = title
        self.freq_menu.options = [f"{f} Hz" for f in self.freqs]
        self.freq_menu.selected_idx = 0
        self.freq_menu.scroll_offset = 0

    def handle_add_freq(self, diff, clicked):
        if diff != 0:
            self.current_freq_input += diff * self.step_size
            if self.current_freq_input < 0:
                self.current_freq_input = 0
                
        if clicked:
            # Save the new frequency
            if self.current_freq_input not in self.freqs:
                self.freqs.append(self.current_freq_input)
                self.freqs.sort()
            self.state = "main"

    def handle_remove_freq(self, diff, clicked):
        if diff > 0:
            self.freq_menu.next()
        elif diff < 0:
            self.freq_menu.prev()
            
        if clicked:
            if self.freqs:
                idx = self.freq_menu.selected_idx
                self.freqs.pop(idx)
            # Return to main menu after action
            self.state = "main"

    def handle_listen_freq(self, diff, clicked):
        if diff > 0:
            self.freq_menu.next()
        elif diff < 0:
            self.freq_menu.prev()
            
        if clicked:
            if self.freqs:
                # Placeholder for listening logic where a frequency is actually tuned
                selected_freq = self.freqs[self.freq_menu.selected_idx]
                print(f"Now tuning to {selected_freq} Hz...")
            self.state = "main"

    def update_display(self):
        """Render the current state to the OLED."""
        self.oled.fill(0)
        
        if self.state == "main":
            self.main_menu.draw(self.oled)
            
        elif self.state == "add":
            self.oled.text("Add Frequency", 0, 0, 1)
            self.oled.hline(0, 10, 128, 1)
            self.oled.text(f"Val: {self.current_freq_input} Hz", 0, 25, 1)
            self.oled.text("Click to save", 0, 50, 1)
            
        elif self.state == "remove":
            self.freq_menu.draw(self.oled)
            if not self.freqs:
                self.oled.text("Click to back", 0, 50, 1)
                
        elif self.state == "listen":
            self.freq_menu.draw(self.oled)
            if not self.freqs:
                self.oled.text("Click to back", 0, 50, 1)
            
        self.oled.show()

if __name__ == "__main__":
    app = SDRApp()
    app.run()
