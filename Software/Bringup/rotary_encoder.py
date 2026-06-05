"""
Quadrature Rotary Encoder and Button Controller
================================================
Reads a rotary encoder with detent detection and handles button inputs on RP2040.

Code structure generated with GitHub Copilot (Claude Haiku 4.5).
Modified, debugged, and hardware-tested by Jeffrey McCormick in Lab 1.

Hardware Setup:
- Rotary Encoder A:        GPIO 21
- Rotary Encoder B:        GPIO 20
- Center Click Button:     GPIO 22

All inputs use internal pull-ups (pulled HIGH, go LOW when pressed).
The script tracks rotation using quadrature encoding and prints:
- Counter value when a detent is crossed
- "Button (ring) pressed" message
- "Center click pressed" message
"""

from machine import Pin
import time


class QuadratureEncoder:
    """Handle quadrature rotary encoder with detent detection."""
    
    def __init__(self, pin_a, pin_b, ppr=1):
        """
        Initialize quadrature encoder.
        
        Args:
            pin_a: GPIO pin for encoder A signal
            pin_b: GPIO pin for encoder B signal
            ppr: Pulses per rotation/detent (default 1 for our encoder, adjust if needed)
        """
        self.pin_a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self.pin_b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self.counter = 0
        self.last_a = self.pin_a.value()
        self.last_b = self.pin_b.value()
        self.step_count = 0
        self.ppr = ppr
        
        # Attach interrupt handlers for edge detection on both pins
        self.pin_a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.on_change)
        self.pin_b.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.on_change)
    
    def on_change(self, pin):
        """Handle changes on either encoder pin using quadrature logic."""
        current_a = self.pin_a.value()
        current_b = self.pin_b.value()
        
        # Only process on A pin changes for cleaner detent detection
        if current_a != self.last_a:
            # A changed: if B != A, we're going clockwise (increment)
            # if B == A, we're going counterclockwise (decrement)
            if current_b != current_a:
                self.step_count += 1
            else:
                self.step_count -= 1
            
            # Check if a detent has been crossed (complete quadrature cycle)
            if abs(self.step_count) >= self.ppr:
                complete_detents = int(self.step_count / self.ppr)
                self.counter += complete_detents
                self.step_count -= complete_detents * self.ppr
                direction = "CW" if complete_detents > 0 else "CCW"
                print(f"Detent crossed ({direction}) - Counter: {self.counter}")
        
        self.last_a = current_a
        self.last_b = current_b


class ButtonHandler:
    """Handle push button inputs with debouncing."""
    
    def __init__(self, pin, name, debounce_ms=20, callback=None):
        """
        Initialize button handler.
        
        Args:
            pin: GPIO pin number
            name: Display name for button
            debounce_ms: Debounce time in milliseconds
            callback: Optional function to call on press
        """
        self.pin = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.name = name
        self.debounce_ms = debounce_ms
        self.last_press_time = 0
        self.callback = callback
        self.flag = False
        
        # Attach interrupt for falling edge (button press, active LOW)
        self.pin.irq(trigger=Pin.IRQ_FALLING, handler=self.on_press)
    
    def on_press(self, pin):
        """Handle button press with debouncing."""
        current_time = time.ticks_ms()
        
        # Debounce: ignore if pressed too soon after last press
        if current_time - self.last_press_time < self.debounce_ms:
            return
        
        # Confirm button is still pressed (active LOW)
        if self.pin.value() == 0:
            self.last_press_time = current_time
            self.flag = True
            print(f"{self.name} pressed")
            if self.callback:
                self.callback()
                
    def get_click(self):
        """Return True if button was clicked since last check, and clear flag."""
        if self.flag:
            self.flag = False
            return True
        return False


if __name__ == "__main__":

    # Initialize encoder and buttons
    encoder = QuadratureEncoder(pin_a=18, pin_b=17, ppr=1)
    center_button = ButtonHandler(pin=5, name="Center click")

    print("=" * 50)
    print("Rotary Encoder and Button Controller")
    print("=" * 50)
    print("Encoder:     GPIO 21 (A) and GPIO 20 (B)")
    print("Center Button: GPIO 22")
    print("-" * 50)
    print("Turn the encoder or press buttons...\n")

    # Keep the script running
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nProgram stopped")
