"""Hybrid - calm, and about efficiency.

Soft blues, and range promoted above speed. The layout for a long day on grass: the question it
answers first is not how fast you are going but how far you can keep going,
and it puts the two figures that decide that at the top.

The instrument in the middle is a semicircular gauge that runs from charge on
the left to power on the right through a hard zero at the top. A bar tells you
a number; an arc tells you a proportion, and on a long ride the proportion is
what you are actually watching.
"""
from .. import bigfont, bands
from ..base import W, LABEL
from . import Base
from . import kit

L, R = 16, W - 16
SPAN = R - L

#: Range leads and speed is the smaller figure beside it. The inversion is
#: the whole thesis of this layout.
RANGE_X, RANGE_Y, RANGE_S = 16, 40, 13        # 104 x 65
SPEED_X, SPEED_Y, SPEED_S = 136, 46, 11       # 88 x 55
LABEL_TOP = 28

#: Nothing else may sit inside the gauge's box. The band is repainted whole
#: every time the needle moves and fills with the ground colour first, so a
#: numeral clearing its own box on top of the arc rubs the arc out.
GAUGE_CX, GAUGE_CY, GAUGE_R = 120, 190, 66
GAUGE_T = 9
A0, A1 = -90.0, 90.0
GAUGE_TOP = GAUGE_CY - GAUGE_R - 4
GAUGE_H = GAUGE_R + 6                         # ends at 192
ENDS_Y = GAUGE_TOP + GAUGE_H + 2              # CHG and PWR, under the ends

AMP_S = 8                                     # the reading, in the mouth
#: Four pixels lower than centred. The dial's mouth narrows as it rises, and
#: the numeral's top corners were grazing the inside of the arc - which the
#: full repaint drew and the differential one cleared.
AMP_Y = GAUGE_CY - bigfont.char_h(AMP_S) - 2

BATT_Y, BATT_H = 208, 12
BOT_Y, BOT_S = 236, 7                         # charge and volts, 236..271
FOOT_Y = 288
FAULT_Y, FAULT_H = 232, 70    # over the bottom row AND the footnote it blanks


def _angle(frac):
    """Signed -1..1 to a position on the half dial."""
    return (A0 + A1) / 2.0 + (A1 - A0) / 2.0 * max(-1.0, min(1.0, frac))


def _track(c, t):
    """The unlit gauge, and the mark at its centre."""
    dd = min(1.0, 57.3 / GAUGE_R)
    deg = A0
    while deg <= A1:
        sin, cos = bands.sincos(deg)
        c.spoke(GAUGE_CX, GAUGE_CY, GAUGE_R - GAUGE_T, GAUGE_R, sin, cos,
                t.track, 2)
        deg += dd
    # Zero, at the top: the one place on the dial that means coasting.
    sin, cos = bands.sincos(0.0)
    c.spoke(GAUGE_CX, GAUGE_CY, GAUGE_R - GAUGE_T - 5, GAUGE_R + 3,
            sin, cos, t.ink, 2)


class Layout(Base):
    grid_exceptions = {
        "range": "the hero on this layout", "speed": "demoted, deliberately",
        "gauge": "a half dial has no column", "amps": "in the dial's mouth",
        "batt": "spans the width", "pct": "bottom row", "volts": "bottom row",
        "foot": "footnotes", "fault": "displaces the bottom row",
    }
    overlap_exceptions = {("fault", "foot"), ("fault", "pct"),
                          ("fault", "volts"), ("gauge", "amps")}
    tweens = {"gauge": (4, 4.0)}

    def target(self, key, s, f, b):
        return _angle(f["avg_motor_current"] / max(1.0, b.motor_current))

    def chrome(self, s, d):
        t = s.t
        bands.paint(d, 0, GAUGE_TOP, W, GAUGE_H,
                    lambda c: (c.fill(t.ground), _track(c, t)))
        d.set_color(t.dim, t.ground)
        for x, y, txt in ((RANGE_X, LABEL_TOP, "RANGE KM"),
                          (SPEED_X, LABEL_TOP, "KM/H"),
                          (L, ENDS_Y, "CHG"), (R - 24, ENDS_Y, "PWR"),
                          (L, BOT_Y - 12, "CHARGE"),
                          (R - 48, BOT_Y - 12, "VOLTS")):
            d.set_pos(x, y)
            d.print(txt)

    def regions(self, s):
        amp_w = bigfont.width("00", AMP_S)
        return (
            ("fault", L, FAULT_Y, SPAN, FAULT_H, kit.fault_text,
             kit.banner(s, L, FAULT_Y, SPAN, FAULT_H,
                        ("pct", "volts", "foot"))),
            ("range", RANGE_X, RANGE_Y, bigfont.width("99", RANGE_S),
             bigfont.char_h(RANGE_S), kit.range_text,
             kit.big(s, "range", RANGE_X, RANGE_Y, RANGE_S)),
            ("speed", SPEED_X, SPEED_Y, bigfont.width("00", SPEED_S),
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", SPEED_X, SPEED_Y, SPEED_S)),
            ("gauge", 0, GAUGE_TOP, W, GAUGE_H,
             lambda f, b: s.tw("gauge"),
             kit.arc_sweep(s, "gauge", GAUGE_CX, GAUGE_CY, GAUGE_R, GAUGE_T,
                           A0, A1,
                           # Regen and drive are different things, not more or
                           # less of the same thing.
                           lambda f, b, t: (t.accent
                                            if f["avg_motor_current"] < 0
                                            else t.warn),
                           under=_track, forces=("amps",), from_mid=True)),
            ("amps", GAUGE_CX - amp_w // 2, AMP_Y, amp_w,
             bigfont.char_h(AMP_S),
             lambda f, b: kit.fit(abs(f["avg_motor_current"])),
             kit.big(s, "amps", GAUGE_CX - amp_w // 2, AMP_Y, AMP_S)),
            ("batt", L, BATT_Y, SPAN, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, L, BATT_Y, SPAN, BATT_H, segs=14, gap=3)),
            ("pct", L, BOT_Y, bigfont.width("100", BOT_S),
             bigfont.char_h(BOT_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", L, BOT_Y, BOT_S)),
            ("volts", R - 84, BOT_Y, bigfont.width("00", BOT_S),
             bigfont.char_h(BOT_S),
             lambda f, b: ("" if f["fault"]
                           else kit.fit(f["input_voltage"])),
             kit.big(s, "volts", R - 84, BOT_Y, BOT_S)),
            ("foot", L, FOOT_Y, SPAN, 12,
             lambda f, b: ("" if f["fault"] else
                           "FET %sC  MOT %sC  %sWH"
                           % (kit.fit(f["temp_fet_filtered"], 3),
                              kit.fit(f["temp_motor_filtered"], 3),
                              kit.fit(f["s_wh_per_km"])
                              if f.get("s_wh_per_km") else "--")),
             kit.quiet(s.value_painter("foot", L, FOOT_Y, scale=LABEL))),
        )
