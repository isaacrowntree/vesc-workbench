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

SPLIT_Y0, SPLIT_Y1 = 96, 132                  # the diagonal across the top
SPEED_X, SPEED_Y, SPEED_S = 20, 32, 12
UNIT_X, UNIT_Y = 130, 84

CELLS_Y, CELL_R = 186, 34                     # three hexagons
CELL_X = (52, 120, 188)

BAR_L, BAR_R = 16, 224
BAR_Y, BAR_H, BAR_RISE = 250, 22, 10          # the trough slants up to the right
BIG_Y, BIG_S = 282, 7
FAULT_Y, FAULT_H = 276, 42    # past the numerals, or their last row survives


def _hex(c, cx, cy, r, colour):
    xs, ys = [], []
    for i in range(6):
        sin, cos = bands.sincos(i * 60 - 30)
        xs.append(cx + int(r * sin))
        ys.append(cy - int(r * cos))
    c.wedge(xs, ys, colour)


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
                _hex(c, cx, CELLS_Y, CELL_R, t.track)
        bands.paint(d, 0, CELLS_Y - CELL_R, W, 2 * CELL_R + 2, cells)

        d.set_color(t.dim, t.ground)
        for x, y, txt in ((UNIT_X, UNIT_Y, "KM/H"),
                          (CELL_X[0] - 12, CELLS_Y + 12, "MOT"),
                          (CELL_X[1] - 12, CELLS_Y + 12, "BAT"),
                          (CELL_X[2] - 12, CELLS_Y + 12, "FET")):
            d.set_pos(x, y)
            d.print(txt)

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
            x = CELL_X[i] - 22
            return (name, x, CELLS_Y - 22, 44, 20, value,
                    # Inside a hexagon, so it clears to the hexagon's fill.
                    s.value_painter(name, x, CELLS_Y - 18, scale=LABEL,
                                    bg=s.t.track))
        return (
            ("fault", 16, FAULT_Y, W - 32, FAULT_H, kit.fault_text,
             kit.banner(s, 16, FAULT_Y, W - 32, FAULT_H, ("pct", "range"))),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S,
                     bg=s.t.track)),
            cell("mot", 0, lambda f, b: "%.0fA" % f["avg_motor_current"]),
            cell("pack", 1, lambda f, b: "%.0fA" % f["avg_input_current"]),
            cell("fet", 2, lambda f, b: "%d C" % round(f["temp_fet_filtered"])),
            ("batt", BAR_L, BAR_Y - BAR_RISE, BAR_R - BAR_L,
             BAR_H + BAR_RISE + 1,
             lambda f, b: BAR_L + int((BAR_R - BAR_L)
                                      * kit.soc(b, f["input_voltage"], f)),
             self._slant_bar(s)),
            ("pct", 16, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", 16, BIG_Y, BIG_S)),
            ("range", W - 16 - 56, BIG_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", W - 16 - 56, BIG_Y, BIG_S)),
        )
