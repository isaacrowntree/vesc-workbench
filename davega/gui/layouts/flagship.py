"""Nazare - the flagship.

The best idea from each of the others and nothing else. Speed takes nearly
half the panel, a speed rail runs the full height of the left edge, power flows
from a hard centre zero, and charge and range share the bottom block in
numerals big enough to read without looking.

Everything is pulled in tight. Negative space on a 2.8 inch panel at 40 km/h
is wasted screen.
"""
from .. import bigfont
from ..base import W, LABEL
from . import Base
from . import kit

RAIL_X, RAIL_W = 3, 14
RAIL_TOP, RAIL_BOT = 26, 316

#: 176 x 110 for two digits, centred in the body span the rail leaves
SPEED_X, SPEED_Y, SPEED_S = 40, 30, 22
#: right-aligned on its own line under the numeral - the flow block below
#: moves down to give it that line rather than the unit borrowing one
UNIT_X, UNIT_Y = 200, 144

FLOW_Y, FLOW_H = 170, 26
AMP_Y = 200
BATT_Y, BATT_H = 218, 28
BIG_Y, BIG_S = 266, 10                       # charge and range, 40 x 50
BODY_L = 24
#: the rail already holds the left edge, so the body only needs a hairline of
#: margin on the right - not the symmetric gutter it was using
BODY_R = W - 8
RANGE_X = BODY_R - 80                        # two digits, right-aligned
FAULT_Y, FAULT_H = 266, 50
LABEL_DY = 12


class Layout(Base):
    grid_exceptions = {
        "rail": "peripheral gauge, owns the left edge",
        "speed": "the hero numeral, centred on its own",
        "flow": "centre-zero meter spans the width",
        "amps": "reads against the meter",
        "batt": "segmented bar spans the width",
        "pct": "clear of the rail", "range": "paired with pct",
        "fault": "full-bleed banner",
    }
    overlap_exceptions = {("fault", "pct"), ("fault", "range")}
    tweens = {"rail": (5, 4.0), "flow": (4, 3.0)}

    def target(self, key, s, f, b):
        if key == "rail":
            return (RAIL_BOT - RAIL_TOP) * min(1.0, kit.kph(f, b) / 45.0)
        half = (BODY_R - BODY_L) / 2.0
        return half * max(-1.0, min(1.0, f["avg_motor_current"]
                                    / max(1.0, b.motor_current)))

    def chrome(self, s, d):
        t = s.t
        d.fill_rectangle(RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP, t.track)
        # The meter's track is furniture, painted once. Leaving it to the
        # delta painter meant a full repaint never drew it at all, and the
        # differential path did - so the two disagreed.
        d.fill_rectangle(BODY_L, FLOW_Y, BODY_R - BODY_L, FLOW_H, t.track)
        d.set_color(t.dim, t.ground)
        for x, y, s_ in ((UNIT_X, UNIT_Y, "KM/H"),
                         (BODY_L, FLOW_Y - 14, "REGEN"),
                         (BODY_R - 40, FLOW_Y - 14, "DRIVE"),
                         (BODY_L, BIG_Y - LABEL_DY, "CHARGE"),
                         (RANGE_X, BIG_Y - LABEL_DY, "RANGE KM")):
            d.set_pos(x, y)
            d.print(s_)

    def regions(self, s):
        span = BODY_R - BODY_L
        return (
            ("fault", BODY_L, FAULT_Y, span, FAULT_H, kit.fault_text,
             kit.banner(s, BODY_L, FAULT_Y, span, FAULT_H, ("pct", "range"))),
            ("rail", RAIL_X, RAIL_TOP, RAIL_W, RAIL_BOT - RAIL_TOP,
             lambda f, b: int(s.tw("rail")),
             kit.vrail(s, "rail", RAIL_X, RAIL_TOP, RAIL_BOT, RAIL_W)),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("flow", BODY_L, FLOW_Y - 4, span, FLOW_H + 8,
             lambda f, b: int(s.tw("flow")),
             # Zero is the centre of the *body*, not of the panel: the rail
             # takes the left edge, so the two are eight pixels apart and a
             # meter centred on the panel paints outside its own region.
             kit.centre_meter(s, "flow", BODY_L, span, FLOW_Y, FLOW_H,
                              mid=BODY_L + span // 2)),
            ("amps", BODY_L, AMP_Y, span, 12,
             lambda f, b: "%.0fA MOTOR   %.0fA PACK" % (f["avg_motor_current"],
                                                        f["avg_input_current"]),
             s.value_painter("amps", BODY_L, AMP_Y, scale=LABEL)),
            ("batt", BODY_L, BATT_Y, span, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, BODY_L, BATT_Y, span, BATT_H)),
            ("pct", BODY_L, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", BODY_L, BIG_Y, BIG_S)),
            ("range", RANGE_X, BIG_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", RANGE_X, BIG_Y, BIG_S)),
        )
