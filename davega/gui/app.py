"""The state machine: what is on screen, what the buttons do, what still owes
a frame.

Animation is not handled per-screen by the caller. Every state answers the same
two questions - "draw yourself" and "are you settled?" - and one loop drives
them. A screen that wants to animate says so by not being settled; nothing
outside it needs to know how, or that it animates at all.

    app = App(SCREENS, board)
    while True:
        frame = read_telemetry()
        while app.tick(display, frame):     # drains any animation
            pass
"""
from .base import W, H
from .startup import Splash


def _light_key(key):
    """Themes are addressed by name; the variant rides along as a suffix so a
    screen only ever needs one string."""
    return (key or "nazare") + "@light"

UP, DOWN, ENTER = "up", "down", "enter"
HOLD = "hold"          # enter, held

SWEEP, SCREEN, MENU = "sweep", "screen", "menu"


class App:
    """States: sweep -> screen <-> menu.

    Buttons follow the stock display's convention so muscle memory survives:
      up / down   cycle screens (or move within the menu)
      enter       enters the menu, selects inside it
      hold enter  leaves the menu
    """

    MAX_FRAMES = 400        # a stuck animation must not lock the loop

    def __init__(self, screens, board, theme=None, menu=None, sweep=True,
                 name="NAZARE", light=False):
        self.screens = list(screens)
        self.board = board
        self.theme = theme
        self.light = light
        self.name = name
        self.index = 0
        self.menu = menu or Menu()
        self._live = {}
        self._splash = Splash(self._theme_key(), name) if sweep else None
        self.state = SWEEP if sweep else SCREEN
        self._dirty = True
        self._frames = 0

    # -- state ------------------------------------------------------------

    @property
    def key(self):
        return self.screens[self.index][0]

    @property
    def in_menu(self):
        return self.state == MENU

    def screen(self):
        key, cls = self.screens[self.index]
        if key not in self._live:
            # Every screen is told the whole set and its place in it, so it
            # can draw the page dots that make five views read as one
            # instrument rather than five unrelated ones.
            names = tuple(k for k, _ in self.screens)
            self._live[key] = cls(self.theme if not self.light
                                  else _light_key(self.theme), names, self.index)
        return self._live[key]

    def current(self):
        """The object that owns the screen right now."""
        if self.state == SWEEP:
            return self._splash
        return self.screen()

    def settled(self):
        """True when nothing on screen still owes a frame."""
        obj = self.current()
        return not hasattr(obj, "settled") or obj.settled()

    def _goto(self, state):
        if self.state == MENU and state != MENU and self.menu.on_close:
            self.menu.on_close(self)
        self.state = state
        self._dirty = True

    # -- input ------------------------------------------------------------

    def press(self, button):
        """Handle one button event. Returns True if a redraw is needed."""
        if self.state == SWEEP:
            # Any press skips the sweep. Nobody wants to watch it twice.
            self._goto(SCREEN)
            return True

        if self.state == MENU:
            if button == HOLD:
                self._goto(SCREEN)
            elif button == UP:
                self.menu.prev()
            elif button == DOWN:
                self.menu.next()
            elif button == ENTER:
                # `activate` may change the theme, and `set_theme` sets
                # `_dirty` itself - which is the one case the menu does have
                # to repaint whole, because every colour on it just changed.
                # Marking every press dirty meant a full-screen erase for a
                # cursor move, and a flash each time you pressed anything.
                self.menu.activate(self)
            return True

        if button == ENTER:
            self._goto(MENU)
        elif button == UP:
            self.index = (self.index - 1) % len(self.screens)
            self._dirty = True
        elif button == DOWN:
            self.index = (self.index + 1) % len(self.screens)
            self._dirty = True
        elif button == HOLD:
            return False
        return True

    def set_light(self, light):
        """Day or night. Every cached screen holds colours and a record of
        what is on the glass; both are wrong now."""
        self.light = bool(light)
        self._live = {}
        if self._splash:
            self._splash = Splash(self._theme_key(), self.name)
        self._dirty = True

    def _theme_key(self):
        return _light_key(self.theme) if self.light else self.theme

    def set_theme(self, theme):
        """Switching theme invalidates every cached screen: their colours and
        their record of what is on the glass are both wrong now."""
        self.theme = theme
        self._live = {}
        if self._splash:
            self._splash = Splash(self._theme_key(), self.name)
        self._dirty = True

    # -- the loop ---------------------------------------------------------

    def tick(self, d, frame):
        """Draw one frame. Returns True if another is owed straight away
        (an animation is mid-flight), False if the screen is settled and the
        caller should wait for new telemetry."""
        if self.state == MENU:
            self.menu.render(d, self, full=self._dirty)
            self._dirty = False
            return False

        obj = self.current()
        obj.render(d, frame, self.board, full=self._dirty)
        self._dirty = False
        self._frames += 1

        if self.state == SWEEP:
            if self._splash.settled() or self._frames > self.MAX_FRAMES:
                self._goto(SCREEN)
            return True

        return not self.settled() and self._frames <= self.MAX_FRAMES

    def render(self, d, frame):
        """Draw until settled. For callers that do not run their own loop."""
        n = 0
        while self.tick(d, frame) and n < self.MAX_FRAMES:
            n += 1
        return n


