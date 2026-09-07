"""Papaya - precision over drama.

Hairline arcs, a single saturated accent, and more black than anything else.
It reads like a telemetry readout because that is what it is: three thin arcs
across the top, each one a different quantity, and numbers set beneath them
with no boxes, no fills and no ornament.

The arcs are hairlines - two pixels - which on this panel is the cheapest
curve there is, and the reason this layout can afford three of them where the
dial affords one.
"""
from .. import bigfont, bands
from ..base import W, LABEL
from . import Base
from . import kit

CX, CY = 120, 142                             # the arcs share a centre
RADII = (108, 96, 84)                         # speed, charge, power
#: kept off the horizontal so the arcs - and the band that repaints them -
#: stop above the numbers underneath
A0, A1 = -96.0, 96.0
KPH_MAX = 45.0
ARC_TOP = 26
#: the box the three arcs live in, and the one band that paints them
ARC_X0, ARC_W = CX - RADII[0] - 2, 2 * (RADII[0] + 2)
ARC_H = (CY + int(RADII[0] * 0.11) + 4) - ARC_TOP

SPEED_X, SPEED_Y, SPEED_S = 68, 100, 13
UNIT_Y = 170

ROW_Y, ROW_S = 196, 8
FOOT_Y = 244
BIG_Y = 262
#: reaches up over the footnote. A region that blanks for the banner must be
#: a region the banner actually covers, or it just stops being repainted and
#: its last value stays on the glass.
FAULT_Y, FAULT_H = 244, 60


def _sweep(c, colour, r, a0, a1, thickness=2):
    """Spokes closer together than a degree.

    At radius 108 a whole degree is 1.9 px and a radial spoke does not span
    it, so an arc stepped by one degree comes out dotted.
    """
    dd = min(1.0, 57.3 / r)
    deg = a0
    while deg <= a1:
        sin, cos = bands.sincos(deg)
        c.spoke(CX, CY, r - thickness, r, sin, cos, colour, 2)
        deg += dd


def _a(frac):
    return A0 + (A1 - A0) * max(0.0, min(1.0, frac))


class Layout(Base):
    grid_exceptions = {
        "arcs": "three concentric arcs have no column",
        "speed": "centred under the arcs",
        "pct": "left of the pair", "range": "right of the pair",
        "foot": "footnotes", "fault": "displaces the footnotes",
    }
    overlap_exceptions = {("arcs", "speed"), ("fault", "foot")}
    tweens = {"speed": (5, 6.0)}

    def target(self, key, s, f, b):
        return _a(kit.kph(f, b) / KPH_MAX)

    def chrome(self, s, d):
        t = s.t
        d.set_color(t.dim, t.ground)
        for x, y, txt in ((104, UNIT_Y, "KM/H"), (16, ROW_Y - 12, "CHARGE"),
                          (W - 16 - 72, ROW_Y - 12, "RANGE KM")):
            d.set_pos(x, y)
            d.print(txt)

    def _arcs(self, s):
        """All three arcs, in one band.

        They are concentric, so any band big enough for one of them lies
        across the other two. Painted separately each one scrubs its
        neighbours and has to put them back; painted together there is nothing
        to put back, it is one transfer instead of three, and the three can
        never disagree about what is underneath them.
        """
        def paint(d, f, b, v):
            t = s.t
            speed, soc, power = v
            lit = (t.accent, t.soc_color(soc), t.warn)
            vals = (speed, _a(soc), _a(power))

            def draw(c):
                c.fill(t.ground)
                for r, col, upto in zip(RADII, lit, vals):
                    _sweep(c, t.dim, r, A0, A1)
                    _sweep(c, col, r, A0, upto)
            bands.paint(d, ARC_X0, ARC_TOP, ARC_W, ARC_H, draw)
            s._force.add("speed")
        return paint

    def regions(self, s):
        return (
            ("fault", 16, FAULT_Y, W - 32, FAULT_H, kit.fault_text,
             kit.banner(s, 16, FAULT_Y, W - 32, FAULT_H, ("foot",))),
            ("arcs", ARC_X0, ARC_TOP, ARC_W, ARC_H,
             lambda f, b: (s.tw("speed"),
                           kit.soc(b, f["input_voltage"], f),
                           min(1.0, abs(f["avg_motor_current"])
                               / max(1.0, b.motor_current))),
             self._arcs(s)),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("pct", 16, ROW_Y, bigfont.width("100", ROW_S),
             bigfont.char_h(ROW_S), kit.charge_text,
             kit.big(s, "pct", 16, ROW_Y, ROW_S)),
            ("range", W - 16 - 64, ROW_Y, bigfont.width("99", ROW_S),
             bigfont.char_h(ROW_S), kit.range_text,
             kit.big(s, "range", W - 16 - 64, ROW_Y, ROW_S)),
            ("foot", 16, FOOT_Y, W - 32, 12,
             lambda f, b: ("" if f["fault"] else
                           "%.1fV %.0fA %.0fA %dC"
                           % (f["input_voltage"], f["avg_motor_current"],
                              f["avg_input_current"],
                              round(f["temp_fet_filtered"]))),
             kit.quiet(s.value_painter("foot", 16, FOOT_Y, scale=LABEL))),
        )
