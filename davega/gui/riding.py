"""The riding screen: one host, nine arrangements.

Sized for reading at speed rather than for looking tidy on a monitor. The
large numerals are drawn with `bigfont`, which renders the display's own 3x5
digits as rectangles and therefore has no size ceiling - the stock routine
tops out well below legibility because it builds each glyph in a 1650-pixel
framebuffer.

The arrangement itself lives in `layouts/`, chosen by the theme. This module
is what every arrangement gets for free: the tween plumbing, the fault-block
bookkeeping, and the contract with `RegionScreen`.
"""
from . import themes
from .anim import Tweened
from .base import RegionScreen, W, H
from .layouts import load, DEFAULT
from .layouts.kit import soc                      # noqa: F401  (public here)


class Riding(RegionScreen):
    title = "RIDING"

    def __init__(self, theme=None, siblings=(), position=0):
        t = themes.get(theme)
        self.lay = load(getattr(t, "layout", DEFAULT))()
        self._fault_shown = False
        self._tw = dict((k, Tweened(0.0, frames=fr, snap=sn))
                        for k, (fr, sn) in self.lay.tweens.items())
        self.grid_exceptions = self.lay.grid_exceptions
        self.overlap_exceptions = self.lay.overlap_exceptions
        self.shows_page_dots = self.lay.shows_page_dots
        # Layouts draw curves, which have to know where the panel ends.
        self.d_width, self.d_height = W, H
        RegionScreen.__init__(self, theme, siblings, position)

    # -- animation ---------------------------------------------------------

    def tw(self, key):
        """The current value of a tweened quantity, for a layout's painter."""
        return self._tw[key].value

    def on_full(self, f, b):
        self._fault_shown = False
        for k, tween in self._tw.items():
            tween.value = tween.target = self.lay.target(k, self, f, b)
            tween._step = tween.frames

    def on_frame(self, f, b):
        for k, tween in self._tw.items():
            tween.set(self.lay.target(k, self, f, b)).advance()

    def settled(self):
        for tween in self._tw.values():
            if not tween.settled:
                return False
        return True

    # -- delegation --------------------------------------------------------

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        self.lay.chrome(self, d)

    def footer(self, d):
        if self.shows_page_dots:
            RegionScreen.footer(self, d)

    def _build_regions(self):
        return self.status_regions() + tuple(self.lay.regions(self))


def render(d, frame, board, theme=None):
    Riding(theme).render(d, frame, board, full=True)
