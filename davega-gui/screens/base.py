"""The differential rendering engine every screen shares.

A screen declares regions - a key, a bounding box, a function that computes its
value, and a painter. Rendering repaints only the regions whose value moved,
and the painters use `widgets.text`, which repaints only the character cells
that differ. On this hardware a character costs ~8.6 ms and a draw call ~2.7 ms,
so that is the whole game.
"""
from . import widgets
from .themes import get as get_theme

W, H = 240, 320

# ---- the grid --------------------------------------------------------------
# Screens feel like one instrument when they share a skeleton, not just a
# palette. Every position on every screen comes from here, so a value in the
# left column sits at the same x whichever screen you are on, and switching
# screens does not move the furniture.
MARGIN = 8
GUTTER = 8
COLS = 2
COL_W = (W - 2 * MARGIN - GUTTER * (COLS - 1)) // COLS
HALF = COL_W                      # kept: reads better in two-column layouts

HEADER_H = 22                     # the status strip, on every screen
FOOTER_H = 14                     # page dots, on every screen
BODY_TOP = HEADER_H + 10
BODY_BOTTOM = H - FOOTER_H - 6

ROW = 38                          # vertical rhythm for stacked values

# One type scale, used the same way everywhere.
HERO = 6                          # the one number a screen is about
PRIMARY = 3                       # a headline value
VALUE = 2                         # a normal value
LABEL = 1                         # everything that names something


def col_x(i):
    return MARGIN + i * (COL_W + GUTTER)


def row_y(n, top=BODY_TOP):
    return top + n * ROW


class RegionScreen:
    """Subclasses provide `_build_regions()` and optionally `chrome()`."""

    #: set by App so a screen can draw its own place in the set
    siblings = ()
    position = 0

    def __init__(self, theme=None, siblings=(), position=0):
        self._drawn = {}
        self.t = get_theme(theme)
        self.siblings = siblings
        self.position = position
        # Built once: rebuilding the table every frame allocates a dozen
        # tuples and closures per render, which is not free on an ESP32.
        self._regions = self._build_regions()

    def _build_regions(self):
        return ()

    def regions(self):
        return self._regions

    #: shown in the status strip, and in the menu
    title = ""

    def chrome(self, d):
        """Static furniture, painted once. The part that cannot change.

        Subclasses extend this; they do not replace it - the header and footer
        are what make five screens read as one instrument.
        """
        self.header(d)
        self.footer(d)

    def header(self, d):
        """Screen name on the left. The right-hand side is live, so it is a
        region rather than chrome."""
        d.set_color(self.t.dim, self.t.ground)
        d.set_pos(MARGIN, 6)
        d.print(self.title or "")
        d.fill_rectangle(MARGIN, HEADER_H - 4, W - 2 * MARGIN, 1, self.t.track)

    def footer(self, d):
        """Page dots: which of the set you are on, so the screens read as a
        sequence rather than five unrelated views."""
        total = len(self.siblings) if self.siblings else 0
        if total < 2:
            return
        dot, gap = 4, 8
        span = total * dot + (total - 1) * (gap - dot)
        x = (W - span) // 2
        y = H - FOOTER_H + 4
        for i in range(total):
            on = i == self.position
            d.fill_rectangle(x + i * gap, y, dot, dot,
                             self.t.accent if on else self.t.track)

    def on_full(self, f, b):
        """A full repaint shows the truth, not a tween on its way to it.
        Screens with animation snap it here."""

    # -- helpers subclasses use -------------------------------------------

    def label(self, d, x, y, s):
        d.set_color(self.t.dim, self.t.ground)
        d.set_pos(x, y)
        d.print(s)

    def value_painter(self, key, x, y, scale=2, color=None):
        def paint(d, f, b, v):
            col = color(f, b, self.t) if color else self.t.ink
            widgets.text(d, x, y, self._drawn.get(key), v,
                         scale=scale, color=col, bg=self.t.ground)
        return paint

    def cell(self, key, x, y, label):
        """A labelled value. The label is chrome; only the value redraws."""
        return (label, x, y), self.value_painter(key, x, y + 12)

    # -- rendering ---------------------------------------------------------

    def status_regions(self):
        """The live half of the header: battery and link, same place on every
        screen. Subclasses concatenate this into their own regions."""
        return (
            ("hdr_soc", W - 96, 4, 56, 12,
             lambda f, b: "%3d%%" % round(100 * b.soc_for_voltage(f["input_voltage"])),
             self._hdr_soc),
            ("hdr_link", W - 30, 4, 22, 12,
             lambda f, b: "" if f.get("link_ok", True) else "NO ESC",
             self._hdr_link),
        )

    def _hdr_soc(self, d, f, b, v):
        widgets.text(d, W - 96, 6, self._drawn.get("hdr_soc"), v,
                     color=self.t.dim, bg=self.t.ground)

    def _hdr_link(self, d, f, b, v):
        d.set_color(self.t.ground, self.t.ground)
        d.fill_rectangle(W - 56, 4, 48, 12, self.t.ground)
        if v:
            d.set_color(self.t.warn, self.t.ground)
            d.set_pos(W - 56, 6)
            d.print(v)

    def render(self, d, f, b, full=False):
        if full or not self._drawn:
            d.set_color(self.t.ink, self.t.ground)
            d.erase()
            self._drawn = {}
            self.on_full(f, b)
            self.chrome(d)
        for key, x, y, w, h, value_of, paint in self.regions():
            v = value_of(f, b)
            if not full and self._drawn.get(key, _MISSING) == v:
                continue
            if full:
                self._drawn.pop(key, None)
            paint(d, f, b, v)
            self._drawn[key] = v


class _Missing:
    def __eq__(self, other):
        return False


_MISSING = _Missing()
