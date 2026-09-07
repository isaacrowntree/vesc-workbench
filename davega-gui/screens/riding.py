"""The riding screen.

Sized for reading at speed rather than for looking tidy on a monitor. The
speed numeral is drawn with `bigfont`, which renders the display's own 3x5
digits as rectangles and therefore has no size ceiling - the stock routine
tops out well below legibility because it builds each glyph in a 1650-pixel
framebuffer.

Everything is pulled in tight. Negative space on a 2.8 inch panel at 40 km/h
is wasted screen.
"""
from . import widgets, bigfont
from .anim import Tweened
from .base import RegionScreen, W, H, MARGIN, col_x, VALUE, LABEL

RAIL_X, RAIL_W = 4, 9
RAIL_TOP, RAIL_BOT = 26, 294

SPEED_X, SPEED_Y, SPEED_S = 20, 28, 18      # 2 digits = 144 x 90
UNIT_X, UNIT_Y = 172, 100

FLOW_Y, FLOW_H = 136, 24
AMP_Y = 166

BATT_Y, BATT_H = 186, 26
BIG_Y, BIG_S = 224, 9                        # percent and range, 36 x 45
FOOT_Y = 280
BODY_L = 20                                  # clear of the rail


def soc(board, volts, frame=None):
    """State of charge. Prefers the runner's Rint-compensated figure, which
    does not sag under throttle."""
    if frame is not None and frame.get("soc") is not None:
        return frame["soc"]
    return board.soc_for_voltage(volts)


