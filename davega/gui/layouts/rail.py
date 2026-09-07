"""Motorsport - edge-lit and angular.

A shift-light rail down the left that climbs with speed and changes colour as
it fills, a tricolour stripe, and blocks that sit at a slant. The rail is the
point: you read it peripherally, without moving your eyes off the road, and
the numeral is there for when you have a moment.

The slants are furniture - drawn once as wedges into a band, because the panel
has no line primitive and a diagonal repainted every frame would cost more
than the whole frame budget.
"""
from .. import bigfont, bands
from ..base import W, H, LABEL
from . import Base
from . import kit

RAIL_X, RAIL_W = 0, 22
RAIL_TOP, RAIL_BOT = 22, H
STRIPE_Y, STRIPE_H = 22, 6                    # the tricolour, under the header

L = RAIL_X + RAIL_W + 12
R = W - 10
SPAN = R - L

SPEED_X, SPEED_Y, SPEED_S = 44, 46, 21
UNIT_X, UNIT_Y = 196, 158

SLANT_Y, SLANT_H = 178, 40                    # the slanted data block
AMP_Y = 190

BATT_Y, BATT_H = 230, 18
BIG_Y, BIG_S = 262, 9
FAULT_Y, FAULT_H = 262, 50


class Layout(Base):
    grid_exceptions = {
        "rail": "shift light, owns the left edge",
        "speed": "the numeral, centred in what the rail leaves",
        "amps": "inside the slanted block",
        "batt": "spans the body", "pct": "bottom block",
        "range": "paired with pct", "fault": "displaces both",
    }
    overlap_exceptions = {("fault", "pct"), ("fault", "range")}
    tweens = {"rail": (5, 4.0)}

    def target(self, key, s, f, b):
        return (RAIL_BOT - RAIL_TOP) * min(1.0, kit.kph(f, b) / 45.0)

    def chrome(self, s, d):
        t = s.t
        d.fill_rectangle(RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP, t.track)
        # The tricolour: the one flash of the marque, and a hard edge for the
        # rail to run out of.
        third = SPAN // 3
        for i, col in enumerate((t.accent, t.ink, t.danger)):
            d.fill_rectangle(L + i * third, STRIPE_Y, third, STRIPE_H, col)

        # The slanted block. A wedge, composed once and pushed as bands - a
        # diagonal costs 2.9 ms a column drawn as rectangles, and nothing at
        # all drawn into a buffer.
        def draw(c):
            c.fill(t.ground)
            c.wedge([L, R, R, L], [SLANT_Y + 10, SLANT_Y,
                                   SLANT_Y + SLANT_H, SLANT_Y + SLANT_H + 10],
                    t.track)
        bands.paint(d, L, SLANT_Y, SPAN, SLANT_H + 12, draw)

        d.set_color(t.dim, t.ground)
        for x, y, txt in ((UNIT_X, UNIT_Y, "KM/H"),
                          (L, BIG_Y - 12, "CHARGE"),
                          (R - 72, BIG_Y - 12, "RANGE KM")):
            d.set_pos(x, y)
            d.print(txt)

    def regions(self, s):
        return (
            ("fault", L, FAULT_Y, SPAN, FAULT_H, kit.fault_text,
             kit.banner(s, L, FAULT_Y, SPAN, FAULT_H, ("pct", "range"))),
            ("rail", RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP,
             lambda f, b: int(s.tw("rail")),
             kit.vrail(s, "rail", RAIL_X, RAIL_TOP, RAIL_BOT, RAIL_W,
                       # A shift light: green through amber to red as it fills.
                       lambda f, b, t: (t.danger if kit.kph(f, b) > 38 else
                                        t.warn if kit.kph(f, b) > 28
                                        else t.accent))),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("amps", L + 8, AMP_Y, SPAN - 16, 12,
             lambda f, b: "%.0fA MOT %.0fA PK %dC"
                          % (f["avg_motor_current"], f["avg_input_current"],
                             round(f["temp_fet_filtered"])),
             # Cleared to the slant's own colour, not to the ground: a shorter
             # value pads with blanks, and blanks the ground colour would cut a
             # notch out of the furniture underneath.
             s.value_painter("amps", L + 8, AMP_Y, scale=LABEL,
                             bg=s.t.track)),
            ("batt", L, BATT_Y, SPAN, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, L, BATT_Y, SPAN, BATT_H, segs=10, gap=3)),
            ("pct", L, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", L, BIG_Y, BIG_S)),
            ("range", R - 72, BIG_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", R - 72, BIG_Y, BIG_S)),
        )
