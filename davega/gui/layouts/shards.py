"""Toro - everything is a shard.

Hexagonal cells on a diagonal split, acid green on carbon. Aggressive, angular
and unapologetically loud: the only layout with no horizontal edges, which on
a panel whose sole primitive is an axis-aligned rectangle is a deliberately
awkward thing to ask for.

It works because the angles are all furniture. The split, the hexagons and the
slanted battery trough are composed into bands once, and the trough is
repainted whole - 6.8k pixels in one transfer, nine milliseconds - rather than
as a delta, because a delta wedge and a full wedge round their slanted ends
differently and the two paths then disagree by a few pixels at the seam.
"""
from .. import bigfont, bands
from ..base import W, LABEL
from . import Base
from . import kit

SPLIT_Y0, SPLIT_Y1 = 100, 140                 # the diagonal across the top
SPEED_X, SPEED_Y, SPEED_S = 16, 32, 15        # 120 x 75
UNIT_X, UNIT_Y = 150, 90

#: The cell values are numerals, not captions - the whole point of a hexagon
#: is that it is big enough to hold something. Scale 5 is 40x25, and a
#: hexagon of radius 34 is only 43 px wide at the top of a 30 px box: a
#: numeral that clears to the cell's fill has to stay inside the cell, or it
#: paints the fill colour out over the ground beside it.
CELL_S = 5

CELLS_Y, CELL_R = 190, 34                     # three hexagons
#: 78 apart for a 68-wide cell: they are separate objects, and hexagons that
#: touch read as one band with notches in it.
CELL_X = (42, 120, 198)

BAR_L, BAR_R = 16, 224
BAR_Y, BAR_H, BAR_RISE = 244, 18, 8           # the trough slants up to the right
BIG_Y, BIG_S = 278, 8         # 278 + 40 = 318, the last usable row
LABEL_Y = 266
FAULT_Y, FAULT_H = 274, 46    # past the numerals, or their last row survives


def _hex(c, cx, cy, r, fill, stroke=None, weight=2):
    """A hexagon, outlined then filled.

    The panel has no polygon primitive and no stroke, so the outline is a
    hexagon two pixels larger with the fill laid inside it. Cheap, and it is
    the outline that makes these read as cells rather than as dark patches -
    which is the whole difference between the drawing and the dashboard.
    """
    def poly(rr):
        xs, ys = [], []
        for i in range(6):
            sin, cos = bands.sincos(i * 60 - 30)
            xs.append(cx + int(rr * sin))
            ys.append(cy - int(rr * cos))
        return xs, ys

    if stroke is not None:
        xs, ys = poly(r)
        c.wedge(xs, ys, stroke)
        r -= weight
    xs, ys = poly(r)
    c.wedge(xs, ys, fill)


class Layout(Base):
    grid_exceptions = {
        "speed": "sits above the split", "batt": "a slanted trough",
        "mot": "in a hexagon", "pack": "in a hexagon", "fet": "in a hexagon",
        "pct": "under the trough", "range": "paired with pct",
        "fault": "displaces both",
    }
    overlap_exceptions = {("fault", "pct"), ("fault", "range")}

    def chrome(self, s, d):
        t = s.t
        def top(c):
            c.fill(t.ground)
            c.wedge([0, W, W, 0], [26, 26, SPLIT_Y0, SPLIT_Y1], t.track)
            c.wedge([0, W, W, 0],
                    [SPLIT_Y1, SPLIT_Y0, SPLIT_Y0 + 8, SPLIT_Y1 + 8], t.accent)
        bands.paint(d, 0, 26, W, SPLIT_Y1 + 10 - 26, top)

        def cells(c):
            c.fill(t.ground)
            for cx in CELL_X:
                _hex(c, cx, CELLS_Y, CELL_R, t.track, t.dim)
        bands.paint(d, 0, CELLS_Y - CELL_R, W, 2 * CELL_R + 2, cells)

        # The unit in the accent, on the split, because on this layout the
        # accent is the point and there is nowhere quiet to hide it.
        d.set_color(t.accent, t.track)
        d.set_pos(UNIT_X, UNIT_Y)
        d.print("KM/H")
        # Cell captions sit under their numerals, inside the hexagon.
        d.set_color(t.accent, t.track)
        for cx, txt in zip(CELL_X, ("MOT", "BAT", "FET")):
            d.set_pos(cx - 12, CELLS_Y + 14)
            d.print(txt)
        d.set_color(t.dim, t.ground)
        d.set_pos(16, LABEL_Y)
        d.print("CHARGE")
        d.set_pos(W - 16 - 64, LABEL_Y)
        d.print("RANGE KM")

    def _slant_bar(self, s):
        """The battery, following the trough's angle."""
        def paint(d, f, b, v):
            t = s.t
            col = t.soc_color(kit.soc(b, f["input_voltage"], f))
            span = float(BAR_R - BAR_L)

            def rise(x):
                return BAR_Y - int(BAR_RISE * (x - BAR_L) / span)

            def draw(c):
                c.fill(t.ground)
                c.wedge([BAR_L, BAR_R, BAR_R, BAR_L],
                        [rise(BAR_L), rise(BAR_R), rise(BAR_R) + BAR_H,
                         rise(BAR_L) + BAR_H], t.track)
                if v > BAR_L:
                    c.wedge([BAR_L, v, v, BAR_L],
                            [rise(BAR_L), rise(v), rise(v) + BAR_H,
                             rise(BAR_L) + BAR_H], col)
            bands.paint(d, 0, BAR_Y - BAR_RISE, W, BAR_H + BAR_RISE + 1, draw)
        return paint

    def regions(self, s):
        def cell(name, i, value):
            # Two numerals, centred in the hexagon, drawn with bigfont rather
            # than the 8x8 font - a cell this size holding caption-sized text
            # is the shape without the substance.
            w = bigfont.width("00", CELL_S)
            x = CELL_X[i] - w // 2
            y = CELLS_Y - bigfont.char_h(CELL_S) // 2 - 4
            return (name, x, y, w, bigfont.char_h(CELL_S), value,
                    # Inside a hexagon, so it clears to the hexagon's fill.
                    kit.big(s, name, x, y, CELL_S, bg=s.t.track))
        return (
            ("fault", 16, FAULT_Y, W - 32, FAULT_H, kit.fault_text,
             kit.banner(s, 16, FAULT_Y, W - 32, FAULT_H, ("pct", "range"))),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S,
                     bg=s.t.track)),
            cell("mot", 0, lambda f, b: kit.fit(abs(f["avg_motor_current"]))),
            cell("pack", 1, lambda f, b: kit.fit(abs(f["avg_input_current"]))),
            cell("fet", 2, lambda f, b: kit.fit(f["temp_fet_filtered"])),
            ("batt", BAR_L, BAR_Y - BAR_RISE, BAR_R - BAR_L,
             BAR_H + BAR_RISE + 1,
             lambda f, b: BAR_L + int((BAR_R - BAR_L)
                                      * kit.soc(b, f["input_voltage"], f)),
             self._slant_bar(s)),
            ("pct", 16, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", 16, BIG_Y, BIG_S)),
            ("range", W - 16 - 64, BIG_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", W - 16 - 64, BIG_Y, BIG_S)),
        )
