"""Hybrid - calm, and about efficiency.

A centre-zero eco meter you read without focusing, soft blues, and range
promoted above speed. The layout for a long day on grass: the question it
answers first is not how fast you are going but how far you can keep going,
and it puts the two figures that decide that at the top.

The eco arc is a hairline over the meter, marking where the efficient band
ends - the one place in the ten where a curve is a legend rather than a value.
"""
from .. import bigfont, bands
from ..base import W, LABEL
from . import Base
from . import kit

L, R = 16, W - 16
SPAN = R - L

RANGE_X, RANGE_Y, RANGE_S = 16, 40, 13        # range is the hero here
PCT_S = 8                                     # charge, deliberately smaller
RANGE_LABEL_Y = 28
PCT_X = W - 16 - 96

ECO_Y, ECO_H = 138, 30                        # centre-zero, with an eco band
ECO_LABEL_Y = 126
ARC_CY, ARC_R = 172, 96

SPEED_X, SPEED_Y, SPEED_S = 16, 200, 11
SPEED_LABEL_Y = 188
WKM_X = W - 16 - 108

BATT_Y, BATT_H = 258, 16
FOOT_Y = 286
#: the bottom block, below the battery. A banner that covers the battery is
#: repainted over by it on a full repaint and not on a differential one - the
#: battery redraws unconditionally, the banner does not.
FAULT_Y, FAULT_H = 280, 40


class Layout(Base):
    grid_exceptions = {
        "range": "the hero on this layout", "pct": "paired with range",
        "eco": "centre-zero meter spans the width",
        "speed": "demoted, deliberately", "wkm": "paired with speed",
        "batt": "spans the width", "foot": "footnotes",
        "fault": "displaces the footnotes",
    }
    overlap_exceptions = {("fault", "foot")}
    tweens = {"eco": (4, 3.0)}

    def target(self, key, s, f, b):
        return (SPAN / 2.0) * max(-1.0, min(1.0, f["avg_motor_current"]
                                            / max(1.0, b.motor_current)))

    def chrome(self, s, d):
        t = s.t
        d.fill_rectangle(L, ECO_Y, SPAN, ECO_H, t.track)
        # The eco band: a hairline arc over the meter saying where "gentle"
        # stops. A legend, not a reading, so it is furniture.
        def draw(c):
            c.fill(t.ground)
            deg = -34.0
            while deg <= 34.0:
                sin, cos = bands.sincos(deg)
                c.spoke(W // 2, ARC_CY, ARC_R - 2, ARC_R, sin, cos, t.accent, 1)
                deg += 1.0
        bands.paint(d, 0, ECO_Y + ECO_H + 2, W, 26, draw)

        d.set_color(t.dim, t.ground)
        for x, y, txt in ((RANGE_X, RANGE_LABEL_Y, "RANGE KM"),
                          (PCT_X, RANGE_LABEL_Y, "CHARGE"),
                          (L, ECO_LABEL_Y, "REGEN"), (R - 40, ECO_LABEL_Y, "DRIVE"),
                          (SPEED_X, SPEED_LABEL_Y, "KM/H"),
                          (WKM_X, SPEED_LABEL_Y, "WH / KM")):
            d.set_pos(x, y)
            d.print(txt)

    def regions(self, s):
        return (
            ("fault", L, FAULT_Y, SPAN, FAULT_H, kit.fault_text,
             kit.banner(s, L, FAULT_Y, SPAN, FAULT_H, ("foot",))),
            ("range", RANGE_X, RANGE_Y, bigfont.width("99", RANGE_S),
             bigfont.char_h(RANGE_S), kit.range_text,
             kit.big(s, "range", RANGE_X, RANGE_Y, RANGE_S)),
            ("pct", PCT_X, RANGE_Y + 16, bigfont.width("100", PCT_S),
             bigfont.char_h(PCT_S), kit.charge_text,
             kit.big(s, "pct", PCT_X, RANGE_Y + 16, PCT_S)),
            ("eco", L, ECO_Y - 4, SPAN, ECO_H + 8,
             lambda f, b: int(s.tw("eco")),
             kit.centre_meter(s, "eco", L, SPAN, ECO_Y, ECO_H,
                              mid=L + SPAN // 2)),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("wkm", WKM_X, SPEED_Y, bigfont.width("99", SPEED_S),
             bigfont.char_h(SPEED_S),
             lambda f, b: ("%d" % round(f["s_wh_per_km"])
                           if f.get("s_wh_per_km") else "--"),
             kit.big(s, "wkm", WKM_X, SPEED_Y, SPEED_S)),
            ("batt", L, BATT_Y, SPAN, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, L, BATT_Y, SPAN, BATT_H, segs=14, gap=3)),
            ("foot", L, FOOT_Y, SPAN, 12,
             lambda f, b: ("" if f["fault"] else
                           "%.1fV  %.0fA  %dC / %dC"
                           % (f["input_voltage"], f["avg_input_current"],
                              round(f["temp_fet_filtered"]),
                              round(f["temp_motor_filtered"]))),
             kit.quiet(s.value_painter("foot", L, FOOT_Y, scale=LABEL))),
        )
