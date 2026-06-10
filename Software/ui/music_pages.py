from page import Page
from menu_page import BACK_LABEL

class MusicListPage(Page):
    """Selectable list of WAV files from the SD card."""

    def __init__(self):
        self.title = "Music Player"
        self.menu = None
        self._draw_app = None

    def _ensure_menu(self):
        if self.menu is None:
            from menu import Menu
            self.menu = Menu(self.title + "\n", [])

    def on_enter(self, app):
        self._ensure_menu()
        self._draw_app = app
        options = [BACK_LABEL]
        
        try:
            files = app.playback_controller.list_tracks()
            options.extend(files)
        except Exception as e:
            print("Failed to list tracks:", e)
            
        self.menu.options = options
        self.menu.selected_idx = 0
        self.menu.scroll_offset = 0

    def _selected_item(self):
        idx = self.menu.selected_idx
        if idx == 0:
            return None
        return self.menu.options[idx]

    def handle_input(self, app, diff, clicked, long_press):
        if diff > 0:
            self.menu.next()
        elif diff < 0:
            self.menu.prev()

        if clicked:
            selected = self._selected_item()
            if selected is None:
                app.nav_stack.pop()
                return "redraw"
            
            # Start playback page
            app.nav_stack.push(PlaybackPage(selected))

        return "redraw"

    def draw(self, oled):
        self.menu.draw(oled)
        if len(self.menu.options) <= 1:
            oled.text("  (No files)", 0, 27, 1)

class PlaybackPage(Page):
    """Shows playback controls for a specific track."""

    def __init__(self, filename):
        self.filename = filename
        self.title = "Playing:"
        self.menu = None
        self._draw_app = None

    def _ensure_menu(self):
        if self.menu is None:
            from menu import Menu
            self.menu = Menu(self.title + "\n", ["Pause", "Exit"])

    def on_enter(self, app):
        self._ensure_menu()
        self._draw_app = app
        app.playback_controller.play(self.filename)
        self.menu.selected_idx = 0
        self.menu.scroll_offset = 0

    def handle_input(self, app, diff, clicked, long_press):
        if diff > 0:
            self.menu.next()
        elif diff < 0:
            self.menu.prev()

        if clicked:
            selected = self.menu.get_selected()
            if selected == "Exit":
                app.playback_controller.stop()
                app.nav_stack.pop()
            elif selected == "Pause" or selected == "Play":
                app.playback_controller.toggle_pause()
                # Update menu text
                if app.playback_controller.is_playing():
                    self.menu.options[0] = "Pause"
                else:
                    self.menu.options[0] = "Play"

        return "redraw"

    def draw(self, oled):
        oled.text(self.title, 0, 0, 1)
        oled.hline(0, 10, 128, 1)
        oled.text(self.filename[:16], 0, 15, 1)
        
        # Draw the menu options
        y = 30
        for i, opt in enumerate(self.menu.options):
            prefix = ">" if i == self.menu.selected_idx else " "
            oled.text(f"{prefix} {opt}", 0, y, 1)
            y += 12
