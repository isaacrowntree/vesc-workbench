"""Papaya - precision over drama.

One hairline arc, a single saturated accent, and more black than anything
else. Under it a list: label on the left, value on the right, and a hairline
rule beneath each row that is itself the reading. It looks like a telemetry
printout because that is what it is.

The rules are the whole idea. They are one pixel tall and they carry three of
the four numbers on the screen, which is why this layout can be almost empty
and still tell you everything.
"""
from .. import bigfont, bands
from ..base import W, LABEL
from . import Base
from . import kit

CX, CY = 120, 128                             # the arc's centre
ARC_R = 96
#: Kept off the horizontal so the arc - and the band that repaints it - stops
#: above the list underneath.
A0, A1 = -96.0, 96.0
KPH_MAX = 45.0
ARC_TOP = 26
ARC_X0, ARC_W = CX - ARC_R - 3, 2 * (ARC_R + 3)
ARC_H = (CY + 6) - ARC_TOP

SPEED_S = 13                                  # 104 x 65, inside the arc
SPEED_X = CX - bigfont.width("00", SPEED_S) // 2
SPEED_Y = CY - bigfont.char_h(SPEED_S) - 4
#: Below the arc's band and below the numeral's box: the band fills with the
#: ground colour before it redraws, so anything inside it lasts one frame.
UNIT_Y = 136

#: The list. Each row is a label, a right-aligned value, and a rule.
L, R = 16, W - 16
ROW_Y, ROW_H = 152, 34
RULE_DY = 20                                  # rule, below the row's baseline
RULE_H = 2

FOOT_Y = 292
FAULT_Y, FAULT_H = 276, 44


def _sweep(c, colour, r, a0, a1, thickness=2):
    """Spokes closer together than a degree.

    At radius 96 a whole degree is 1.7 px and a radial spoke does not span it,
    so an arc stepped by one degree comes out dotted.
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
        "arc": "an arc has no column", "speed": "centred in the arc",
        "charge": "a list row", "motor": "a list row", "pack": "a list row",
        "charge_bar": "the rule under its row, full width",
        "motor_bar": "the rule under its row, full width",
        "pack_bar": "the rule under its row, full width",
        "foot": "footnotes", "fault": "displaces the list",
    }
    overlap_exceptions = {("arc", "speed"), ("fault", "foot")}
    tweens = {"arc": (5, 6.0)}

    def target(self, key, s, f, b):
        return _a(kit.kph(f, b) / KPH_MAX)

    def chrome(self, s, d):
        t = s.t
        d.set_color(t.dim, t.ground)
        d.set_pos(CX - 16, UNIT_Y)
        d.print("KM/H")
        for i, label in enumerate(("CHARGE", "MOTOR A", "PACK A")):
            d.set_pos(L, ROW_Y + i * ROW_H)
            d.print(label)

    def _arc(self, s):
        """One arc, in one band, repainted whole."""
        def paint(d, f, b, v):
            t = s.t

            def draw(c):
                c.fill(t.ground)
                _sweep(c, t.dim, ARC_R, A0, A1)
                _sweep(c, t.accent, ARC_R, A0, v)
            bands.paint(d, ARC_X0, ARC_TOP, ARC_W, ARC_H, draw)
            s._force.add("speed")
        return paint

    def _row(self, s, key, i, text_of, frac_of, colour=None):
        """A row: a value right-aligned, and a rule under it that is itself
        the reading.

        Two regions rather than one, because the label on the left is chrome
        and a region's box has to be what the region actually paints - a box
        that swallowed the label would be claiming to repaint something it
        never touches.
        """
        y = ROW_Y + i * ROW_H
        rule_y = y + RULE_DY
        vx = R - 8 * 6                          # six characters of headroom

        def bar(d, f, b, v):
            t = s.t
            col = colour(f, b, t) if colour else t.accent
            d.fill_rectangle(L, rule_y, v, RULE_H, col)
            d.fill_rectangle(L + v, rule_y, (R - L) - v, RULE_H, t.track)

        return (
            (key, vx, y, R - vx, 10, text_of,
             s.value_painter(key, vx, y, scale=LABEL, color=colour)),
            (key + "_bar", L, rule_y, R - L, RULE_H,
             lambda f, b: int((R - L) * frac_of(f, b)), bar),
        )

    def regions(self, s):
        rows = ()
        rows += self._row(s, "charge", 0,
                          lambda f, b: "%s%%" % kit.charge_text(f, b),
                          lambda f, b: kit.soc(b, f["input_voltage"], f),
                          lambda f, b, t: t.soc_color(
                              kit.soc(b, f["input_voltage"], f)))
        rows += self._row(s, "motor", 1,
                          lambda f, b: "%sA" % kit.fit(
                              abs(f["avg_motor_current"]), 3),
                          lambda f, b: min(1.0, abs(f["avg_motor_current"])
                                           / max(1.0, b.motor_current)))
        rows += self._row(s, "pack", 2,
                          lambda f, b: "%sA" % kit.fit(
                              abs(f["avg_input_current"]), 3),
                          lambda f, b: min(1.0, abs(f["avg_input_current"])
                                           / max(1.0, b.battery_current)))
        return (
            ("fault", L, FAULT_Y, R - L, FAULT_H, kit.fault_text,
             kit.banner(s, L, FAULT_Y, R - L, FAULT_H, ("foot",))),
            ("arc", ARC_X0, ARC_TOP, ARC_W, ARC_H,
             lambda f, b: s.tw("arc"), self._arc(s)),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("foot", L, FOOT_Y, R - L, 12,
             lambda f, b: ("" if f["fault"] else
                           "%.1fV   %sKM   %sC"
                           % (f["input_voltage"], kit.range_text(f, b),
                              kit.fit(f["temp_fet_filtered"], 3))),
             kit.quiet(s.value_painter("foot", L, FOOT_Y, scale=LABEL))),
        ) + rows
