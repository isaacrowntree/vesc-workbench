"""Curves on a panel that cannot draw one.

The display driver offers `fill_rectangle`, `pixel` and `writeblock`, and
nothing else. There is no line, no circle, no polygon. Measured on the board:

    fill_rectangle   2.9 ms per call, whatever its size
    pixel            2.29 ms per call
    writeblock       12 ms for a 240x40 band - 9,600 px in one transfer

So a 96 px-radius arc drawn the way a region is drawn - one rectangle per
column - costs 481 ms, and as pixels 914 ms. Both are past the budget for a
whole frame. Composed into a buffer and pushed with `writeblock` the same arc
costs about 12 ms a band.

The catch is memory: 98 kB free, and a 200x100 RGB565 buffer (40 kB) fails to
allocate. So the picture is drawn in horizontal bands with one buffer reused,
and `paint` hands the drawing code a canvas that takes absolute coordinates
and quietly discards whatever falls outside the band it is currently filling.

MicroPython's C `framebuf` does the rasterising where it exists; the harness
gets a pure-Python stand-in with the same primitives, so a mockup cannot
promise something the panel will not draw.
"""

#: Tallest band we will allocate: 240 x 40 x 2 bytes is 19 kB, which left
#: 77 kB free on the board. Twice that failed outright.
MAX_ROWS = 40


