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

BLACK = 0x0000
WHITE = 0xFFFF
GREY = 0x8410
RED = 0xF800
AMBER = 0xFD20
GREEN = 0x07E0

W, H = 240, 320
MARGIN = 6
HALF = (W - 2 * MARGIN) // 2


def soc(board, volts):
    """State of charge from pack voltage. Crude on purpose - under load this
    reads low, which is the honest direction to be wrong in."""
    span = board.v_full - board.v_empty
    return max(0.0, min(1.0, (volts - board.v_empty) / span))


def _speed(f, b):
    return "%3d" % round(abs(b.kph_for_erpm(f.rpm)))


def _bar_fill(f, b):
    return int((W - 2 * MARGIN) * soc(b, f.input_voltage))


def _volts(f, b):
    return "%4.1fV  %3d%%" % (f.input_voltage, round(soc(b, f.input_voltage) * 100))


class Riding:
    """Regions are (key, x, y, w, h, value_fn, draw_fn)."""

    def __init__(self):
        self._drawn = {}

    # -- element painters --------------------------------------------------

    def _big_speed(self, d, f, b, v):
        widgets.text(d, MARGIN, 24, self._drawn.get("speed"), v,
                     scale=6, color=WHITE, bg=BLACK)

    def _bar(self, d, f, b, v):
        bar_w = W - 2 * MARGIN
        d.fill_rectangle(MARGIN, 96, bar_w, 18, GREY)
        if v:
            pct = v / bar_w
            col = GREEN if pct > 0.5 else AMBER if pct > 0.2 else RED
            d.fill_rectangle(MARGIN, 96, v, 18, col)

    def _volts_line(self, d, f, b, v):
        widgets.text(d, MARGIN, 120, self._drawn.get("volts"), v,
                     color=WHITE, bg=BLACK)

    def _cell(self, key, x, y, color=lambda f, b: WHITE):
        """The label is static furniture; only the value is ever redrawn."""
        def paint(d, f, b, v):
            widgets.text(d, x, y + 12, self._drawn.get(key), v,
                         scale=2, color=color(f, b), bg=BLACK)
        return paint

    def _fault(self, d, f, b, v):
        # The banner is a filled block, not text, so it has to be cleared
        # explicitly when the fault goes away - otherwise it stays on the
        # glass after the ESC has recovered, which is worse than never
        # showing it.
        if not v:
            d.set_color(BLACK, BLACK)
            d.fill_rectangle(0, 272, W, 24, BLACK)
            return
        d.set_color(WHITE, RED)
        d.fill_rectangle(0, 272, W, 24, RED)
        d.set_pos(MARGIN, 280)
        d.print(v)

    # -- layout ------------------------------------------------------------

    def regions(self):
        hot = lambda f, b: RED if f.temp_fet_filtered >= b.temp_derate_start else WHITE
        return (
            ("speed", MARGIN, 24, 150, 48, _speed, self._big_speed),
            ("bar", MARGIN, 96, W - 2 * MARGIN, 18, _bar_fill, self._bar),
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
        d.set_color(GREY, BLACK)
        d.set_pos(MARGIN + 150, 60)
        d.print("km/h")
        for label, x, y in (("MOTOR A", MARGIN, 148), ("BATT A", MARGIN + HALF, 148),
                            ("FET C", MARGIN, 208), ("USED Ah", MARGIN + HALF, 208)):
            d.set_color(GREY, BLACK)
            d.set_pos(x, y)
            d.print(label)

    # -- rendering ---------------------------------------------------------

    def render(self, d, f, b, full=False):
        if full or not self._drawn:
            d.set_color(WHITE, BLACK)
            d.erase()
            self._drawn = {}
            self.chrome(d)
        for key, x, y, w, h, value_of, paint in self.regions():
            v = value_of(f, b)
            # A region whose value is unchanged is already correct on the
            # glass. Repainting it costs SPI bytes and buys nothing.
            if not full and self._drawn.get(key, object()) == v:
                continue
            if full:
                self._drawn.pop(key, None)
            paint(d, f, b, v)
            self._drawn[key] = v


def render(d, frame, board):
    """One-shot full repaint. Kept for callers that do not hold state."""
    Riding().render(d, frame, board, full=True)
