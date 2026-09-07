"""The riding screen: the Nazare layout.

The design the mockups promised, drawn for real. Everything on it earns its
place against the cost model - a character costs ~8.6 ms on this panel and a
draw call ~2.7 ms, so a screen crowded with numbers is a screen that updates in
lurches.

  * the speed rail up the left edge sweeps, so speed reads peripherally
  * one dominant numeral, with no unit label competing with it
  * power flow from a hard centre zero: regen left, drive right
  * the battery segmented, with percentage and range beside it
  * everything else grey until it matters

Digits snap and gauges sweep, which is what every good dash does and also what
this hardware can afford.
"""
from . import widgets
from .anim import Tweened
from .base import (RegionScreen, W, H, MARGIN, col_x, BODY_TOP, HERO_XL,
                   VALUE, LABEL)

# The rail and the hero numeral sit outside the two-column grid on purpose:
# this screen is the one place where a peripheral gauge and a single dominant
# number beat a tidy table.
RAIL_X, RAIL_W = 8, 6
RAIL_TOP, RAIL_BOT = 40, 268
SPEED_X, SPEED_Y = 30, 52
FLOW_Y, FLOW_H = 170, 14
BATT_Y, BATT_H = 214, 14
BIG_Y = 240
FOOT_Y = 276


def soc(board, volts, frame=None):
    """State of charge.

    Prefers the compensated figure the runner computes from the Rint model,
    which does not sag under throttle; falls back to the raw discharge curve
    when nothing has estimated the pack's resistance yet.
    """
    if frame is not None and frame.get("soc") is not None:
        return frame["soc"]
    return board.soc_for_voltage(volts)


