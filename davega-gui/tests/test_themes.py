#!/usr/bin/env python3
"""Every theme goes through the same harness as the default.

A theme that only looks right in a mockup is a mockup, not a theme. Each one
renders every frame in the envelope, stays inside the display, stays inside the
drawing budget, and its differential rendering matches a full repaint.

It also asserts the palettes in themes.py are the values the mockup page shows,
so the pictures cannot quietly drift from what the device draws.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from harness.display import Display, OutOfBounds       # noqa: E402
from harness.telemetry import Board                    # noqa: E402
from screens.riding import Riding                      # noqa: E402
from screens.themes import THEMES, DEFAULT, get        # noqa: E402
from screens.palette import (contrast, separation, separation_cb,  # noqa: E402
                             MIN_PRIMARY, MIN_LABEL, MIN_SEPARATION,
                             MIN_SEPARATION_CB)

MOCKUPS = os.path.join(ROOT, "mockups", "themes.html")
THEMES_PY = os.path.join(ROOT, "screens", "themes.py")
BUDGET_FULL = 1.30
BUDGET_STEADY = 0.07

def settle(screen, d, frame, board, limit=40):
    """Render until nothing is mid-animation.

    With a tween on screen the differential path is deliberately *not*
    identical to a full repaint on any given frame - it is on its way there.
    The invariant that matters is that it converges.
    """
    for _ in range(limit):
        screen.render(d, frame, board)
        if not hasattr(screen, "settled") or screen.settled():
            return


fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


def main():
    board = Board()
    env = board.envelope()

    print("== every theme renders every frame, inside the display")
    for key in sorted(THEMES):
        bad = None
        for name, frame in env:
            try:
                Riding(key).render(Display(), frame, board, full=True)
            except OutOfBounds as e:
                bad = "%s: %s" % (name, e)
                break
        check("renders/%s" % key, bad is None, bad or "")

    print()
    print("== differential rendering matches a full repaint, per theme")
    for key in sorted(THEMES):
        bad = None
        for from_name, from_frame in env:
            for to_name, to_frame in env:
                inc, screen = Display(), Riding(key)
                settle(screen, inc, from_frame, board)
                settle(screen, inc, to_frame, board)
                full = Display()
                Riding(key).render(full, to_frame, board, full=True)
                if inc.pixels != full.pixels:
                    bad = "%s -> %s leaves stale pixels" % (from_name, to_name)
                    break
            if bad:
                break
        check("differential/%s" % key, bad is None, bad or "")

    print()
    print("== drawing budget, per theme")
    for key in sorted(THEMES):
        d, screen = Display(), Riding(key)
        screen.render(d, board.nominal(), board)
        first = d.px_written
        d.px_written = 0
        screen.render(d, board.frame(**dict(board.nominal(),
                                            rpm=board.erpm_for_kph(26.0))), board)
        steady = d.px_written
        ok = (first <= d.full_frame_px * BUDGET_FULL
              and steady <= d.full_frame_px * BUDGET_STEADY)
        check("budget/%-11s first %.2fx  steady %.3fx"
              % (key, first / d.full_frame_px, steady / d.full_frame_px), ok)

    print()
    print("== contrast: a dash is read in sunlight, at speed, while vibrating")
    # Grey on black looks refined on a monitor and is unreadable on a 2.8"
    # panel outdoors. This is the constraint that keeps taste in check.
    for key in sorted(THEMES):
        t = THEMES[key]
        checks = (("ink", t.ink, MIN_PRIMARY), ("accent", t.accent, MIN_LABEL),
                  ("dim", t.dim, MIN_LABEL), ("warn", t.warn, MIN_LABEL),
                  ("danger", t.danger, MIN_LABEL))
        worst, worst_name, worst_min = 99.0, "", 0
        for name, col, floor in checks:
            r = contrast(col, t.ground)
            if r / floor < worst / max(1, worst_min):
                worst, worst_name, worst_min = r, name, floor
        ok = all(contrast(c, t.ground) >= f for _, c, f in checks)
        check("contrast/%-11s worst %s %.1f:1 (floor %.1f)"
              % (key, worst_name, worst, worst_min), ok)

    print()
    print("== semantic colours are tellable apart, including colour blind")
    # A theme can clear every contrast bar and still be useless: if "getting
    # warm" and "fault" are the same red, or nothing can be highlighted
    # because the accent is the text colour, the palette cannot carry state.
    for key in sorted(THEMES):
        t = THEMES[key]
        wd = separation(t.warn, t.danger)
        cb = separation_cb(t.warn, t.danger)
        ia = separation(t.accent, t.ink)
        ok = wd >= MIN_SEPARATION and cb >= MIN_SEPARATION_CB and ia >= 12
        check("semantic/%-11s warn~danger %.0f (cb %.0f)  accent~ink %.0f"
              % (key, wd, cb, ia), ok)

    print()
    print("== the mockups show the colours the device draws")
    if not os.path.exists(MOCKUPS):
        check("mockups present", False, MOCKUPS + " is missing")
    else:
        shown = set(x.upper() for x in re.findall(r"#([0-9A-Fa-f]{6})", open(MOCKUPS).read()))
        declared = set(x.upper() for x in re.findall(r'"#([0-9A-Fa-f]{6})"', open(THEMES_PY).read()))
        missing = sorted(declared - shown)
        check("all %d theme colours appear in the mockups" % len(declared),
              not missing, "absent: " + ", ".join(missing))

    print()
    check("default theme exists", DEFAULT in THEMES)
    check("unknown theme falls back to the default", get("nope").key == DEFAULT)
    check("ten themes", len(THEMES) == 10, "found %d" % len(THEMES))

    print()
    if fails:
        print("%d THEME TESTS FAILED" % len(fails))
        return 1
    print("all theme tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
