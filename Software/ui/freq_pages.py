from ui.page import Page
from ui.menu_page import BACK_LABEL


class ValueEditorPage(Page):
    """Adjust a numeric value with the encoder; click to save, long-press to cancel."""

    def __init__(self, title, value_attr, step_attr, min_value=0, on_save=None):
        self.title = title
        self.value_attr = value_attr
        self.step_attr = step_attr
        self.min_value = min_value
        self.on_save = on_save
        self._draw_app = None

    def on_enter(self, app):
        self._draw_app = app

    def handle_input(self, app, diff, clicked, long_press):
        value = getattr(app, self.value_attr)
        step = getattr(app, self.step_attr)

        if diff != 0:
            value += diff * step
            if value < self.min_value:
                value = self.min_value
            setattr(app, self.value_attr, value)

        if clicked and self.on_save:
            self.on_save(app)
            app.nav_stack.pop()

        return "redraw"

    def draw(self, oled):
        app = self._draw_app
        if app is None:
            return
        oled.text(self.title, 0, 0, 1)
        oled.hline(0, 10, 128, 1)
        oled.text(f"Val: {getattr(app, self.value_attr)} Hz", 0, 25, 1)
        Page.draw_footer(oled, "Hold: Back", y=44)
        Page.draw_footer(oled, "Click: Save", y=54)


class AddFreqPage(ValueEditorPage):
    """Page for entering and saving a new frequency."""

    def __init__(self):
        super().__init__(
            title="Add Frequency",
            value_attr="current_freq_input",
            step_attr="step_size",
            min_value=0,
            on_save=self._save_freq,
        )

    def _save_freq(self, app):
        value = app.current_freq_input
        if value not in app.freqs:
            app.freqs.append(value)
            app.freqs.sort()


class FreqListPage(Page):
    """Selectable frequency list for remove or listen actions."""

    def __init__(self, mode):
        self.mode = mode
        self.title = "Remove Freq" if mode == "remove" else "Listen Freq"
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
        options.extend(f"{f} Hz" for f in app.freqs)
        self.menu.title = self.title + "\n"
        self.menu.options = options
        self.menu.selected_idx = 0
        self.menu.scroll_offset = 0

    def _freq_index(self):
        idx = self.menu.selected_idx
        if idx == 0:
            return None
        return idx - 1

    def handle_input(self, app, diff, clicked, long_press):
        if diff > 0:
            self.menu.next()
        elif diff < 0:
            self.menu.prev()

        if clicked:
            selected = self.menu.get_selected()
            if selected == BACK_LABEL:
                app.nav_stack.pop()
                return "redraw"

            freq_idx = self._freq_index()
            if freq_idx is not None and freq_idx < len(app.freqs):
                if self.mode == "remove":
                    app.freqs.pop(freq_idx)
                    self.on_enter(app)
                elif self.mode == "listen":
                    selected_freq = app.freqs[freq_idx]
                    print(f"Now tuning to {selected_freq} Hz...")

        return "redraw"

    def draw(self, oled):
        self.menu.draw(oled)
        if self._draw_app is not None and not self._draw_app.freqs:
            oled.text("  (No freqs)", 0, 27, 1)
        Page.draw_footer(oled, "Hold: back")
