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

from harness.display import Display, glyph_size, OutOfBounds                  # noqa: E402
from harness.telemetry import Board                               # noqa: E402
from gui.riding import Riding                                 # noqa: E402
from gui.panels import (RangeScreen, OverviewScreen,          # noqa: E402
                            SessionScreen, LifetimeScreen)
from gui.app import (App, Menu, MenuItem, UP, DOWN, ENTER,     # noqa: E402
                         HOLD, SWEEP, SCREEN, MENU)
from gui.themes import THEMES                                 # noqa: E402
from gui.startup import Splash, play as play_sweep            # noqa: E402
from gui import base                                          # noqa: E402

SCREENS = (("riding", Riding), ("range", RangeScreen),
           ("overview", OverviewScreen), ("session", SessionScreen),
           ("lifetime", LifetimeScreen))

# The riding screen is nine arrangements, not one: the layout comes from the
# theme, so a check that only ever looks at Nazare is checking a tenth of what
# ships. Every layout gets the same overlap, grid and footer checks.
LAYOUT_THEMES = tuple(sorted(THEMES))

#: Every screen in every theme, day and night. The riding screen is nine
#: arrangements rather than one, and the other four are shared - but all of
#: them take their colours from the theme, so a check that only ever looks at
#: Nazare at night is checking a twentieth of what ships.
EVERY = tuple(("%s/%s%s" % (n, k, "" if dark else "@light"), c,
               k if dark else k + "@light")
              for k in LAYOUT_THEMES
              for n, c in SCREENS
              for dark in (True, False))

