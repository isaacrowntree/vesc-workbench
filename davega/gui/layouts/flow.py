"""Nevera - built for electrons.

Power flow gets the top half: regen left, drive right, from a hard zero. The
only layout that treats current as more important than speed, because on an
electric board current is the thing you actually control and speed is what
happens next.

Dense by design. Every number a rider might want mid-corner is on this screen
at once, and the meter is readable in peripheral vision so the numbers do not
have to be.
"""
from .. import bigfont
from ..base import W, LABEL
from . import Base
from . import kit

L, R = 16, W - 16
SPAN = R - L

FLOW_Y, FLOW_H = 44, 38                       # the hero: power, not speed
FLOW_LABEL_Y = 30
AMP_X, AMP_Y, AMP_S = 16, 96, 11              # motor amps, large
PACK_X = W - 16 - 88

SPEED_X, SPEED_Y, SPEED_S = 16, 170, 11
PCT_S = 9
SPEED_LABEL_Y = 158
PCT_X, PCT_Y = W - 16 - 108, 174

BATT_Y, BATT_H = 244, 22
FOOT_Y = 276
FAULT_Y, FAULT_H = 270, 46


class Layout(Base):
    grid_exceptions = {
        "flow": "the hero, spans the width",
        "amps": "paired against the meter", "pack": "paired with amps",
        "speed": "secondary here, by design", "pct": "paired with speed",
        "batt": "segmented bar spans the width",
        "foot": "footnotes under the bar", "fault": "displaces the footnotes",
    }
    overlap_exceptions = {("fault", "foot")}
    tweens = {"flow": (4, 3.0)}

    def target(self, key, s, f, b):
        return (SPAN / 2.0) * max(-1.0, min(1.0, f["avg_motor_current"]
                                            / max(1.0, b.motor_current)))

    def chrome(self, s, d):
        t = s.t
        d.fill_rectangle(L, FLOW_Y, SPAN, FLOW_H, t.track)
        d.set_color(t.dim, t.ground)
        for x, y, txt in ((L, FLOW_LABEL_Y, "REGEN"),
                          (R - 40, FLOW_LABEL_Y, "DRIVE"),
                          (AMP_X, 88, "MOTOR A"), (PACK_X, 88, "PACK A"),
                          (SPEED_X, SPEED_LABEL_Y, "KM/H"),
                          (PCT_X, SPEED_LABEL_Y, "CHARGE")):
            d.set_pos(x, y)
            d.print(txt)

    def regions(self, s):
        return (
            ("fault", L, FAULT_Y, SPAN, FAULT_H, kit.fault_text,
             kit.banner(s, L, FAULT_Y, SPAN, FAULT_H, ("foot",))),
            ("flow", L, FLOW_Y - 4, SPAN, FLOW_H + 8,
             lambda f, b: int(s.tw("flow")),
             kit.centre_meter(s, "flow", L, SPAN, FLOW_Y, FLOW_H,
                              mid=L + SPAN // 2)),
            ("amps", AMP_X, AMP_Y, bigfont.width("00", AMP_S),
             bigfont.char_h(AMP_S),
             lambda f, b: kit.fit(abs(f["avg_motor_current"])),
             kit.big(s, "amps", AMP_X, AMP_Y, AMP_S)),
            ("pack", PACK_X, AMP_Y, bigfont.width("00", AMP_S),
             bigfont.char_h(AMP_S),
             lambda f, b: kit.fit(abs(f["avg_input_current"])),
             kit.big(s, "pack", PACK_X, AMP_Y, AMP_S)),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("pct", PCT_X, PCT_Y, bigfont.width("100", PCT_S),
             bigfont.char_h(PCT_S), kit.charge_text,
             kit.big(s, "pct", PCT_X, PCT_Y, PCT_S)),
            ("batt", L, BATT_Y, SPAN, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, L, BATT_Y, SPAN, BATT_H, segs=16, gap=2)),
            ("foot", L, FOOT_Y, SPAN, 12,
             lambda f, b: ("" if f["fault"] else
                           "%.1f V   %s KM   %d C"
                           % (f["input_voltage"], kit.range_text(f, b),
                              round(f["temp_fet_filtered"]))),
             kit.quiet(s.value_painter("foot", L, FOOT_Y, scale=LABEL))),
        )
