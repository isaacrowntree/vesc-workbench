"""Screen set, button handling and the menu - the parts that make it a UI.

A screen is a pure render function. This is the state around them: which one is
showing, what the buttons do, and what the menu offers. It is deliberately
testable without a device - `App` takes button events as plain strings, so a
test can drive a whole session and assert what got drawn.
"""

UP, DOWN, ENTER = "up", "down", "enter"
HOLD = "hold"          # enter, held


class App:
    """Screen switching and menu state.

    Buttons follow the stock display's convention so muscle memory survives:
      up / down   cycle screens (or move within the menu)
      enter       enters the menu, selects inside it
      hold enter  leaves the menu
    """

    def __init__(self, screens, board, theme=None, menu=None):
        self.screens = list(screens)          # [(key, ScreenClass), ...]
        self.board = board
        self.theme = theme
        self.index = 0
        self.menu = menu or Menu()
        self.in_menu = False
        self._live = {}
        self._dirty = True

    # -- state ------------------------------------------------------------

    @property
    def key(self):
        return self.screens[self.index][0]

    def screen(self):
        key, cls = self.screens[self.index]
        if key not in self._live:
            self._live[key] = cls(self.theme)
        return self._live[key]

    def press(self, button):
        """Handle one button event. Returns True if a redraw is needed."""
        if self.in_menu:
            if button == HOLD:
                self.in_menu = False
            elif button == UP:
                self.menu.prev()
            elif button == DOWN:
                self.menu.next()
            elif button == ENTER:
                self.menu.activate(self)
            self._dirty = True
            return True

        if button == ENTER:
            self.in_menu = True
        elif button == UP:
            self.index = (self.index - 1) % len(self.screens)
        elif button == DOWN:
            self.index = (self.index + 1) % len(self.screens)
        elif button == HOLD:
            return False
        self._dirty = True
        return True

    def set_theme(self, theme):
        """Switching theme invalidates every cached screen: their colours and
        their record of what is on the glass are both wrong now."""
        self.theme = theme
        self._live = {}
        self._dirty = True

    # -- drawing ----------------------------------------------------------

    def render(self, d, frame):
        if self.in_menu:
            self.menu.render(d, self, full=self._dirty)
        else:
            self.screen().render(d, frame, self.board, full=self._dirty)
        self._dirty = False


class MenuItem:
    def __init__(self, label, values=None, on_select=None):
        self.label = label
        self.values = list(values) if values else None
        self.pos = 0
        self.on_select = on_select

    @property
    def value(self):
        return self.values[self.pos] if self.values else None

    def activate(self, app):
        if self.values:
            self.pos = (self.pos + 1) % len(self.values)
        if self.on_select:
            self.on_select(app, self.value)


class Menu:
    """A short list. Long menus on a 2.8 inch screen are a scrolling exercise
    nobody enjoys with gloves on."""

    ROW_H = 28
    TOP = 44

    def __init__(self, items=None):
        self.items = items or []
        self.cursor = 0

    def next(self):
        if self.items:
            self.cursor = (self.cursor + 1) % len(self.items)

    def prev(self):
        if self.items:
            self.cursor = (self.cursor - 1) % len(self.items)

    def activate(self, app):
        if self.items:
            self.items[self.cursor].activate(app)

    def render(self, d, app, full=True):
        t = app.screen().t
        d.set_color(t.ink, t.ground)
        d.erase()
        d.set_color(t.dim, t.ground)
        d.set_pos(8, 16)
        d.print("MENU")
        for i, item in enumerate(self.items):
            y = self.TOP + i * self.ROW_H
            selected = i == self.cursor
            if selected:
                d.fill_rectangle(0, y - 4, 240, self.ROW_H - 4, t.track)
            d.set_color(t.ink if selected else t.dim, t.ground)
            d.set_pos(8, y)
            d.print(item.label)
            if item.values:
                d.set_color(t.accent if selected else t.dim, t.ground)
                d.set_pos(150, y)
                d.print(str(item.value))
