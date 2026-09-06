"""A host-side stand-in for the DAVEGA's ILI9341.

Same method names and semantics as `frozen.display.DISPLAY` on the device, so a
screen written against this runs unchanged there. Every call is recorded, and
the result rasterises to RGB for golden-image comparison.

Two things it measures that the device cannot easily tell you:

  * the draw-call budget - an ESP32 pushing 400 fill_rectangles per frame will
    be slow no matter how the screen looks, and that is knowable here
  * out-of-bounds drawing - anything outside 240x320, or a string wider than
    the space it was given, is a test failure rather than a visual surprise
"""

WIDTH, HEIGHT = 240, 320

# Two different glyph paths on the device, with different metrics:
#   scale 1        frozen.fonts.glcdfont, an 8x8 cell
#   scale > 1      display_util.draw_number against FONT_3X5, which measures
#                  6 x 10 per character at scale 2 - narrower and taller than
#                  the 8x8 cell, so modelling both matters for layout fidelity.
CHAR_W, CHAR_H = 8, 8
NUM_W, NUM_H = 3, 5
NUM_GAP = 1


def glyph_size(text, scale, numeric=None):
    """Cell size the device will use. `numeric` overrides the guess, because
    the choice belongs to the whole string: pulling one digit out of "257 Wh"
    to repaint it must not switch that character to the numeric font."""
    if numeric is None:
        numeric = _numeric(text)
    if scale > 1 and numeric:
        return (NUM_W + NUM_GAP) * scale, NUM_H * scale
    return CHAR_W * scale, CHAR_H * scale


def _numeric(t):
    for c in t:
        if c not in "0123456789.- ":
            return False
    return True


def rgb565_to_rgb(c):
    return (((c >> 11) & 0x1F) * 255 // 31,
            ((c >> 5) & 0x3F) * 255 // 63,
            (c & 0x1F) * 255 // 31)


def rgb_to_rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


class OutOfBounds(AssertionError):
    pass


class Display:
    def __init__(self, width=WIDTH, height=HEIGHT, strict=True):
        self.width = width
        self.height = height
        self.strict = strict
        self.is_horizontal = False
        self.reset_state()

    # -- harness surface ---------------------------------------------------

    def reset_state(self):
        self.pixels = bytearray(self.width * self.height * 3)
        self.calls = []
        # Pixels touched. Kept because it is the honest measure of SPI
        # traffic - but NOT the thing that decides whether a screen feels
        # fast. See COST below.
        self.px_written = 0
        self.chars_written = 0
        self.color = 0xFFFF
        self.bg = 0x0000
        self.pos = (0, 0)
        self.font = None

    @property
    def call_counts(self):
        counts = {}
        for name, _ in self.calls:
            counts[name] = counts.get(name, 0) + 1
        return counts

    def _record(self, name, **kw):
        self.calls.append((name, kw))

    def _bounds(self, x, y, w, h, what):
        if not self.strict:
            return
        if x < 0 or y < 0 or x + w > self.width or y + h > self.height:
            raise OutOfBounds(
                "%s at (%d,%d) size %dx%d leaves the %dx%d frame"
                % (what, x, y, w, h, self.width, self.height))

    # Measured on a DAVEGA X (ESP32, MicroPython 1.14), 100 calls each:
    #
    #   fill_rectangle   4x4      2.86 ms
    #   fill_rectangle  40x40     4.74 ms
    #   fill_rectangle 240x40    12.60 ms
    #   set_pos + print 3 chars  25.88 ms   <- 8.6 ms PER CHARACTER
    #   set_color                 0.13 ms
    #
    # So the cost is not pixels. A draw call costs ~2.7 ms of interpreter
    # overhead whatever its size, and drawing a character costs three times
    # that again. Pixels are close to free by comparison (~1 us each).
    #
    # Optimising a screen therefore means drawing fewer CHARACTERS, then
    # making fewer CALLS - and only then worrying about area.
    CALL_MS = 2.70          # per drawing call, any size
    PX_MS = 0.001           # per pixel on top of that
    CHAR_MS = 8.60          # per character drawn

    @property
    def est_ms(self):
        """Estimated frame time on the device, from measured constants."""
        drawing = sum(1 for n, _ in self.calls
                      if n in ("fill_rectangle", "print", "chars", "pixel", "erase"))
        return (drawing * self.CALL_MS
                + self.px_written * self.PX_MS
                + self.chars_written * self.CHAR_MS)

    @property
    def spi_bytes(self):
        """2 bytes per pixel, plus ~11 bytes of column/page/write commands for
        each addressed window."""
        windows = sum(1 for n, _ in self.calls
                      if n in ("fill_rectangle", "print", "chars", "pixel", "erase"))
        return self.px_written * 2 + windows * 11

    @property
    def full_frame_px(self):
        return self.width * self.height

    def _blit(self, x, y, w, h, color):
        r, g, b = rgb565_to_rgb(color)
        self.px_written += max(0, min(self.width, x + w) - max(0, x)) * \
                           max(0, min(self.height, y + h) - max(0, y))
        for yy in range(max(0, y), min(self.height, y + h)):
            base = (yy * self.width + max(0, x)) * 3
            for i in range(max(0, min(self.width, x + w) - max(0, x))):
                o = base + i * 3
                self.pixels[o] = r
                self.pixels[o + 1] = g
                self.pixels[o + 2] = b

    # -- the device's API --------------------------------------------------

    def erase(self):
        self._record("erase")
        self._blit(0, 0, self.width, self.height, self.bg)

    def set_color(self, fg, bg=None):
        self._record("set_color", fg=fg, bg=bg)
        self.color = fg
        if bg is not None:
            self.bg = bg

    def set_font(self, font):
        self._record("set_font", font=getattr(font, "__name__", str(font)))
        self.font = font

    def set_pos(self, x, y):
        self._record("set_pos", x=x, y=y)
        self.pos = (x, y)

    def fill_rectangle(self, x, y, w, h, color=None):
        self._record("fill_rectangle", x=x, y=y, w=w, h=h, color=color)
        self._bounds(x, y, w, h, "fill_rectangle")
        self._blit(x, y, w, h, self.color if color is None else color)

    def pixel(self, x, y, color=None):
        self._record("pixel", x=x, y=y, color=color)
        self._bounds(x, y, 1, 1, "pixel")
        self._blit(x, y, 1, 1, self.color if color is None else color)

    def print(self, text, scale=1, numeric=None):
        """Draw at the current position. Glyphs are solid blocks: the harness
        tests layout and overflow, not letterforms."""
        text = str(text)
        self._record("print", text=text, scale=scale, pos=self.pos)
        x, y = self.pos
        cw, h = glyph_size(text, scale, numeric)
        w = len(text) * cw
        self._bounds(x, y, w, h, "print(%r)" % text[:24])
        self.chars_written += sum(1 for c in text if c != " ")
        for i, ch in enumerate(text):
            if ch != " ":
                self._blit(x + i * cw, y, cw - scale, h, self.color)
        self.pos = (x + w, y)

    def chars(self, text, scale=1, numeric=None):
        self.print(text, scale, numeric)

    def next_line(self, *a, **kw):
        self._record("next_line")
        self.pos = (0, self.pos[1] + CHAR_H)

    def reset_scroll(self):
        self._record("reset_scroll")

    def scrdef(self, *a):
        self._record("scrdef", args=a)

    def scrset(self, *a):
        self._record("scrset", args=a)


DISPLAY = Display()