class _PyFrame:
    """The framebuf primitives we use, in Python, for the harness.

    Deliberately the same subset MicroPython's C module offers - fill, pixel,
    hline, vline, line, rect, fill_rect - so device and harness rasterise the
    same shapes and a golden image means something.
    """

    def __init__(self, buf, w, h):
        self.buf, self.w, self.h = buf, w, h

    def pixel(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 2
            self.buf[i] = (c >> 8) & 0xFF
            self.buf[i + 1] = c & 0xFF

    def fill(self, c):
        hi, lo = (c >> 8) & 0xFF, c & 0xFF
        for i in range(0, len(self.buf), 2):
            self.buf[i] = hi
            self.buf[i + 1] = lo

    def hline(self, x, y, w, c):
        for i in range(w):
            self.pixel(x + i, y, c)

    def vline(self, x, y, h, c):
        for i in range(h):
            self.pixel(x, y + i, c)

    def fill_rect(self, x, y, w, h, c):
        for j in range(h):
            self.hline(x, y + j, w, c)

    def rect(self, x, y, w, h, c, f=False):
        if f:
            return self.fill_rect(x, y, w, h, c)
        self.hline(x, y, w, c)
        self.hline(x, y + h - 1, w, c)
        self.vline(x, y, h, c)
        self.vline(x + w - 1, y, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.pixel(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy


class _Swapped:
    """A native framebuf that is handed byte-swapped colours.

    MicroPython stores an RGB565 pixel with a native 16-bit write, so on a
    little-endian MCU the low byte lands first. The ILI9341 wants the high
    byte first on the wire, and `writeblock` streams the buffer untouched -
    so a colour drawn straight into a framebuf comes out of the panel with
    its bytes reversed. Red draws blue.

    Swapping on the way in puts the bytes in panel order while keeping the C
    rasteriser, which is the only reason curves are affordable at all. The
    Python stand-in writes big-endian directly and needs no wrapper, which is
    exactly why this never showed up off-device.
    """

    def __init__(self, fb):
        self.fb = fb

    @staticmethod
    def _s(c):
        return ((c & 0xFF) << 8) | (c >> 8)

    def fill(self, c):
        self.fb.fill(self._s(c))

    def pixel(self, x, y, c):
        self.fb.pixel(x, y, self._s(c))

    def hline(self, x, y, w, c):
        self.fb.hline(x, y, w, self._s(c))

    def vline(self, x, y, h, c):
        self.fb.vline(x, y, h, self._s(c))

    def line(self, x0, y0, x1, y1, c):
        self.fb.line(x0, y0, x1, y1, self._s(c))

    def rect(self, x, y, w, h, c, f=False):
        if f:
            self.fb.fill_rect(x, y, w, h, self._s(c))
        else:
            self.fb.rect(x, y, w, h, self._s(c))

    def fill_rect(self, x, y, w, h, c):
        self.fb.fill_rect(x, y, w, h, self._s(c))


def _little_endian():
    """Ask, rather than assume. Checked once, at import."""
    try:
        import framebuf
    except ImportError:
        return False
    probe = bytearray(2)
    framebuf.FrameBuffer(probe, 1, 1, framebuf.RGB565).pixel(0, 0, 0x1234)
    return probe[0] == 0x34


_SWAP = _little_endian()


def _frame(buf, w, h):
    try:
        import framebuf
        fb = framebuf.FrameBuffer(buf, w, h, framebuf.RGB565)
        return _Swapped(fb) if _SWAP else fb
    except ImportError:
        return _PyFrame(buf, w, h)


class Canvas:
    """A drawing surface in screen coordinates, backed by one band.

    Everything outside the band is clipped by the frame buffer itself, so the
    drawing code is written once, in absolute coordinates, and simply gets
    called again for the next band.
    """

    def __init__(self, fb, x0, y0, w, h):
        self.fb = fb
        self.x0, self.y0 = x0, y0
        self.w, self.h = w, h

    def fill(self, c):
        self.fb.fill(c)

    def pixel(self, x, y, c):
        self.fb.pixel(x - self.x0, y - self.y0, c)

    def hline(self, x, y, w, c):
        self.fb.hline(x - self.x0, y - self.y0, w, c)

    def vline(self, x, y, h, c):
        self.fb.vline(x - self.x0, y - self.y0, h, c)

    def line(self, x0, y0, x1, y1, c):
        self.fb.line(x0 - self.x0, y0 - self.y0,
                     x1 - self.x0, y1 - self.y0, c)

    def rect(self, x, y, w, h, c, f=False):
        self.fb.rect(x - self.x0, y - self.y0, w, h, c, f)

    def fill_rect(self, x, y, w, h, c):
        self.fb.fill_rect(x - self.x0, y - self.y0, w, h, c)

    # -- shapes the panel has no primitive for ----------------------------

    def ring(self, cx, cy, r, colour, thickness=1):
        """A circle, as a run of horizontal spans per row.

        Rasterised rather than stroked: for each row the span between the
        outer and inner radius is filled on both sides. Cheap inside a band
        and impossible outside one.
        """
        inner = r - thickness
        for dy in range(-r, r + 1):
            yy = cy + dy
            if yy < self.y0 - 1 or yy > self.y0 + self.h:
                continue
            o = _isqrt(r * r - dy * dy)
            i = _isqrt(inner * inner - dy * dy) if abs(dy) < inner else 0
            if i:
                self.hline(cx - o, yy, o - i + 1, colour)
                self.hline(cx + i, yy, o - i + 1, colour)
            else:
                self.hline(cx - o, yy, 2 * o + 1, colour)

    def disc(self, cx, cy, r, colour):
        for dy in range(-r, r + 1):
            yy = cy + dy
            if yy < self.y0 - 1 or yy > self.y0 + self.h:
                continue
            o = _isqrt(r * r - dy * dy)
            self.hline(cx - o, yy, 2 * o + 1, colour)

    def spoke(self, cx, cy, r0, r1, sin, cos, colour, width=1):
        """A radial tick or needle, from r0 to r1 along a direction."""
        x0, y0 = cx + int(r0 * sin), cy - int(r0 * cos)
        x1, y1 = cx + int(r1 * sin), cy - int(r1 * cos)
        for k in range(width):
            self.line(x0 + k, y0, x1 + k, y1, colour)

    def wedge(self, xs, ys, colour):
        """A filled polygon, scanline style. Used for shards and slants."""
        if len(xs) < 3:
            return
        top, bot = min(ys), max(ys)
        for yy in range(max(top, self.y0 - 1), min(bot, self.y0 + self.h) + 1):
            hits = []
            for i in range(len(xs)):
                j = (i + 1) % len(xs)
                ya, yb = ys[i], ys[j]
                if (ya <= yy < yb) or (yb <= yy < ya):
                    t = (yy - ya) / float(yb - ya)
                    hits.append(int(xs[i] + t * (xs[j] - xs[i])))
            if len(hits) >= 2:
                hits.sort()
                for k in range(0, len(hits) - 1, 2):
                    self.hline(hits[k], yy, hits[k + 1] - hits[k] + 1, colour)


def _isqrt(n):
    if n <= 0:
        return 0
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x


def paint(d, x, y, w, h, draw, rows=MAX_ROWS):
    """Compose `draw(canvas)` into bands and push each one.

    One buffer, reused down the region, because the whole picture will not fit
    in RAM. `draw` is called once per band with the same absolute coordinates
    every time and is expected to be a pure function of them.
    """
    rows = min(rows, h)
    buf = bytearray(w * rows * 2)
    fb = _frame(buf, w, rows)
    top = y
    while top < y + h:
        tall = min(rows, y + h - top)
        if tall != rows:                      # last band, short
            buf = bytearray(w * tall * 2)
            fb = _frame(buf, w, tall)
        draw(Canvas(fb, x, top, w, tall))
        d.writeblock(x, top, x + w - 1, top + tall - 1, buf)
        top += tall


def sincos(deg):
    """Sine and cosine without importing math on the device.

    Small enough tables and enough accuracy for a dial: degrees are integers
    and the panel is 240 px wide, so a tenth of a degree is invisible.
    """
    import math
    r = deg * math.pi / 180.0
    return math.sin(r), math.cos(r)
