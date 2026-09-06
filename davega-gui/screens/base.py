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
MARGIN = 6
HALF = (W - 2 * MARGIN) // 2


class RegionScreen:
    """Subclasses provide `_build_regions()` and optionally `chrome()`."""

    def __init__(self, theme=None):
        self._drawn = {}
        self.t = get_theme(theme)
        # Built once: rebuilding the table every frame allocates a dozen
        # tuples and closures per render, which is not free on an ESP32.
        self._regions = self._build_regions()

    def _build_regions(self):
        return ()

    def regions(self):
        return self._regions

    def chrome(self, d):
        """Static furniture, painted once. The part that cannot change."""

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

    def render(self, d, f, b, full=False):
        if full or not self._drawn:
            d.set_color(self.t.ink, self.t.ground)
            d.erase()
            self._drawn = {}
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