# Device-measured constants (see harness/display.py). A settled frame has to
# stay usable against 5 Hz telemetry; a full repaint is allowed to be slow
# because it happens once per screen change.
# A moving frame on the riding screen redraws the speed, the rail and the flow
# meter together - which is the common case while actually riding, not an
# outlier. 150 ms is ~7 fps against 5 Hz telemetry.
MAX_SETTLED_MS = 150
MAX_FULL_MS = 950

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
    print("== a colour change repaints even when the text does not move")
    # "FET  95" going amber to red is the change that matters most, and it
    # does not alter a single character.
    hot = b.frame(temp_fet_filtered=b.temp_derate_start + 10)
    cool = b.frame(temp_fet_filtered=25.0)
    for name, cls in SCREENS:
        warm = Display()
        s1 = cls("nazare")
        settle(s1, warm, cool, b)
        settle(s1, warm, hot, b)
        direct = Display()
        cls("nazare").render(direct, hot, b, full=True)
        check("colour/%s" % name, warm.pixels == direct.pixels)

    print()
    print("== declared regions do not overlap")
    # Overlapping regions are invisible on a full repaint and corrupt the
    # differential path, because repainting one clears part of another.
    for name, cls, theme in EVERY:
        screen = cls(theme)
        regions = screen.regions()
        clash = None
        for i, a in enumerate(regions):
            for c in regions[i + 1:]:
                ax, ay, aw, ah = a[1], a[2], a[3], a[4]
                cx, cy, cw, ch = c[1], c[2], c[3], c[4]
                allowed = getattr(screen, "overlap_exceptions", set())
                if ((a[0], c[0]) in allowed or (c[0], a[0]) in allowed):
                    continue        # declared, and the pair never draw at once
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
    check("boots into the sweep", app.state == SWEEP)
    d0 = Display()
    frames = app.render(d0, b.nominal())
    check("sweep runs then hands over (%d frames)" % frames,
          app.state == SCREEN and frames > 10)
    check("starts on the first screen", app.key == "riding")
    app.press(DOWN)
    check("down moves forward", app.key == "range")
    app.press(UP)
    app.press(UP)
    check("up wraps backwards", app.key == "lifetime")
    app.press(ENTER)
    check("enter opens the menu", app.state == MENU)
    d = Display()
    app.render(d, b.nominal())
    check("menu draws", len(d.calls) > 0)
    app.press(DOWN)
    check("down moves the cursor, not the screen",
          app.menu.cursor == 1 and app.key == "lifetime")
    app.press(ENTER)
    check("enter cycles the value", app.menu.items[1].value == "imperial")
    app.press(HOLD)
    check("hold leaves the menu", app.state == SCREEN)

    skip = App([(n, c) for n, c in SCREENS], b, "nazare")
    skip.tick(Display(), b.nominal())
    skip.press(DOWN)
    check("a press skips the sweep", skip.state == SCREEN)

    # The loop contract: tick() keeps asking for frames only while something
    # is animating, so a caller never has to know which screens animate.
    quiet = App([(n, c) for n, c in SCREENS], b, "nazare", sweep=False)
    dq = Display()
    quiet.render(dq, b.nominal())
    check("a settled screen owes no further frames",
          quiet.tick(dq, b.nominal()) is False)

    d = Display()
    app.render(d, b.nominal())
    check("returning from the menu repaints fully", len(d.calls) > 20)

    app.set_theme("rosso")
    check("theme change drops cached screens", app._live == {})
    d = Display()
    app.render(d, b.nominal())
    check("renders in the new theme", len(d.calls) > 0)

    print()
    print("== the screens are one instrument, not five views")
    names = tuple(n for n, _ in SCREENS)

    # Same header, same place, on every screen.
    headers = []
    for i, (name, cls) in enumerate(SCREENS):
        d = Display()
        cls("nazare", names, i).render(d, b.nominal(), b, full=True)
        rule = [c for c in d.calls if c[0] == "fill_rectangle"
                and c[1].get("y") == base.HEADER_H - 4]
        headers.append(bool(rule))
    check("every screen draws the header rule", all(headers),
          "missing on %s" % [n for (n, _), h in zip(SCREENS, headers) if not h])

    titles = [cls.title for _, cls in SCREENS]
    check("every screen names itself", all(titles), "got %r" % titles)
    check("titles are unique", len(set(titles)) == len(titles))

    # Page dots: present, and the lit one follows the position.
    lit = []
    for i, (name, cls) in enumerate(SCREENS):
        d = Display()
        cls("nazare", names, i).render(d, b.nominal(), b, full=True)
        dots = [c[1] for c in d.calls if c[0] == "fill_rectangle"
                and c[1].get("h") == 4 and c[1].get("w") == 4]
        accent = THEMES["nazare"].accent
        on = [j for j, dd in enumerate(dots) if dd.get("color") == accent]
        if not dots and not cls("nazare", names, i).shows_page_dots:
            lit.append(True)        # opted out, deliberately and declared
            continue
        lit.append(len(dots) == len(SCREENS) and on == [i])
    check("page dots show which of the set you are on", all(lit),
          "wrong on %s" % [n for (n, _), ok in zip(SCREENS, lit) if not ok])

    # Everything sits on the grid.
    off = []
    xs = set(base.col_x(i) for i in range(base.COLS))
    for name, cls, theme in EVERY:
        screen = cls(theme, names, 0)
        for r in screen.regions():
            if r[0].startswith("hdr_"):
                continue            # the status strip has its own anchor
            if r[1] == 0 and r[3] == base.W:
                continue            # full-bleed banners are deliberate
            if r[0] in getattr(screen, "grid_exceptions", {}):
                continue            # declared, with a reason, on the layout
            if r[1] not in xs:
                off.append("%s/%s x=%d" % (name, r[0], r[1]))
    check("every region starts on a grid column", not off,
          "off-grid: " + ", ".join(off[:4]))

    # One type scale, used the same way.
    scales = set()
    for name, cls in SCREENS:
        d = Display()
        cls("nazare", names, 0).render(d, b.nominal(), b, full=True)
        for call, kw in d.calls:
            if call == "print":
                scales.add(kw.get("scale", 1))
    allowed = {base.LABEL, base.VALUE, base.PRIMARY, base.HERO, base.HERO_XL}
    check("only scales from the type scale are used (%s)" % sorted(scales),
          scales <= allowed, "stray: %s" % sorted(scales - allowed))

    print()
    print("== the power-on sweep")
    for key in sorted(THEMES):
        sp = Splash(key)
        d = Display()
        worst = [0.0]
        total = [0.0]

        def watch(_n, d=d, worst=worst, total=total):
            worst[0] = max(worst[0], d.est_ms)
            total[0] += d.est_ms
            d.px_written = d.chars_written = 0
            d.calls = []

        try:
            n = play_sweep(sp, d, b, b.nominal(), on_frame=watch)
        except OutOfBounds as e:
            check("sweep/%s" % key, False, str(e))
            continue
        avg = total[0] / max(1, n)
        # What matters is that it is a real sweep and that every frame is
        # cheap: the wall-clock duration is set by how fast the caller renders,
        # not by the drawing cost. Painting deltas instead of clearing took a
        # frame from 34 ms to 13 - which is the black flash gone.
        ok = sp.settled() and n >= 40 and avg <= 40
        check("sweep/%-11s %d frames, avg %.0f ms" % (key, n, avg), ok,
              "settled=%s" % sp.settled())

    # A sweep that leaves the dash showing a made-up number is worse than no
    # sweep, so the hand-off has to land on the real frame.
    sp = Splash("nazare")
    d = Display()
    play_sweep(sp, d, b, b.nominal())
    real = Riding("nazare")
    real.render(d, b.nominal(), b, full=True)
    want = Display()
    Riding("nazare").render(want, b.nominal(), b, full=True)
    check("hands over to the real screen cleanly", d.pixels == want.pixels)

    print()
    print("== day and night are a setting, not two builds")
    dayapp = App([(n, c) for n, c in SCREENS], b, "nazare", sweep=False)
    d_night = Display()
    dayapp.render(d_night, b.nominal())
    dayapp.set_light(True)
    check("switching drops cached screens", dayapp._live == {})
    d_day = Display()
    dayapp.render(d_day, b.nominal())
    check("the screen actually changes", d_night.pixels != d_day.pixels)
    check("the light one is lighter",
          sum(d_day.pixels) > sum(d_night.pixels))
    check("every screen follows the setting",
          all(cls("nazare@light").t.light for _, cls in SCREENS))
    dayapp.set_light(False)
    d_back = Display()
    dayapp.render(d_back, b.nominal())
    check("and switches back", d_back.pixels == d_night.pixels)

    print()
    print("== every screen renders in every light variant")
    bad = None
    for name, cls in SCREENS:
        for key in sorted(THEMES):
            try:
                cls(key + "@light").render(Display(), b.nominal(), b, full=True)
            except OutOfBounds as e:
                bad = "%s/%s: %s" % (name, key, e)
                break
        if bad:
            break
    check("all %d screens x %d light themes" % (len(SCREENS), len(THEMES)),
          bad is None, bad or "")

    print()
    print("== no value can run off the panel")
    # A column at this digit size holds four characters. Anything longer is
    # drawn past the right edge, which the strict harness catches only if the
    # exact frame that produces it is in the envelope.
    from gui import panels
    long_values = []
    for name, cls in SCREENS:
        if not hasattr(cls, "PAIRS"):
            continue
        for _, frame in env:
            for row in cls.PAIRS:
                for label, spec in row:
                    if spec is None:
                        continue
                    v = spec[1](frame, b)
                    if len(v) > panels.MAX_CHARS:
                        long_values.append("%s/%s=%r" % (name, spec[0], v))
    check("every panel value fits %d characters" % panels.MAX_CHARS,
          not long_values, ", ".join(long_values[:4]))

    print()
    print("== no value can outgrow the box that was drawn for it")
    # A region's width is fixed when the layout is built, from the widest
    # value the designer expected. One digit more does not wrap or clip - it
    # draws off the side of the panel. Ranges and efficiencies are the ones
    # that bite: both are estimates, and both can be large early in a ride
    # before there is enough evidence to be sensible.
    #
    # Rather than reason abouteach region's width, render it and let the
    # display's own bounds check answer.
    silly = dict(b.nominal())
    silly.update({"s_range_km": 1480.0, "s_wh_per_km": 940.0,
                  "s_trip_km": 9999.0, "l_trip_km": 99999.0,
                  "s_max_kph": 999.0, "avg_motor_current": 1234.0,
                  "avg_input_current": 999.0, "input_voltage": 100.0,
                  "temp_fet_filtered": 199.0, "temp_motor_filtered": 199.0,
                  "s_wh_spent": 99999.0, "l_wh_spent": 99999.0})
    over = []
    for name, cls, theme in EVERY:
        try:
            cls(theme, names, 0).render(Display(), silly, b, full=True)
        except OutOfBounds as e:
            over.append("%s: %s" % (name, e))
        except Exception as e:                       # noqa: BLE001
            over.append("%s raised %r" % (name, e))
    check("absurd values stay inside the panel", not over,
          "; ".join(over[:3]))

    print("== chrome labels stay out of the regions that repaint")
    # A label is furniture: it is drawn once and never again. A region is
    # repainted whenever its value changes, and the panel's font is opaque -
    # so a label inside a region's box is erased the first time that value
    # moves and never comes back. It looks right on the bench, at a
    # standstill, and wrong thirty seconds into a ride.
    for name, cls, theme in EVERY:
        screen = cls(theme, names, 0)
        d = Display()
        d.set_color(screen.t.ink, screen.t.ground)
        d.erase()
        screen.chrome(d)
        labels = []
        for call, kw in d.calls:
            if call != "print":
                continue
            lx, ly = kw["pos"]
            cw, lh = base.glyph_size(kw["text"], kw.get("scale", 1)) \
                if hasattr(base, "glyph_size") else glyph_size(
                    kw["text"], kw.get("scale", 1))
            labels.append((lx, ly, len(kw["text"]) * cw, lh, kw["text"]))
        clash = []
        for lx, ly, lw, lh, txt in labels:
            for r in screen.regions():
                if r[0].startswith("hdr_"):
                    continue
                rx, ry, rw, rh = r[1], r[2], r[3], r[4]
                if (lx < rx + rw and rx < lx + lw
                        and ly < ry + rh and ry < ly + lh):
                    clash.append("%s over %s" % (txt.strip(), r[0]))
        check("labels/%-16s %2d clear" % (name, len(labels)), not clash,
              "; ".join(clash[:3]))

    print()
    print("== nothing paints over the page dots")
    # The riding screen's fault banner sat exactly on them, so its background
    # fill erased the one marker telling you where you are in the set - and
    # only on that screen, which is how it went unnoticed.
    dots_y = base.H - base.FOOTER_H + 4
    for name, cls, theme in EVERY:
        screen = cls(theme, names, 0)
        if not screen.shows_page_dots:
            continue
        covering = [r[0] for r in screen.regions()
                    if not r[0].startswith("hdr_")
                    and r[2] < dots_y + 4 and dots_y < r[2] + r[4]]
        check("dots/%-9s clear" % name, not covering, "covered by %s" % covering)

    print()
    print("== the screens use the whole panel")
    # A 2.8 inch display is small enough without leaving a third of it black.
    # Every screen's lowest drawn region must reach the bottom band.
    for name, cls in SCREENS:
        regions = [r for r in cls("nazare", names, 0).regions()
                   if not r[0].startswith("hdr_")]
        lowest = max(r[2] + r[4] for r in regions)
        rightmost = max(r[1] + r[3] for r in regions)
        check("fills/%-9s lowest %d, widest %d" % (name, lowest, rightmost),
              lowest >= 280 and rightmost >= 210)

    print()
    print("== every screen is reachable")
    app2 = App([(n, c) for n, c in SCREENS], b, "nazare", sweep=False)
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
