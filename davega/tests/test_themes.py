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
from gui.riding import Riding                      # noqa: E402
from gui.themes import THEMES, DEFAULT, get, light_theme  # noqa: E402
from gui import themes as themes_module                       # noqa: E402

# The light variants are built on demand on the device, to keep ten of them
# off a small heap. The tests want them all, so they ask for them all.
LIGHT = dict((k, light_theme(k)) for k in THEMES)
from gui.palette import (contrast, separation, separation_cb,  # noqa: E402
                             MIN_PRIMARY, MIN_LABEL, MIN_SEPARATION,
                             MIN_SEPARATION_CB, MIN_TRACK, MIN_LIT)

MOCKUPS = os.path.join(ROOT, "mockups", "index.html")
THEMES_PY = os.path.join(ROOT, "gui", "themes.py")
# The Nazare layout paints a rail, a flow meter and fourteen battery segments
# on top of a full erase, so a first paint touches a little over the frame
# area. Pixels are the cheap part on this hardware - the ms budgets in
# test_ui.py are the ones that bite.
#: A full repaint is allowed to be slow - it happens on a theme change and a
#: wake, not while riding. A settled frame is what runs at 8 fps.
FULL_MS = 900
SETTLED_MS = 120

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
    # In milliseconds, not pixels. Once a layout composes a curve into a band
    # and pushes it with writeblock, pixels stop being the cost: a 9,600 px
    # band is 12 ms and a single fill_rectangle of nine pixels is 2.9. Time is
    # what the rider feels.
    for key in sorted(THEMES):
        d, screen = Display(), Riding(key)
        screen.render(d, board.nominal(), board, full=True)
        for _ in range(20):
            screen.render(d, board.nominal(), board)
            if screen.settled():
                break
        first = d.est_ms
        d2 = Display()
        screen.render(d2, board.frame(**dict(board.nominal(),
                                             rpm=board.erpm_for_kph(26.0))),
                      board)
        ok = first <= FULL_MS and d2.est_ms <= SETTLED_MS
        check("budget/%-11s first %4.0f ms  steady %5.1f ms"
              % (key, first, d2.est_ms), ok)

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
    print("== a gauge shows where it ends, not just how far it has come")
    # The unlit segments are the reading. A battery bar whose empty end is
    # invisible in sunlight tells you a third is left by looking exactly like
    # a bar a third as long floating in the dark.
    for name, group in (("dark", THEMES), ("light", LIGHT)):
        for key in sorted(group):
            t = group[key]
            tg = contrast(t.track, t.ground)
            lit = contrast(t.accent, t.track)
            check("track/%-5s %-11s %.2f on ground, accent %.1f over it"
                  % (name, key, tg, lit),
                  tg >= MIN_TRACK and lit >= MIN_LIT)

    print()
    print("== the light variants clear contrast and normal-vision separation")
    for key in sorted(LIGHT):
        t = LIGHT[key]
        ink = contrast(t.ink, t.ground)
        acc = contrast(t.accent, t.ground)
        dim = contrast(t.dim, t.ground)
        wd = separation(t.warn, t.danger)
        ai = separation(t.accent, t.ink)
        ok = (ink >= MIN_PRIMARY and acc >= MIN_LABEL and dim >= MIN_LABEL
              and wd >= MIN_SEPARATION and ai >= 12)
        check("light/%-11s ink %.1f  warn~danger %.0f  accent~ink %.0f"
              % (key, ink, wd, ai), ok)

    # Colour blindness on a light ground is a known shortfall, reported rather
    # than hidden. Every colour has to darken to be readable on paper, and two
    # dark warm colours are closer under deuteranopia than two bright ones on
    # black. Three themes clear the dark-theme bar; the rest sit at 10-13.
    short = [k for k in sorted(LIGHT)
             if separation_cb(LIGHT[k].warn, LIGHT[k].danger) < MIN_SEPARATION_CB]
    print("        colour-blind separation below %.0f on light: %s"
          % (MIN_SEPARATION_CB, ", ".join(short) if short else "none"))
    worst = min(separation_cb(LIGHT[k].warn, LIGHT[k].danger) for k in LIGHT)
    check("light colour blindness never regresses below its floor (%.1f)" % worst,
          worst >= 9.5)

    print()
    print("== a light variant exists for every theme, and differs from it")
    check("same set of keys", set(LIGHT) == set(THEMES))
    check("every light ground is lighter than its dark one",
          all(contrast(LIGHT[k].ground, 0x0000) > contrast(THEMES[k].ground, 0x0000)
              for k in THEMES))
    lit = get("rosso", True)
    check("get(key, light=True) returns the light one",
          lit.light and lit.ground == LIGHT["rosso"].ground
          and get("rosso") is THEMES["rosso"])
    check('the "@light" suffix means the same thing',
          get("rosso@light").ground == lit.ground)

    # Derived on demand and only one kept. A rider looks at one theme; caching
    # the other nine caches nothing anybody is looking at, and on the board
    # cycling the themes in day mode ran it out of memory where night mode
    # survived.
    for k in sorted(THEMES):
        get(k, True)
    check("only the light variant in use is cached (%d held)"
          % len(themes_module.LIGHT), len(themes_module.LIGHT) == 1,
          "holding %d" % len(themes_module.LIGHT))

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