class Riding(RegionScreen):
    title = "RIDING"

    grid_exceptions = {
        "rail": "peripheral gauge, owns the left edge",
        "speed": "the hero numeral, centred on its own",
        "flow": "centre-zero meter spans the width",
        "amps": "reads against the meter",
        "batt": "segmented bar spans the width",
        "pct": "clear of the rail", "range": "paired with pct",
        "fet": "clear of the rail", "volts": "paired with fet",
        "gear": "state block, top right",
        "fault": "full-bleed banner",
    }

    def __init__(self, theme=None, siblings=(), position=0):
        self._rail = Tweened(0.0, frames=5, snap=4.0)
        self._flow = Tweened(0.0, frames=4, snap=3.0)
        RegionScreen.__init__(self, theme, siblings, position)

    def on_full(self, f, b):
        for tw, val in ((self._rail, self._rail_target(f, b)),
                        (self._flow, self._flow_target(f, b))):
            tw.value = tw.target = val
            tw._step = tw.frames

    def on_frame(self, f, b):
        self._rail.set(self._rail_target(f, b)).advance()
        self._flow.set(self._flow_target(f, b)).advance()

    def settled(self):
        return self._rail.settled and self._flow.settled

    def _rail_target(self, f, b):
        kph = abs(b.kph_for_erpm(f["rpm"]))
        return (RAIL_BOT - RAIL_TOP) * max(0.0, min(1.0, kph / 45.0))

    def _flow_target(self, f, b):
        half = (W - 2 * BODY_L) / 2.0
        return half * max(-1.0, min(1.0,
                                    f["avg_motor_current"] / max(1.0, b.motor_current)))

    # -- chrome ------------------------------------------------------------

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        t = self.t
        d.fill_rectangle(RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP, t.track)
        # The meter's track is furniture, painted once. Leaving it to the
        # delta painter meant a full repaint never drew it at all, and the
        # differential path did - so the two disagreed.
        d.fill_rectangle(BODY_L, FLOW_Y, W - 2 * BODY_L, FLOW_H, t.track)
        d.set_color(t.dim, t.ground)
        d.set_pos(UNIT_X, UNIT_Y)
        d.print("KM/H")
        d.set_pos(BODY_L, FLOW_Y - 10)
        d.print("REGEN")
        d.set_pos(W - BODY_L - 40, FLOW_Y - 10)
        d.print("DRIVE")

    # -- painters ----------------------------------------------------------

    def _paint_rail(self, d, f, b, v):
        """Only the difference is repainted: clearing the whole track and
        refilling it flashes, and this runs every frame."""
        t = self.t
        prev = self._drawn.get("rail", 0) or 0
        if v > prev:
            d.fill_rectangle(RAIL_X, RAIL_BOT - v, RAIL_W, v - prev, t.accent)
        elif v < prev:
            d.fill_rectangle(RAIL_X, RAIL_BOT - prev, RAIL_W, prev - v, t.track)

    def _paint_speed(self, d, f, b, v):
        widgets.big(d, SPEED_X, SPEED_Y, self._drawn.get("speed"), v,
                    SPEED_S, self.t.ink, self.t.ground)

    def _paint_flow(self, d, f, b, v):
        t = self.t
        mid = W // 2
        prev = self._drawn.get("flow", 0) or 0
        # Same idea as the rail: repaint the change, not the meter.
        if (v >= 0) != (prev >= 0):
            d.fill_rectangle(BODY_L, FLOW_Y, W - 2 * BODY_L, FLOW_H, t.track)
            prev = 0
        if v >= 0:
            if v > prev:
                d.fill_rectangle(mid + prev, FLOW_Y, v - prev, FLOW_H, t.warn)
            elif v < prev:
                d.fill_rectangle(mid + v, FLOW_Y, prev - v, FLOW_H, t.track)
        else:
            if v < prev:
                d.fill_rectangle(mid + v, FLOW_Y, prev - v, FLOW_H, t.accent)
            elif v > prev:
                d.fill_rectangle(mid + prev, FLOW_Y, v - prev, FLOW_H, t.track)
        d.fill_rectangle(mid - 1, FLOW_Y - 4, 2, FLOW_H + 8, t.ink)

    def _paint_batt(self, d, f, b, v):
        t = self.t
        segs, gap = 12, 3
        span = W - 2 * BODY_L
        sw = (span - gap * (segs - 1)) // segs
        colour = t.soc_color(v)
        for i in range(segs):
            lit = (i / float(segs)) < v
            d.fill_rectangle(BODY_L + i * (sw + gap), BATT_Y, sw, BATT_H,
                             colour if lit else t.track)

    def _big(self, key, x, colour=None):
        def paint(d, f, b, v):
            col = colour(f, b, self.t) if colour else self.t.ink
            widgets.big(d, x, BIG_Y, self._drawn.get(key), v, BIG_S, col,
                        self.t.ground)
        return paint

    def _paint_gear(self, d, f, b, v):
        t = self.t
        d.fill_rectangle(W - 34, 26, 26, 30, t.ground)
        bigfont.draw(d, W - 32, 28, v, 5, t.accent)

    def _paint_fault(self, d, f, b, v):
        t = self.t
        if not v:
            d.fill_rectangle(0, H - 24, W, 24, t.ground)
            return
        d.fill_rectangle(0, H - 24, W, 24, t.danger)
        d.set_color(t.ink, t.danger)
        d.set_pos(MARGIN, H - 18)
        d.print(v)

    # -- layout ------------------------------------------------------------

    def _build_regions(self):
        span = W - 2 * BODY_L
        hot = lambda f, b, t: t.temp_color(f["temp_fet_filtered"],
                                           b.temp_derate_start)
        return self.status_regions() + (
            ("rail", RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP,
             lambda f, b: int(self._rail.value), self._paint_rail),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S),
             lambda f, b: "%2d" % round(abs(b.kph_for_erpm(f["rpm"]))),
             self._paint_speed),
            ("gear", W - 34, 26, 26, 30,
             lambda f, b: str(f.get("gear", 3)), self._paint_gear),
            ("flow", BODY_L, FLOW_Y - 4, span, FLOW_H + 8,
             lambda f, b: int(self._flow.value), self._paint_flow),
            ("amps", BODY_L, AMP_Y, span, 12,
             lambda f, b: "%.0fA MOTOR   %.0fA PACK" % (f["avg_motor_current"],
                                                        f["avg_input_current"]),
             self.value_painter("amps", BODY_L, AMP_Y, scale=LABEL)),
            ("batt", BODY_L, BATT_Y, span, BATT_H,
             lambda f, b: soc(b, f["input_voltage"], f), self._paint_batt),
            ("pct", BODY_L, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "%d" % round(100 * soc(b, f["input_voltage"], f)),
             self._big("pct", BODY_L)),
            ("range", 132, BIG_Y, bigfont.width("999", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: ("%d" % round(f["s_range_km"])
                           if f.get("s_range_km") else "--"),
             self._big("range", 132)),
            ("fet", BODY_L, FOOT_Y, 100, 12,
             lambda f, b: "FET %.0f" % f["temp_fet_filtered"],
             self.value_painter("fet", BODY_L, FOOT_Y, scale=LABEL, color=hot)),
            ("volts", 132, FOOT_Y, 96, 12,
             lambda f, b: "%.1f V" % f["input_voltage"],
             self.value_painter("volts", 132, FOOT_Y, scale=LABEL)),
            ("fault", 0, H - 24, W, 24,
             lambda f, b: ("FAULT %d" % f["fault"]) if f["fault"] else "",
             self._paint_fault),
        )


def render(d, frame, board, theme=None):
    Riding(theme).render(d, frame, board, full=True)
