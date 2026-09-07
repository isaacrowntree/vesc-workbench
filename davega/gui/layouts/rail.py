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

#: Three slabs, each a label on the left and a value on the right. The
#: original drawing had them as separate blocks and reading them as a list is
#: the point - one run-on line of "18A MOT 9A PK 42C" is a different, worse
#: instrument.
SLAB_Y, SLAB_H, SLAB_GAP = 176, 22, 3
SLAB_SLANT = 6                                # each slab leans, none are square

BATT_Y, BATT_H = 258, 12
BIG_Y, BIG_S = 284, 7
FAULT_Y, FAULT_H = 280, 40

#: The shift light is blocks, not a bar: a solid column tells you how fast you
#: are going, and a column of discrete lights tells you how close you are to
#: the top of the range without being read at all.
RAIL_SEGS = 14
RAIL_GAP = 3


class Layout(Base):
    grid_exceptions = {
        "rail": "shift light, owns the left edge",
        "speed": "the numeral, centred in what the rail leaves",
        "motor": "on its slab", "pack": "on its slab", "fet": "on its slab",
        "batt": "spans the body", "pct": "bottom block",
        "range": "paired with pct", "fault": "displaces both",
    }
    overlap_exceptions = {("fault", "pct"), ("fault", "range")}

    def chrome(self, s, d):
        t = s.t
        d.fill_rectangle(RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP, t.track)
        # The tricolour: the one flash of the marque, and a hard edge for the
        # rail to run out of.
        third = SPAN // 3
        for i, col in enumerate((t.accent, t.ink, t.danger)):
            d.fill_rectangle(L + i * third, STRIPE_Y, third, STRIPE_H, col)

        # Three slanted slabs, composed once and pushed as bands. A diagonal
        # costs 2.9 ms a column drawn as rectangles and nothing at all drawn
        # into a buffer.
        def draw(c):
            c.fill(t.ground)
            for i in range(3):
                y = SLAB_Y + i * (SLAB_H + SLAB_GAP)
                c.wedge([L, R, R, L],
                        [y + SLAB_SLANT, y, y + SLAB_H,
                         y + SLAB_H + SLAB_SLANT], t.track)
        bands.paint(d, L, SLAB_Y, SPAN,
                    3 * (SLAB_H + SLAB_GAP) + SLAB_SLANT, draw)

        d.set_color(t.dim, t.ground)
        d.set_pos(UNIT_X, UNIT_Y)
        d.print("KM/H")
        # The slab captions, on the slab.
        d.set_color(t.dim, t.track)
        for i, txt in enumerate(("MOTOR", "PACK", "FET")):
            d.set_pos(L + 10, SLAB_Y + i * (SLAB_H + SLAB_GAP) + 12)
            d.print(txt)
        d.set_color(t.dim, t.ground)
        d.set_pos(L, BIG_Y - 12)
        d.print("CHARGE")
        d.set_pos(R - 64, BIG_Y - 12)
        d.print("RANGE KM")

    def _shift_light(self, s):
        """Blocks, lighting from the bottom, changing colour near the top."""
        def paint(d, f, b, v):
            t = s.t
            span = RAIL_BOT - RAIL_TOP
            seg = (span - RAIL_GAP * (RAIL_SEGS - 1)) // RAIL_SEGS
            for i in range(RAIL_SEGS):
                y = RAIL_BOT - (i + 1) * seg - i * RAIL_GAP
                if i >= v:
                    col = t.track
                elif i >= RAIL_SEGS - 3:
                    col = t.danger
                elif i >= RAIL_SEGS - 6:
                    col = t.warn
                else:
                    col = t.accent
                d.fill_rectangle(RAIL_X, y, RAIL_W, seg, col)
        return paint

    def _slab(self, s, key, i, value):
        """A value right-aligned on its slab, with the caption drawn as
        chrome on the left."""
        y = SLAB_Y + i * (SLAB_H + SLAB_GAP)
        w = 7 * 8                       # four characters and a little air
        x = R - 10 - w
        return (key, x, y + 8, w, 10, value,
                # Cleared to the slab's own colour: a shorter value pads with
                # blanks, and blanks in the ground colour would cut a notch
                # out of the furniture underneath.
                s.value_painter(key, x, y + 8, scale=LABEL, bg=s.t.track))

    def regions(self, s):
        return (
            ("fault", L, FAULT_Y, SPAN, FAULT_H, kit.fault_text,
             kit.banner(s, L, FAULT_Y, SPAN, FAULT_H, ("pct", "range"))),
            ("rail", RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP,
             lambda f, b: min(RAIL_SEGS,
                              int(RAIL_SEGS * kit.kph(f, b) / 45.0 + 0.5)),
             self._shift_light(s)),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            self._slab(s, "motor", 0,
                       lambda f, b: "%sA" % kit.fit(abs(f["avg_motor_current"]),
                                                    3)),
            self._slab(s, "pack", 1,
                       lambda f, b: "%sA" % kit.fit(abs(f["avg_input_current"]),
                                                    3)),
            self._slab(s, "fet", 2,
                       lambda f, b: "%sC" % kit.fit(f["temp_fet_filtered"], 3)),
            ("batt", L, BATT_Y, SPAN, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, L, BATT_Y, SPAN, BATT_H, segs=10, gap=3)),
            ("pct", L, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", L, BIG_Y, BIG_S)),
            ("range", R - 64, BIG_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", R - 64, BIG_Y, BIG_S)),
        )
