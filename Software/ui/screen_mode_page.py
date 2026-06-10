from page import Page

class ScreenModePage(Page):
    """Placeholder page for Screen Mode functionality."""

    def __init__(self):
        self.title = "Screen Mode"

    def handle_input(self, app, diff, clicked, long_press):
        # Allow exiting by long press which is handled by NavStack globally
        # But we can also allow exit by click for convenience
        if clicked:
            app.nav_stack.pop()
        return "redraw"

    def draw(self, oled):
        oled.text(self.title, 0, 0, 1)
        oled.hline(0, 10, 128, 1)
        oled.text("Coming Soon!", 0, 25, 1)
