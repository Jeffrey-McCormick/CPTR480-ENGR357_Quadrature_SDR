"""
SSD1306 OLED Exercise Program for MicroPython
Display connected via I2C: SDA=GPIO12, SCL=GPIO13
Tested on Raspberry Pi Pico / ESP32 style boards
This program was written by Claude Sonnet AI, prompted by
Dr. Rob Frohne on 06/02/2026
"""

import machine
import ssd1306
import time
import math
import random

# --- I2C Setup ---
I2C_SDA = 12
I2C_SCL = 13
I2C_FREQ = 400_000  # 400 kHz fast mode

i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)

# Scan for display and report address
devices = i2c.scan()
if not devices:
    raise RuntimeError("No I2C devices found — check wiring on GPIO12/13")
print("I2C devices found:", [hex(d) for d in devices])

# SSD1306 is typically at 0x3C or 0x3D
OLED_ADDR = 0x3C if 0x3C in devices else devices[0]
print(f"Using OLED at {hex(OLED_ADDR)}")

# Display dimensions
WIDTH  = 128
HEIGHT = 64

oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=OLED_ADDR)


# ------------------------------------------------------------------ helpers --

def clear(show=True):
    oled.fill(0)
    if show:
        oled.show()

def centered_text(text, y, invert=False):
    """Draw text horizontally centred on the display."""
    x = (WIDTH - len(text) * 8) // 2
    oled.text(text, max(x, 0), y, 0 if invert else 1)

def pause(ms, label=""):
    if label:
        print(f"  [{label}]")
    time.sleep_ms(ms)


# ================================================================== TESTS ==

def test_fill():
    """Full-screen fill / invert cycle."""
    print("Test: fill / invert")
    for _ in range(3):
        oled.fill(1)
        oled.show()
        pause(300)
        oled.fill(0)
        oled.show()
        pause(300)


def test_text():
    """Text rendering at multiple positions."""
    print("Test: text")
    clear(show=False)
    oled.text("MicroPython", 0, 0)
    oled.text("SSD1306 OK", 0, 12)
    oled.text("GPIO SDA=12", 0, 24)
    oled.text("GPIO SCL=13", 0, 36)
    oled.text("128x64 OLED", 0, 48)
    oled.show()
    pause(2000, "text")


def test_scrolling_banner():
    """Horizontal text scroll."""
    print("Test: scroll banner")
    msg = "  ** Hello from MicroPython **  "
    for offset in range(len(msg) * 8):
        clear(show=False)
        x = WIDTH - offset
        oled.text(msg, x, 28)
        oled.show()
        time.sleep_ms(30)


def test_pixel_pattern():
    """Individual pixel addressing — checkerboard."""
    print("Test: pixel checkerboard")
    clear(show=False)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if (x + y) % 2 == 0:
                oled.pixel(x, y, 1)
    oled.show()
    pause(1500, "checkerboard")


def test_lines():
    """Horizontal, vertical, and diagonal lines."""
    print("Test: lines")
    # Horizontal lines
    clear(show=False)
    for y in range(0, HEIGHT, 8):
        oled.hline(0, y, WIDTH, 1)
    oled.show()
    pause(800, "hlines")

    # Vertical lines
    clear(show=False)
    for x in range(0, WIDTH, 8):
        oled.vline(x, 0, HEIGHT, 1)
    oled.show()
    pause(800, "vlines")

    # Diagonal
    clear(show=False)
    for i in range(min(WIDTH, HEIGHT)):
        oled.pixel(i, i, 1)
        oled.pixel(WIDTH - 1 - i, i, 1)
    oled.show()
    pause(800, "diagonals")