class Riding(RegionScreen):
    title = "RIDING"

    #: regions that deliberately sit off the two-column grid, and why
    grid_exceptions = {
        "pct": "clear of the speed rail, which owns the left edge",
        "fet": "clear of the speed rail",
        "rail": "peripheral gauge, pinned to the edge",
        "speed": "the hero numeral is centred on its own",
        "kmh": "sits under the hero numeral",
        "flow": "centre-zero meter spans the width",
        "flow_a": "reads against the meter, right aligned",
        "batt": "segmented bar spans the width",
        "gear": "state block, top right",
        "fault": "full-bleed banner",
    }

    def __init__(self, theme=None, siblings=(), position=0):
        self._rail = Tweened(0.0, frames=6, snap=3.0)
        self._flow = Tweened(0.0, frames=5, snap=2.0)
        RegionScreen.__init__(self, theme, siblings, position)

    def on_full(self, f, b):
        for tween, value in ((self._rail, self._rail_target(f, b)),
                             (self._flow, self._flow_target(f, b))):
            tween.value = tween.target = value
            tween._step = tween.frames

    def on_frame(self, f, b):
        self._rail.set(self._rail_target(f, b)).advance()
        self._flow.set(self._flow_target(f, b)).advance()

    def settled(self):
        return self._rail.settled and self._flow.settled

    # -- targets -----------------------------------------------------------

    def _rail_target(self, f, b):
        kph = abs(b.kph_for_erpm(f["rpm"]))
        top = b.kph_for_erpm(b.erpm_for_kph(45.0))
        return (RAIL_BOT - RAIL_TOP) * max(0.0, min(1.0, kph / top))

    def _flow_target(self, f, b):
        span = (W - 2 * SPEED_X) / 2.0
        frac = f["avg_motor_current"] / max(1.0, b.motor_current)
        return span * max(-1.0, min(1.0, frac))

    # -- chrome ------------------------------------------------------------

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        t = self.t
        # rail track and its quarter ticks
        d.fill_rectangle(RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP, t.track)
        for i in range(5):
            y = RAIL_TOP + (RAIL_BOT - RAIL_TOP) * i // 4
            d.fill_rectangle(RAIL_X - 3, y, RAIL_W + 6, 1, t.dim)
        d.set_color(t.dim, t.ground)
        d.set_pos(SPEED_X + 2, SPEED_Y + 62)
        d.print("KM/H")
        d.set_pos(SPEED_X, FLOW_Y - 12)
        d.print("REGEN")
        d.set_pos(W - SPEED_X - 40, FLOW_Y - 12)
        d.print("DRIVE")

    # -- painters ----------------------------------------------------------

    def _paint_rail(self, d, f, b, v):
        t = self.t
        d.fill_rectangle(RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP, t.track)
        if v > 0:
            d.fill_rectangle(RAIL_X, RAIL_BOT - v, RAIL_W, v, t.accent)

    def _paint_speed(self, d, f, b, v):
        widgets.text(d, SPEED_X, SPEED_Y, self._drawn.get("speed"), v,
                     scale=HERO_XL, color=self.t.ink, bg=self.t.ground)

    def _paint_flow(self, d, f, b, v):
        t = self.t
        mid = W // 2
        d.fill_rectangle(SPEED_X, FLOW_Y, W - 2 * SPEED_X, FLOW_H, t.track)
        if v > 0:
            d.fill_rectangle(mid, FLOW_Y, int(v), FLOW_H, t.warn)
        elif v < 0:
            d.fill_rectangle(mid + int(v), FLOW_Y, int(-v), FLOW_H, t.accent)
        d.fill_rectangle(mid - 1, FLOW_Y - 3, 2, FLOW_H + 6, t.ink)

    def _paint_batt(self, d, f, b, v):
        t = self.t
        segs, gap = 14, 3
        span = W - 2 * SPEED_X
        sw = (span - gap * (segs - 1)) // segs
        for i in range(segs):
            lit = (i / float(segs)) < v
            d.fill_rectangle(SPEED_X + i * (sw + gap), BATT_Y, sw, BATT_H,
                             t.soc_color(v) if lit else t.track)

    def _paint_gear(self, d, f, b, v):
        t = self.t
        d.fill_rectangle(W - 40, 26, 26, 22, t.ground)
        d.set_color(t.accent, t.ground)
        d.set_pos(W - 34, 30)
        d.print(v, scale=VALUE)

    def _paint_fault(self, d, f, b, v):
        t = self.t
        if not v:
            d.fill_rectangle(0, H - 26, W, 26, t.ground)
            return
        d.fill_rectangle(0, H - 26, W, 26, t.danger)
        d.set_color(t.ink, t.danger)
        d.set_pos(MARGIN, H - 20)
        d.print(v)

    # -- layout ------------------------------------------------------------

    def _build_regions(self):
        span = W - 2 * SPEED_X
        return self.status_regions() + (
            ("rail", RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP,
             lambda f, b: int(self._rail.value),
             self._paint_rail),
            ("speed", SPEED_X, SPEED_Y, 150, 60,
             lambda f, b: "%2d" % round(abs(b.kph_for_erpm(f["rpm"]))),
             self._paint_speed),
            ("gear", W - 40, 26, 26, 22,
             lambda f, b: str(f.get("gear", 3)), self._paint_gear),
            ("flow", SPEED_X, FLOW_Y - 3, span, FLOW_H + 6,
             lambda f, b: int(self._flow.value),
             self._paint_flow),
            ("flow_a", W - SPEED_X - 60, FLOW_Y + FLOW_H + 4, 60, 14,
             lambda f, b: "%4.0fA" % f["avg_motor_current"],
             self.value_painter("flow_a", W - SPEED_X - 60,
                                FLOW_Y + FLOW_H + 4, scale=LABEL)),
            ("batt", SPEED_X, BATT_Y, span, BATT_H,
             lambda f, b: soc(b, f["input_voltage"], f), self._paint_batt),
            ("pct", SPEED_X, BIG_Y, 80, 22,
             lambda f, b: "%3d%%" % round(100 * soc(b, f["input_voltage"], f)),
             self.value_painter("pct", SPEED_X, BIG_Y, scale=VALUE)),
            ("range", col_x(1), BIG_Y, 86, 22,
             lambda f, b: ("%4.0fkm" % f["s_range_km"]
                           if f.get("s_range_km") else "  --"),
             self.value_painter("range", col_x(1), BIG_Y, scale=VALUE)),
            ("fet", SPEED_X, FOOT_Y, 80, 10,
             lambda f, b: "FET %3.0f" % f["temp_fet_filtered"],
             self.value_painter("fet", SPEED_X, FOOT_Y, scale=LABEL,
                                color=lambda f, b, t: t.temp_color(
                                    f["temp_fet_filtered"], b.temp_derate_start))),
            ("volts", col_x(1), FOOT_Y, 86, 10,
             lambda f, b: "%5.1f V" % f["input_voltage"],
             self.value_painter("volts", col_x(1), FOOT_Y, scale=LABEL)),
            ("fault", 0, H - 26, W, 26,
             lambda f, b: ("FAULT %d" % f["fault"]) if f["fault"] else "",
             self._paint_fault),
        )


def render(d, frame, board, theme=None):
    """One-shot full repaint. Kept for callers that do not hold state."""
    Riding(theme).render(d, frame, board, full=True)
