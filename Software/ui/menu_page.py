from ui.page import Page

BACK_LABEL = "< Back"


class MenuItem:
    """Declarative menu entry that navigates to a page or runs an action."""

    def __init__(self, label, page_factory=None, action=None):
        self.label = label
        self.page_factory = page_factory
        self.action = action


class MenuPage(Page):
    """Selectable list menu built from MenuItem definitions."""

    def __init__(self, title, items, show_back=False):
        self.title = title
        self.items = list(items)
        self.show_back = show_back
        self.menu = None

    def _ensure_menu(self):
        if self.menu is None:
            from menu import Menu
            self.menu = Menu(self.title, [])

    def _build_options(self):
        labels = []
        if self.show_back:
            labels.append(BACK_LABEL)
        labels.extend(item.label for item in self.items)
        self.menu.options = labels
        self.menu.title = self.title

    def on_enter(self, app):
        self._ensure_menu()
        self._build_options()
        self.menu.selected_idx = 0
        self.menu.scroll_offset = 0

    def _selected_item(self):
        idx = self.menu.selected_idx
        if self.show_back:
            if idx == 0:
                return None
            idx -= 1
        if idx < len(self.items):
            return self.items[idx]
        return None

    def handle_input(self, app, diff, clicked, long_press):
        if diff > 0:
            self.menu.next()
        elif diff < 0:
            self.menu.prev()

        if clicked:
            selected = self.menu.get_selected()
            if self.show_back and selected == BACK_LABEL:
                app.nav_stack.pop()
                return "redraw"

            item = self._selected_item()
            if item is None:
                return "redraw"
            if item.page_factory:
                app.nav_stack.push(item.page_factory(app))
            elif item.action:
                item.action(app)

        return "redraw"

    def draw(self, oled):
        self.menu.draw(oled)
        if self.show_back:
            Page.draw_footer(oled, "Hold: back")
        else:
            Page.draw_footer(oled, "Click: select")