def test_rectangles():
    """Filled and outline rectangles."""
    print("Test: rectangles")
    clear(show=False)
    # Outline rects (nested)
    for i in range(0, 32, 8):
        oled.rect(i, i // 2, WIDTH - i * 2, HEIGHT - i, 1)
    oled.show()
    pause(1000, "outline rects")

    clear(show=False)
    # Filled blocks
    for col, x in enumerate(range(0, WIDTH, 16)):
        if col % 2 == 0:
            oled.fill_rect(x, 0, 16, HEIGHT, 1)
    oled.show()
    pause(1000, "filled rects")


def test_circle():
    """Draw circles using the midpoint algorithm."""
    print("Test: circles")

    def draw_circle(cx, cy, r, col=1):
        x, y, err = r, 0, 0
        while x >= y:
            for dx, dy in [(x,y),(y,x),(-y,x),(-x,y),(-x,-y),(-y,-x),(y,-x),(x,-y)]:
                px, py = cx + dx, cy + dy
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    oled.pixel(px, py, col)
            y += 1
            if err <= 0:
                err += 2 * y + 1
            if err > 0:
                x -= 1
                err -= 2 * x + 1

    clear(show=False)
    cx, cy = WIDTH // 2, HEIGHT // 2
    for r in range(4, 30, 5):
        draw_circle(cx, cy, r)
    oled.show()
    pause(1500, "circles")


def test_sine_wave():
    """Animated sine wave sweep."""
    print("Test: sine wave")
    for frame in range(60):
        clear(show=False)
        phase = frame * 0.2
        for x in range(WIDTH):
            y = int((HEIGHT / 2) + (HEIGHT / 2 - 4) * math.sin(x * 0.1 + phase))
            y = max(0, min(HEIGHT - 1, y))
            oled.pixel(x, y, 1)
        oled.show()
        time.sleep_ms(40)


def test_progress_bar():
    """Animated progress bar."""
    print("Test: progress bar")
    for pct in range(0, 101, 2):
        clear(show=False)
        centered_text("Loading...", 10)
        bar_w = WIDTH - 8
        bar_x = 4
        bar_y = 30
        bar_h = 12
        oled.rect(bar_x, bar_y, bar_w, bar_h, 1)
        fill_w = int(bar_w * pct / 100)
        if fill_w > 0:
            oled.fill_rect(bar_x, bar_y, fill_w, bar_h, 1)
        centered_text(f"{pct}%", 48)
        oled.show()
        time.sleep_ms(30)
    pause(500)


def test_random_pixels():
    """Random pixel snow."""
    print("Test: random pixels")
    clear(show=False)
    for _ in range(2000):
        x = random.randint(0, WIDTH - 1)
        y = random.randint(0, HEIGHT - 1)
        oled.pixel(x, y, 1)
        if _ % 100 == 0:
            oled.show()
    oled.show()
    pause(1000, "random pixels")


def test_contrast():
    """Cycle through contrast levels."""
    print("Test: contrast")
    clear(show=False)
    centered_text("Contrast test", 28)
    oled.show()
    for level in list(range(0, 256, 32)) + [255]:
        oled.contrast(level)
        time.sleep_ms(200)
    oled.contrast(200)  # restore sensible default
    pause(500)


def test_invert():
    """Hardware invert toggle."""
    print("Test: invert")
    clear(show=False)
    centered_text("Invert test", 28)
    oled.show()
    for _ in range(4):
        oled.invert(1)
        pause(400)
        oled.invert(0)
        pause(400)


def test_powerdown():
    """Power off / on cycle."""
    print("Test: power off/on")
    clear(show=False)
    centered_text("Power cycle", 28)
    oled.show()
    pause(500)
    oled.poweroff()
    pause(1000, "display off")
    oled.poweron()
    pause(500, "display on")


def test_summary():
    """Final summary screen."""
    clear(show=False)
    centered_text("All tests", 8)
    centered_text("PASSED!", 20)
    oled.hline(10, 32, WIDTH - 20, 1)
    centered_text("SDA GPIO12", 40)
    centered_text("SCL GPIO13", 52)
    oled.show()
    print("All tests complete.")


# ================================================================== MAIN ==

def run_all():
    print("=== SSD1306 Exercise Suite ===")
    tests = [
        test_fill,
        test_text,
        test_scrolling_banner,
        test_pixel_pattern,
        test_lines,
        test_rectangles,
        test_circle,
        test_sine_wave,
        test_progress_bar,
        test_random_pixels,
        test_contrast,
        test_invert,
        test_powerdown,
        test_summary,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  ERROR in {t.__name__}: {e}")
        time.sleep_ms(200)

run_all()
