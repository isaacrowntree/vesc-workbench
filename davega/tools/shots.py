#!/usr/bin/env python3
"""Render the riding screen, per theme, to PNGs for the README and the blog.

Not mockups: these run the real screen code through the real harness display
and write out the pixels it produced. A picture that disagrees with the panel
is therefore impossible, which is the whole point of having a harness at all.

    python3 davega/tools/shots.py [outdir] [scale]
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(ROOT))

from harness import png                                    # noqa: E402
from harness.display import Display                        # noqa: E402
from harness.telemetry import Board                        # noqa: E402
from gui.riding import Riding                          # noqa: E402
from gui.themes import THEMES                          # noqa: E402

W, H = 240, 320


def frame(board):
    """One plausible moment, the same for every theme so they compare.

    Mid-ride at 25 km/h under light drive: fast enough that the speed rail and
    the arcs have something to show, gentle enough that nothing is in a
    warning state. A screenshot of a board at a standstill shows none of the
    behaviour that the layouts differ in.
    """
    f = board.frame(**dict(board.nominal(),
                           rpm=board.erpm_for_kph(25.0),
                           avg_motor_current=18.0,
                           avg_input_current=10.0,
                           input_voltage=45.8,
                           temp_fet_filtered=42.0,
                           temp_motor_filtered=48.0))
    f["s_range_km"] = 21.0
    f["s_wh_per_km"] = 17.3
    f["s_trip_km"] = 12.4
    return f


def shot(theme, board, f):
    d = Display()
    s = Riding(theme)
    s.render(d, f, board, full=True)
    for _ in range(30):                 # let the tweens land
        s.render(d, f, board)
        if s.settled():
            break
    return d


def upscale(pixels, w, h, k):
    """Nearest-neighbour, so a pixel stays a pixel. Smoothing a 240x320 panel
    into something soft would flatter it and misrepresent it."""
    out = bytearray(w * k * h * k * 3)
    for y in range(h):
        row = bytearray()
        for x in range(w):
            o = (y * w + x) * 3
            row += pixels[o:o + 3] * k
        for j in range(k):
            base = ((y * k + j) * w * k) * 3
            out[base:base + len(row)] = row
    return out


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "docs/img"
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    board = Board()
    f = frame(board)

    shots = []
    for key in sorted(THEMES):
        d = shot(key, board, f)
        px = upscale(d.pixels, W, H, scale) if scale > 1 else d.pixels
        path = os.path.join(outdir, "riding-%s.png" % key)
        png.write_rgb(path, W * scale, H * scale, px)
        shots.append((key, d))
        print("%-11s %-9s %s  (%.0f ms first paint)"
              % (key, Riding(key).lay.__module__.split(".")[-1], path,
                 d.est_ms))

    # A contact sheet, for the top of the README and the post: all ten at
    # once, which is the only way the layouts read as a set.
    gap, cols = 10, 5
    rows = (len(shots) + cols - 1) // cols
    tw = cols * W + (cols + 1) * gap
    th = rows * H + (rows + 1) * gap
    sheet = bytearray(b"\x0b\x0d\x10" * (tw * th))
    for i, (_, d) in enumerate(shots):
        cx = gap + (i % cols) * (W + gap)
        cy = gap + (i // cols) * (H + gap)
        for y in range(H):
            o = ((cy + y) * tw + cx) * 3
            src = (y * W) * 3
            sheet[o:o + W * 3] = d.pixels[src:src + W * 3]
    if scale > 1:
        sheet = upscale(sheet, tw, th, scale)
    path = os.path.join(outdir, "riding-all.png")
    png.write_rgb(path, tw * scale, th * scale, sheet)
    print("sheet %s (%dx%d)" % (path, tw * scale, th * scale))


if __name__ == "__main__":
    main()
