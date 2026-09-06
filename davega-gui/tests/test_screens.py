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

GOLDEN = os.path.join(HERE, "golden")
UPDATE = "--update-golden" in sys.argv

# An ESP32 over SPI does not get many of these per frame before the readout
# feels laggy. Kept low deliberately: the number is the design constraint.
BUDGET = {"fill_rectangle": 24, "print": 24, "total": 120}

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
