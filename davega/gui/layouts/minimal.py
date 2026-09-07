"""Minimal - one number, then silence.

Speed fills the frame; everything else is a thin line of grey until it needs
you. The cheapest of the nine to run and the easiest to read at speed, which
are the same property seen from two directions: fewer things drawn is fewer
draw calls and less to look past.

The one concession is the charge strip along the bottom. A speedometer that
will not tell you when to turn back is an ornament.
"""
from .. import bigfont
from ..base import W, LABEL
from . import Base
from . import kit

SPEED_X, SPEED_Y, SPEED_S = 8, 52, 28         # 224 x 140, the full width
UNIT_X, UNIT_Y = 200, 200

STRIP_Y, STRIP_H = 236, 10
PCT_X, PCT_Y, BIG_S = 20, 254, 10
FAULT_Y, FAULT_H = 254, 60


class Layout(Base):
    grid_exceptions = {
        "speed": "the frame is the numeral",
        "strip": "charge runs the full width",
        "pct": "sits under its own strip",
        "range": "paired with pct", "fault": "displaces both",
    }
    overlap_exceptions = {("fault", "pct"), ("fault", "range")}

    def chrome(self, s, d):
        t = s.t
        d.fill_rectangle(20, STRIP_Y, W - 40, STRIP_H, t.track)
        d.set_color(t.dim, t.ground)
        d.set_pos(UNIT_X, UNIT_Y)
        d.print("KM/H")

    def regions(self, s):
        return (
            ("fault", 20, FAULT_Y, W - 40, FAULT_H, kit.fault_text,
             kit.banner(s, 20, FAULT_Y, W - 40, FAULT_H, ("pct", "range"))),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("strip", 20, STRIP_Y, W - 40, STRIP_H,
             lambda f, b: int((W - 40) * kit.soc(b, f["input_voltage"], f)),
             kit.hbar(s, "strip", 20, STRIP_Y, W - 40, STRIP_H,
                      lambda f, b, t: t.soc_color(
                          kit.soc(b, f["input_voltage"], f)))),
            ("pct", PCT_X, PCT_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", PCT_X, PCT_Y, BIG_S)),
            ("range", W - 12 - 80, PCT_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", W - 12 - 80, PCT_Y, BIG_S)),
        )
