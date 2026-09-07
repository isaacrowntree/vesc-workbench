"""Rosso - the tachometer is the hero.

Speed sits inside a full analogue ring with a coloured face and a redline that
sweeps into view. The only layout that gives the circle the whole screen, and
the one that most obviously could not be drawn the way the others are: a
96 px-radius arc built from one rectangle per column costs 481 ms, which is
half a second of a frame that gets 120.

So the face, the bezel and the twenty-one ticks are composed into a buffer and
pushed with `writeblock` - once, as furniture - and the sweep is composed the
same way, into a band that covers only the dial.
"""
from .. import bigfont, bands
from ..base import W, LABEL
from . import Base
from . import kit

CX, CY, R = 120, 126, 98
FACE_TOP = 26
A0, A1 = -130.0, 130.0                        # the sweep, 0 = twelve o'clock
KPH_MAX = 45.0
REDLINE = 0.78                                # of the sweep

#: 104 x 65, whose corner sits 61 px from the centre - inside SWEEP_R's
#: inner edge, so the numeral's clear never touches the arc
SPEED_S = 13
SWEEP_R, SWEEP_T = 78, 8
#: below the dial, not inside it: the sweep's band reaches to the bottom of
#: the arc, and anything painted inside that circle is scrubbed off behind
#: the needle
UNIT_Y = 236

STRIP_Y = 246                                 # the block under the dial
BATT_Y, BATT_H = 246, 12   # clear of the labels at BIG_Y - 12
BIG_Y, BIG_S = 274, 9      # 274 + 45 = 319, the last usable row
FAULT_Y, FAULT_H = 272, 48    # down to the panel edge, or a row survives


def _face(c, t):
    """Bezel, dial and well, plus the ticks.

    Also passed to the sweep as its `under`: the sweep composes a band around
    the arc, and that band is a rectangle that reaches well past it into the
    ticks and the bezel. Filling it with ground and not putting the face back
    scrubs the dial clean behind the needle.
    """
    c.disc(CX, CY, R + 6, t.track)
    c.ring(CX, CY, R, t.accent, 3)
    c.disc(CX, CY, R - 18, t.ground)
    for i in range(21):
        deg = A0 + i * (A1 - A0) / 20.0
        sin, cos = bands.sincos(deg)
        major = (i % 5 == 0)
        inner = R - (16 if major else 9)
        col = t.danger if i / 20.0 > REDLINE else t.ink
        c.spoke(CX, CY, inner, R - 4, sin, cos, col, 3 if major else 1)


def _angle(kph):
    return A0 + (A1 - A0) * max(0.0, min(1.0, kph / KPH_MAX))


class Layout(Base):
    grid_exceptions = {
        "sweep": "an arc has no column", "speed": "centred in the dial",
        "batt": "spans the strip", "pct": "in the strip",
        "range": "paired with pct", "fault": "takes the strip",
    }
    overlap_exceptions = {("fault", "pct"), ("fault", "range"),
                          ("sweep", "speed")}
    tweens = {"sweep": (5, 6.0)}

    def target(self, key, s, f, b):
        return _angle(kit.kph(f, b))

    def chrome(self, s, d):
        t = s.t
        # The face: bezel, dial, well. One composed picture, one transfer per
        # band, and never touched again until the theme changes.
        bands.paint(d, 0, FACE_TOP, W, (CY + R + 8) - FACE_TOP,
                    lambda c: (c.fill(t.ground), _face(c, t)))

        d.set_color(t.dim, t.ground)
        d.set_pos(CX - 16, UNIT_Y)
        d.print("KM/H")
        d.set_pos(16, BIG_Y - 12)
        d.print("CHARGE")
        d.set_pos(W - 16 - 72, BIG_Y - 12)
        d.print("RANGE KM")

    def regions(self, s):
        sw = bigfont.width("00", SPEED_S)
        return (
            ("fault", 16, FAULT_Y, W - 32, FAULT_H, kit.fault_text,
             kit.banner(s, 16, FAULT_Y, W - 32, FAULT_H, ("pct", "range"))),
            # The sweep's box is the dial, because an arc's bounding box is.
            ("sweep", CX - R, CY - R, 2 * R, 2 * R,
             lambda f, b: s.tw("sweep"),
             kit.arc_sweep(s, "sweep", CX, CY, SWEEP_R, SWEEP_T, A0, A1,
                           lambda f, b, t: t.accent,
                           redline=A0 + (A1 - A0) * REDLINE, hot=s.t.danger,
                           # the sweep is inside the well, so it recedes to
                           # the ground and not to the bezel's track
                           unlit=s.t.ground, under=_face,
                           forces=("speed",))),
            ("speed", CX - sw // 2, CY - bigfont.char_h(SPEED_S) // 2, sw,
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", CX - sw // 2,
                     CY - bigfont.char_h(SPEED_S) // 2, SPEED_S)),
            ("batt", 16, BATT_Y, W - 32, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, 16, BATT_Y, W - 32, BATT_H, segs=20, gap=2)),
            ("pct", 16, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", 16, BIG_Y, BIG_S)),
            ("range", W - 16 - 72, BIG_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", W - 16 - 72, BIG_Y, BIG_S)),
        )
