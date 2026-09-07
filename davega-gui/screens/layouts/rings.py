"""Silver - layered and restrained.

Concentric hairline rings, deep graphite, one red hand. It reads expensive
because almost nothing on it is coloured: three rings a pixel or two wide, a
numeral, and the single moving thing on the screen.

The hand is the one place in the ten where the original drawing asks for more
than the panel gives cheaply. A hand's bounding box is the whole dial, and it
moves every frame. It is affordable here because it is painted as the union of
where it was and where it is - a thin wedge - with the rings redrawn inside
that wedge so it leaves no trail. That keeps a frame in budget at the cost of
this being one of the more expensive of the nine to run.
"""
from .. import bigfont, bands
from ..base import W, LABEL
from . import Base
from . import kit

CX, CY = 120, 132
RINGS = ((104, 1), (96, 2), (72, 1))
A0, A1 = -140.0, 140.0
KPH_MAX = 45.0
#: The hand starts outside the numeral rather than at the hub. A hand that
#: crosses the numeral is wiped every time a digit changes, and this is the
#: compromise the feasibility check called for: a long hand, not a full one.
HAND_R0, HAND_R1 = 60, 92
TOP = 26

SPEED_S = 12
#: below the hand's reach. The hand's box is the whole dial - CY + HAND_R1 is
#: 224 - so a label anywhere inside that circle is scrubbed the first time the
#: needle passes over it.
UNIT_Y = 228

BATT_Y, BATT_H = 248, 10
BIG_Y, BIG_S = 270, 9
FAULT_Y, FAULT_H = 268, 48    # past the numerals, or their last row survives


def _angle(kph):
    return A0 + (A1 - A0) * max(0.0, min(1.0, kph / KPH_MAX))


def _face(c, t):
    """The rings and their five markers.

    Passed to the hand as its `under`, so it must draw *everything* chrome
    draws inside the band - the markers included. Leaving them out cost two
    pixels where a marker crosses a ring, which is exactly the kind of thing
    a differential renderer hides until someone diffs the two paths.
    """
    for r, thick in RINGS:
        c.ring(CX, CY, r, t.dim, thick)
    for i in range(5):
        deg = A0 + i * (A1 - A0) / 4.0
        sin, cos = bands.sincos(deg)
        c.spoke(CX, CY, RINGS[0][0] - 8, RINGS[0][0], sin, cos, t.dim, 2)


class Layout(Base):
    grid_exceptions = {
        "hand": "a hand has no column", "speed": "centred in the rings",
        "batt": "spans the width", "pct": "under the rings",
        "range": "paired with pct", "fault": "displaces both",
    }
    overlap_exceptions = {("hand", "speed"), ("fault", "pct"),
                          ("fault", "range")}
    tweens = {"hand": (6, 8.0)}

    def target(self, key, s, f, b):
        return _angle(kit.kph(f, b))

    def chrome(self, s, d):
        t = s.t
        bands.paint(d, 0, TOP, W, (CY + RINGS[0][0] + 6) - TOP,
                    lambda c: (c.fill(t.ground), _face(c, t)))
        d.set_color(t.dim, t.ground)
        for x, y, txt in ((CX - 16, UNIT_Y, "KM/H"), (16, BIG_Y - 12, "CHARGE"),
                          (W - 16 - 72, BIG_Y - 12, "RANGE KM")):
            d.set_pos(x, y)
            d.print(txt)

    def regions(self, s):
        sw = bigfont.width("00", SPEED_S)
        return (
            ("fault", 16, FAULT_Y, W - 32, FAULT_H, kit.fault_text,
             kit.banner(s, 16, FAULT_Y, W - 32, FAULT_H, ("pct", "range"))),
            ("hand", CX - HAND_R1, CY - HAND_R1, 2 * HAND_R1, 2 * HAND_R1,
             lambda f, b: s.tw("hand"),
             kit.needle(s, "hand", CX, CY, HAND_R0, HAND_R1,
                        width=3, under=_face, forces=("speed",))),
            ("speed", CX - sw // 2, CY - bigfont.char_h(SPEED_S) // 2, sw,
             bigfont.char_h(SPEED_S), kit.speed_text,
             kit.big(s, "speed", CX - sw // 2,
                     CY - bigfont.char_h(SPEED_S) // 2, SPEED_S)),
            ("batt", 16, BATT_Y, W - 32, BATT_H,
             lambda f, b: kit.soc(b, f["input_voltage"], f),
             kit.seg_bar(s, 16, BATT_Y, W - 32, BATT_H, segs=24, gap=2)),
            ("pct", 16, BIG_Y, bigfont.width("100", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.charge_text(f, b),
             kit.big(s, "pct", 16, BIG_Y, BIG_S)),
            ("range", W - 16 - 72, BIG_Y, bigfont.width("99", BIG_S),
             bigfont.char_h(BIG_S),
             lambda f, b: "" if f["fault"] else kit.range_text(f, b),
             kit.big(s, "range", W - 16 - 72, BIG_Y, BIG_S)),
        )