class MenuItem:
    def __init__(self, label, values=None, on_select=None):
        self.label = label
        self.values = list(values) if values else None
        self.pos = 0
        self.on_select = on_select

    @property
    def value(self):
        return self.values[self.pos] if self.values else None

    @property
    def position(self):
        """"3/10", so cycling a long list is navigable rather than a guess."""
        if not self.values:
            return ""
        return "%d/%d" % (self.pos + 1, len(self.values))

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

    def __init__(self, items=None, on_close=None):
        self.items = items or []
        self.cursor = 0
        #: Called once when the rider leaves the menu. Settings are applied
        #: live as they are cycled but persisted here, because cycling ten
        #: themes one press at a time is ten writes to flash for nine
        #: settings nobody kept.
        self.on_close = on_close
        self._drawn = {}

    def next(self):
        if self.items:
            self.cursor = (self.cursor + 1) % len(self.items)

    def prev(self):
        if self.items:
            self.cursor = (self.cursor - 1) % len(self.items)

    def activate(self, app):
        if self.items:
            self.items[self.cursor].activate(app)

    #: Widest value we will lay out for. Longer ones are cut rather than
    #: allowed to run off the panel.
    VAL_X = 128
    VAL_CHARS = 13

    def render(self, d, app, full=True):
        """Only the rows that changed.

        This used to erase the whole panel and redraw it, and `tick` calls it
        once per telemetry pass - so the menu wiped and repainted itself five
        times a second and read as a flicker you could not hold still enough
        to use. A row is repainted when its highlight or its value changes,
        and otherwise nothing is drawn at all.
        """
        t = app.screen().t
        if full:
            self._drawn = {}
            d.set_color(t.ink, t.ground)
            d.erase()
            d.set_color(t.dim, t.ground)
            d.set_pos(8, 16)
            d.print("MENU")
            # The way out is a three second hold, which nobody guesses.
            d.set_pos(8, H - 20)
            d.print("HOLD TO GO BACK")

        for i, item in enumerate(self.items):
            selected = i == self.cursor
            state = (selected, item.value, item.position)
            if self._drawn.get(i) == state:
                continue
            self._drawn[i] = state
            self._row(d, t, i, item, selected)

    def _row(self, d, t, i, item, selected):
        y = self.TOP + i * self.ROW_H
        back = t.track if selected else t.ground
        d.fill_rectangle(0, y - 4, W, self.ROW_H - 4, back)
        d.set_color(t.ink if selected else t.dim, back)
        d.set_pos(8, y)
        d.print(item.label)
        if not item.values:
            return
        d.set_color(t.accent if selected else t.dim, back)
        d.set_pos(self.VAL_X, y)
        d.print(str(item.value)[:self.VAL_CHARS])
        # Where you are in the list. Ten themes cycled one press at a time is
        # a guessing game without it.
        if len(item.values) > 2:
            d.set_color(t.dim, back)
            d.set_pos(W - 40, y)
            d.print(item.position)
