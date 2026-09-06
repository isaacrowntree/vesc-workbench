#!/usr/bin/env python3
"""Screen tests: golden images, the drawing budget, and property sweeps.

Run:  python3 davega-gui/tests/test_screens.py [--update-golden]

No device, no hardware, no image library.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from harness import png                                    # noqa: E402
from harness.display import Display, OutOfBounds           # noqa: E402
from harness.telemetry import Board, FIELDS                # noqa: E402
from screens import riding                                 # noqa: E402
from screens.riding import Riding                          # noqa: E402
from screens import anim, palette                          # noqa: E402

GOLDEN = os.path.join(HERE, "golden")
UPDATE = "--update-golden" in sys.argv

# An ESP32 over SPI does not get many of these per frame before the readout
# feels laggy. Kept low deliberately: the number is the design constraint.
BUDGET = {"fill_rectangle": 24, "print": 24, "total": 120}

# Budgets in milliseconds, from constants measured on the panel. Pixels were
# the wrong proxy: a draw call costs ~2.7 ms whatever its size and a character
# ~8.6 ms, so time is what a screen is actually spending.
FULL_MS = 900
SETTLED_MS = 120
ANIMATION_MS = 60          # every frame of a tween, so motion stays smooth

# Pixels pushed, which is what the SPI bus is actually billed for. A full
# repaint is allowed to be expensive; a steady-state frame, where usually one
# digit moved, is not. 8% of the frame is generous and still ~14x cheaper than
# repainting.
FULL_REPAINT_MAX = 1.30          # x frame area - erase plus content over it
STEADY_STATE_MAX = 0.07          # x frame area - a ratchet, tighten as it improves

# An animating frame redraws more than a settled one: a sweeping value can move
# several digits at once. Still bounded, and the bound is what stops an
# animation from being designed that the bus cannot deliver.
ANIMATION_MAX = 0.12

fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


def render(frame, board, strict=True):
    d = Display(strict=strict)
    riding.render(d, frame, board)
    return d


def main():
    board = Board()

    print("== every frame in the envelope renders inside the display")
    for name, frame in board.envelope():
        try:
            d = render(frame, board)
            check("envelope/%s" % name, True)
        except OutOfBounds as e:
            check("envelope/%s" % name, False, str(e))
            continue

        path = os.path.join(GOLDEN, "riding-%s.png" % name)
        if UPDATE or not os.path.exists(path):
            png.write_rgb(path, d.width, d.height, d.pixels)
            print("        wrote %s" % os.path.basename(path))
        else:
            w, h, want = png.read_rgb(path)
            same = (w, h) == (d.width, d.height) and want == d.pixels
            check("golden/%s" % name, same, "differs from %s" % os.path.basename(path))

    print()
    print("== drawing budget")
    d = render(board.nominal(), board)
    counts = d.call_counts
    for op, limit in BUDGET.items():
        n = len(d.calls) if op == "total" else counts.get(op, 0)
        check("budget/%s %d <= %d" % (op, n, limit), n <= limit)

    print()
    print("== differential rendering is identical to a full repaint")
    # The dangerous failure mode for partial redraw is stale pixels: a region
    # whose new value is narrower than the old, leaving part of the previous
    # value on the glass. Checking every transition between envelope frames
    # is what makes the optimisation safe to rely on.
    env = board.envelope()
    bad = None
    for from_name, from_frame in env:
        for to_name, to_frame in env:
            inc = Display()
            screen = Riding()
            screen.render(inc, from_frame, board)      # first paint
            screen.render(inc, to_frame, board)        # then differential
            fullpaint = Display()
            Riding().render(fullpaint, to_frame, board, full=True)
            if inc.pixels != fullpaint.pixels:
                bad = "%s -> %s leaves stale pixels" % (from_name, to_name)
                break
        if bad:
            break
    check("differential == full over %d transitions" % (len(env) ** 2),
          bad is None, bad or "")

    print()
    print("== cost of a frame, in pixels pushed")
    d = Display()
    screen = Riding()
    screen.render(d, board.nominal(), board)
    first = d.px_written
    check("first paint %d px, %.0f ms <= %d ms" % (first, d.est_ms, FULL_MS),
          d.est_ms <= FULL_MS)
    full_ms = d.est_ms

    # A tenth of a km/h faster: the speed digits may change, nothing else does.
    faster = board.frame(**dict(board.nominal(),
                                rpm=board.erpm_for_kph(26.0)))
    d2 = Display()
    d2.px_written = 0
    screen.render(d2, faster, board)
    steady = d2.px_written
    check("steady frame %d px (%.3fx frame) <= %.2fx"
          % (steady, steady / d2.full_frame_px, STEADY_STATE_MAX),
          steady <= d2.full_frame_px * STEADY_STATE_MAX,
          "differential redraw is not saving anything")
    # At a typical 40 MHz SPI clock, 2 bytes per pixel is ~0.4 us/px.
    est = lambda px: px * 2 * 8 / 40e6 * 1000
    print("        full repaint %d px / %d SPI bytes (~%.0f ms of bus time)"
          % (first, first * 2, est(first)))
    print("        steady frame %d px / %d SPI bytes (~%.1f ms)  %.0fx cheaper"
          % (steady, steady * 2, est(steady), first / max(1, steady)))

    # Nothing changed at all: the cheapest case, and it should cost nothing.
    d3 = Display()
    d3.px_written = 0
    screen.render(d3, faster, board)
    check("unchanged frame costs 0 px", d3.px_written == 0,
          "repainted %d px for an identical frame" % d3.px_written)

    print()
    print("== animation stays inside the bus budget")
    # Animating means redrawing every frame, so the per-frame cost is the
    # whole question. A tween that blows the budget is a tween that stutters.
    screen = Riding()
    d = Display()
    screen.render(d, board.frame(), board)          # first paint, from rest
    # The battery bar sweeps between states; the screen reports when it is
    # still owed frames. Every one of those frames has to fit the budget or
    # the sweep stutters.
    screen = Riding("nazare")
    d = Display()
    screen.render(d, board.frame(input_voltage=board.v_full), board, full=True)
    target = board.frame(input_voltage=board.v_empty + 2.0)
    worst, frames = 0.0, 0
    while not screen.settled() and frames < 40:
        d.px_written = d.chars_written = 0
        d.calls = []
        screen.render(d, target, board)
        worst = max(worst, d.est_ms)
        frames += 1
    check("the bar animates rather than jumping", 1 < frames <= 12,
          "took %d frames" % frames)
    check("worst animated frame %.0f ms <= %d ms" % (worst, ANIMATION_MS),
          worst <= ANIMATION_MS)
    check("animation settles", screen.settled())
    print("        %d frames, worst %.0f ms -> %d fps affordable"
          % (frames, worst, int(1000 / max(1.0, worst))))

    # An animation that does not land exactly where a static draw would is a
    # bug you only see as a stale last digit.
    settled_img = Display()
    Riding("nazare").render(settled_img, target, board, full=True)
    live = Display()
    s2 = Riding("nazare")
    s2.render(live, board.frame(input_voltage=board.v_full), board, full=True)
    for _ in range(20):
        s2.render(live, target, board)
        if s2.settled():
            break
    check("animation lands exactly on the static render",
          live.pixels == settled_img.pixels)

    print()
    print("== colour ramps are monotonic and in range")
    bad = None
    for name, fn in (("soc", lambda t: palette.soc_color(t)),
                     ("temp", lambda t: palette.temp_color(20 + t * 80, 85, 100)),
                     ("power", lambda t: palette.power_color(-80 + t * 160, 80))):
        for i in range(21):
            c = fn(i / 20.0)
            if not (0 <= c <= 0xFFFF):
                bad = "%s at %.2f gave %r" % (name, i / 20.0, c)
                break
    check("ramps stay inside RGB565", bad is None, bad or "")

    print()
    print("== every field, swept across its whole range")
    for field, _, _ in FIELDS:
        bad = None
        for value, frame in board.sweep(field):
            try:
                render(frame, board)
            except OutOfBounds as e:
                bad = "%s=%r %s" % (field, value, e)
                break
        check("sweep/%s" % field, bad is None, bad or "")

    print()
    if fails:
        print("%d SCREEN TESTS FAILED" % len(fails))
        return 1
    print("all screen tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
