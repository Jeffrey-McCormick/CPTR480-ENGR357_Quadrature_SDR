class Page:
    """Base class for a navigable OLED screen."""

    def on_enter(self, app):
        pass

    def on_exit(self, app):
        pass

    def handle_input(self, app, diff, clicked, long_press):
        return "noop"

    def draw(self, oled):
        pass

    @staticmethod
    def draw_footer(oled, text, y=52):
        oled.text(text[:16], 0, y, 1)


class NavStack:
    """Stack-based navigation for nested pages."""

    def __init__(self, app):
        self.app = app
        self._stack = []

    def push(self, page):
        if self._stack:
            self._stack[-1].on_exit(self.app)
        self._stack.append(page)
        page.on_enter(self.app)

    def pop(self):
        if len(self._stack) <= 1:
            return False
        self._stack[-1].on_exit(self.app)
        self._stack.pop()
        return True

    def replace(self, page):
        if self._stack:
            self._stack[-1].on_exit(self.app)
            self._stack.pop()
        self._stack.append(page)
        page.on_enter(self.app)

    def can_pop(self):
        return len(self._stack) > 1

    @property
    def current(self):
        return self._stack[-1]
