"""Ghost - almost nothing.

One enormous numeral, a hairline of gold, and acres of black. No gauges, no
bars: the numbers are the instrument. The discipline is that anything which
does not earn its place is not drawn, so what is left has to be large enough
to read in one glance and nothing has to compete with it.

The hairline is the only ornament, and it is doing work: it separates the
speed from the two figures under it without a box, a border or a fill.
"""
from .. import bigfont
from ..base import W, LABEL
from . import Base
from . import kit

RULE_Y = 176
SPEED_X, SPEED_Y, SPEED_S = 26, 34, 26        # 208 x 130, the whole width
#: clear of the numeral's box (34..164). A label inside it is wiped every
#: time a digit changes and never put back, because the numeral repaints
#: itself and the label is chrome.
UNIT_X, UNIT_Y = 196, 166

PCT_X, PCT_Y, BIG_S = 20, 208, 10
RANGE_X = W - 12 - 80          # clear of pct, which is 120 wide
LABEL_Y = 196
FOOT_Y = 296
FAULT_Y, FAULT_H = 208, 55


class Layout(Base):
    grid_exceptions = {
        "speed": "the instrument; everything else is a caption",
        "pct": "paired against the right edge", "range": "paired with pct",
        "fault": "displaces both figures",
        "volts": "footnote, under the rule",
    }
    overlap_exceptions = {("fault", "pct"), ("fault", "range")}

    def chrome(self, s, d):
        t = s.t
        # One hairline. The whole layout hangs off it.
        d.fill_rectangle(20, RULE_Y, W - 40, 1, t.accent)
        d.set_color(t.dim, t.ground)
        for x, y, txt in ((UNIT_X, UNIT_Y, "KM/H"),
                          (PCT_X, LABEL_Y, "CHARGE"),
                          (RANGE_X, LABEL_Y, "RANGE KM")):
            d.set_pos(x, y)
            d.print(txt)

    def regions(self, s):
        return (
            ("fault", 20, FAULT_Y, W - 40, FAULT_H, kit.fault_text,
             kit.banner(s, 20, FAULT_Y, W - 40, FAULT_H, ("pct", "range"))),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("pct", PCT_X, PCT_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", PCT_X, PCT_Y, BIG_S)),
            ("range", RANGE_X, PCT_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", RANGE_X, PCT_Y, BIG_S)),
            ("volts", 20, FOOT_Y, W - 40, 12,
             lambda f, b: "%.1f V   %.0fA   %d C" % (f["input_voltage"],
                                                     f["avg_input_current"],
                                                     round(f["temp_fet_filtered"])),
             s.value_painter("volts", 20, FOOT_Y, scale=LABEL)),
        )
