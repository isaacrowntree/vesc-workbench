"""Riding screen, drawn differentially.

A full repaint of this layout pushes ~90k pixels - more than the whole frame,
because erasing paints everything and then the content paints over it. At two
bytes a pixel that is ~181 kB down the SPI bus for a screen where, between one
frame and the next, usually a single digit changed.

So the screen is described as a set of *regions*, each with a value. Rendering
compares each region's value against what was last drawn there and repaints
only the ones that moved. `render()` still does a full repaint when asked, and
the test suite asserts the two produce identical pixels - which is what makes
the optimisation safe to trust.
"""

from . import widgets
from .anim import Tweened
from .base import RegionScreen, W, H, MARGIN, HALF



def soc(board, volts):
    """State of charge along the pack's discharge curve - the same curve the
    stock firmware uses, read off the device rather than approximated."""
    return board.soc_for_voltage(volts)


def _speed(f, b):
    return "%3d" % round(abs(b.kph_for_erpm(f.rpm)))


def _bar_target(f, b):
    return (W - 2 * MARGIN) * soc(b, f.input_voltage)


def _volts(f, b):
    return "%4.1fV  %3d%%" % (f.input_voltage, round(soc(b, f.input_voltage) * 100))


class Riding(RegionScreen):
    """Regions are (key, x, y, w, h, value_fn, draw_fn).

    The battery bar sweeps; the numbers snap. Animating a gauge costs a
    handful of pixels in one call, animating three large digits costs three
    characters at ~8.6 ms each - and a tweened numeric readout reads like a
    slot machine anyway.
    """

    def __init__(self, theme=None):
        # Declared before the region table is built, because a region closure
        # captures it.
        self._bar = Tweened(0.0, frames=6, snap=2.0)
        RegionScreen.__init__(self, theme)

    def settled(self):
        """True when nothing is mid-animation. A caller that renders only on
        new telemetry uses this to know it still owes frames."""
        return self._bar.settled

    # -- element painters --------------------------------------------------

    def _big_speed(self, d, f, b, v):
        widgets.text(d, MARGIN, 24, self._drawn.get("speed"), v,
                     scale=6, color=self.t.ink, bg=self.t.ground)

    def _bar_value(self, f, b):
        """Step the tween one frame and report where the bar should be now."""
        self._bar.set(_bar_target(f, b))
        return int(self._bar.advance())

    def _paint_bar(self, d, f, b, v):
        bar_w = W - 2 * MARGIN
        d.fill_rectangle(MARGIN, 96, bar_w, 18, self.t.track)
        if v:
            d.fill_rectangle(MARGIN, 96, v, 18, self.t.soc_color(v / bar_w))

    def _volts_line(self, d, f, b, v):
        widgets.text(d, MARGIN, 120, self._drawn.get("volts"), v,
                     color=self.t.ink, bg=self.t.ground)

    def _cell(self, key, x, y, color=None):
        """The label is static furniture; only the value is ever redrawn."""
        def paint(d, f, b, v):
            col = color(f, b) if color else self.t.ink
            widgets.text(d, x, y + 12, self._drawn.get(key), v,
                         scale=2, color=col, bg=self.t.ground)
        return paint

    def _fault(self, d, f, b, v):
        # The banner is a filled block, not text, so it has to be cleared
        # explicitly when the fault goes away - otherwise it stays on the
        # glass after the ESC has recovered, which is worse than never
        # showing it.
        if not v:
            d.set_color(self.t.ground, self.t.ground)
            d.fill_rectangle(0, 272, W, 24, self.t.ground)
            return
        d.set_color(self.t.ink, self.t.danger)
        d.fill_rectangle(0, 272, W, 24, self.t.danger)
        d.set_pos(MARGIN, 280)
        d.print(v)

    # -- layout ------------------------------------------------------------

    def _build_regions(self):
        hot = lambda f, b: self.t.temp_color(f.temp_fet_filtered, b.temp_derate_start)
        return (
            ("speed", MARGIN, 24, 150, 48, _speed, self._big_speed),
            ("bar", MARGIN, 96, W - 2 * MARGIN, 18, self._bar_value, self._paint_bar),
            ("volts", MARGIN, 120, W - 2 * MARGIN, 10, _volts, self._volts_line),
            ("motor_a", MARGIN, 148, HALF, 40,
             lambda f, b: "%4.0f" % f.avg_motor_current,
             self._cell("motor_a", MARGIN, 148)),
            ("batt_a", MARGIN + HALF, 148, HALF, 40,
             lambda f, b: "%4.0f" % f.avg_input_current,
             self._cell("batt_a", MARGIN + HALF, 148)),
            ("fet_c", MARGIN, 208, HALF, 40,
             lambda f, b: "%4.0f" % f.temp_fet_filtered,
             self._cell("fet_c", MARGIN, 208, hot)),
            ("used_ah", MARGIN + HALF, 208, HALF, 40,
             lambda f, b: "%4.1f" % f.amp_hours,
             self._cell("used_ah", MARGIN + HALF, 208)),
            ("fault", 0, 272, W, 24,
             lambda f, b: ("FAULT %d" % f.fault) if f.fault else "",
             self._fault),
        )

    def chrome(self, d):
        """Static furniture. Painted once, then never touched again - it is
        the part of the screen that cannot change."""
        d.set_color(self.t.dim, self.t.ground)
        d.set_pos(MARGIN + 150, 60)
        d.print("km/h")
        for label, x, y in (("MOTOR A", MARGIN, 148), ("BATT A", MARGIN + HALF, 148),
                            ("FET C", MARGIN, 208), ("USED Ah", MARGIN + HALF, 208)):
            d.set_color(self.t.dim, self.t.ground)
            d.set_pos(x, y)
            d.print(label)


def render(d, frame, board, theme=None):
    """One-shot full repaint. Kept for callers that do not hold state."""
    Riding(theme).render(d, frame, board, full=True)
