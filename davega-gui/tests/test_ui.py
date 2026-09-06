#!/usr/bin/env python3
"""The whole UI: every screen, the conversions, and the buttons.

Conversions are pinned to values read off the device's own
`frozen.screen_values`, so our arithmetic cannot drift from what the stock
firmware would have shown. That check already caught a tachometer conversion
that was out by a factor of two.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from harness.display import Display, OutOfBounds                  # noqa: E402
from harness.telemetry import Board                               # noqa: E402
from screens.riding import Riding                                 # noqa: E402
from screens.panels import (RangeScreen, OverviewScreen,          # noqa: E402
                            SessionScreen, LifetimeScreen)
from screens.app import App, Menu, MenuItem, UP, DOWN, ENTER, HOLD  # noqa: E402
from screens.themes import THEMES                                 # noqa: E402

SCREENS = (("riding", Riding), ("range", RangeScreen),
           ("overview", OverviewScreen), ("session", SessionScreen),
           ("lifetime", LifetimeScreen))

# Device-measured constants (see harness/display.py). A settled frame has to
# stay usable against 5 Hz telemetry; a full repaint is allowed to be slow
# because it happens once per screen change.
MAX_SETTLED_MS = 120
MAX_FULL_MS = 900

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
    b = Board()
    env = b.envelope()

    print("== conversions match the device's own")
    # Read off frozen.screen_values on a DAVEGA X running v5.06.
    check("erpm_to_kph(35094) == 45.0004",
          abs(b.kph_for_erpm(35094) - 45.00043) < 0.001,
          "got %.5f" % b.kph_for_erpm(35094))
    check("tachometer_to_km(120000) == 0.4274",
          abs(b.km_for_tacho(120000) - 0.4274276) < 0.0001,
          "got %.6f" % b.km_for_tacho(120000))
    check("max_wh == 587.52",
          abs(b.usable_watt_hours - 587.52) < 0.01,
          "got %.2f" % b.usable_watt_hours)
    check("soc curve ends at 0 and 1",
          b.soc_for_voltage(36.0) == 0.0 and b.soc_for_voltage(50.4) == 1.0)
    check("soc is monotonic across the pack range",
          all(b.soc_for_voltage(v) <= b.soc_for_voltage(v + 0.2)
              for v in [36.0 + i * 0.2 for i in range(70)]))

    print()
    print("== every screen renders every frame, inside the display")
    for name, cls in SCREENS:
        bad = None
        for fname, frame in env:
            try:
                cls("nazare").render(Display(), frame, b, full=True)
            except OutOfBounds as e:
                bad = "%s: %s" % (fname, e)
                break
        check("renders/%s" % name, bad is None, bad or "")

    print()
    print("== every screen in every theme")
    for name, cls in SCREENS:
        bad = None
        for key in sorted(THEMES):
            try:
                cls(key).render(Display(), b.nominal(), b, full=True)
            except OutOfBounds as e:
                bad = "%s/%s: %s" % (name, key, e)
                break
        check("themed/%s" % name, bad is None, bad or "")

    print()
    print("== declared regions do not overlap")
    # Overlapping regions are invisible on a full repaint and corrupt the
    # differential path, because repainting one clears part of another.
    for name, cls in SCREENS:
        regions = cls("nazare").regions()
        clash = None
        for i, a in enumerate(regions):
            for c in regions[i + 1:]:
                ax, ay, aw, ah = a[1], a[2], a[3], a[4]
                cx, cy, cw, ch = c[1], c[2], c[3], c[4]
                if (ax < cx + cw and cx < ax + aw
                        and ay < cy + ch and cy < ay + ah):
                    clash = "%s overlaps %s" % (a[0], c[0])
                    break
            if clash:
                break
        check("layout/%s" % name, clash is None, clash or "")

    print()
    print("== differential rendering matches a full repaint, every screen")
    for name, cls in SCREENS:
        bad = None
        for a, fa in env:
            for c, fc in env:
                inc, s = Display(), cls("nazare")
                settle(s, inc, fa, b)
                settle(s, inc, fc, b)
                full = Display()
                cls("nazare").render(full, fc, b, full=True)
                if inc.pixels != full.pixels:
                    bad = "%s -> %s" % (a, c)
                    break
            if bad:
                break
        check("differential/%s" % name, bad is None, bad or "")

    print()
    print("== frame time, from the device's measured cost model")
    for name, cls in SCREENS:
        d, s = Display(), cls("nazare")
        s.render(d, b.nominal(), b, full=True)
        full_ms = d.est_ms
        f2 = b.nominal()
        f2["rpm"] = b.erpm_for_kph(26.0)
        f2["input_voltage"] = b.v_nominal - 0.4
        d.px_written = d.chars_written = 0
        d.calls = []
        s.render(d, f2, b)
        settled = d.est_ms
        check("time/%-9s full %4.0f ms  settled %3.0f ms" % (name, full_ms, settled),
              full_ms <= MAX_FULL_MS and settled <= MAX_SETTLED_MS)

    print()
    print("== buttons and the menu")
    app = App([(n, c) for n, c in SCREENS], b, "nazare",
              Menu([MenuItem("Theme", ["nazare", "rosso", "ghost"]),
                    MenuItem("Units", ["metric", "imperial"])]))
    check("starts on the first screen", app.key == "riding")
    app.press(DOWN)
    check("down moves forward", app.key == "range")
    app.press(UP)
    app.press(UP)
    check("up wraps backwards", app.key == "lifetime")
    app.press(ENTER)
    check("enter opens the menu", app.in_menu)
    d = Display()
    app.render(d, b.nominal())
    check("menu draws", len(d.calls) > 0)
    app.press(DOWN)
    check("down moves the cursor, not the screen",
          app.menu.cursor == 1 and app.key == "lifetime")
    app.press(ENTER)
    check("enter cycles the value", app.menu.items[1].value == "imperial")
    app.press(HOLD)
    check("hold leaves the menu", not app.in_menu)

    d = Display()
    app.render(d, b.nominal())
    check("returning from the menu repaints fully", len(d.calls) > 20)

    app.set_theme("rosso")
    check("theme change drops cached screens", app._live == {})
    d = Display()
    app.render(d, b.nominal())
    check("renders in the new theme", len(d.calls) > 0)

    print()
    print("== every screen is reachable")
    app2 = App([(n, c) for n, c in SCREENS], b, "nazare")
    seen = {app2.key}
    for _ in range(len(SCREENS) - 1):
        app2.press(DOWN)
        seen.add(app2.key)
    check("all %d screens reachable by pressing down" % len(SCREENS),
          len(seen) == len(SCREENS), "reached %s" % sorted(seen))

    print()
    if fails:
        print("%d UI TESTS FAILED" % len(fails))
        return 1
    print("all ui tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
