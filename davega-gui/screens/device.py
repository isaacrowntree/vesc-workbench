"""Port layer: our screen API on top of the DAVEGA's real display.

The harness `Display` and the device's `frozen.display.DISPLAY` are close but
not identical - the device's `print` takes no scale, and large digits go
through `frozen.display_util.draw_number` against a 3x5 font. Every one of
those differences lives here, so screens stay portable and the harness stays
honest about what it is standing in for.
"""


class DeviceDisplay:
    def __init__(self, raw, draw_number=None, number_dimensions=None, font=None):
        self.raw = raw
        self.width = raw.width
        self.height = raw.height
        self._draw_number = draw_number
        self._dims = number_dimensions
        self._font = font
        self._fg = 0xFFFF
        self._bg = 0x0000

    # -- the API screens are written against -------------------------------

    def erase(self):
        self.raw.erase()

    def set_color(self, fg, bg=None):
        self._fg = fg
        if bg is not None:
            self._bg = bg
            self.raw.set_color(fg, bg)
        else:
            self.raw.set_color(fg)

    def set_font(self, font):
        self.raw.set_font(font)

    def set_pos(self, x, y):
        self._pos = (x, y)
        self.raw.set_pos(x, y)

    def fill_rectangle(self, x, y, w, h, color=None):
        if color is None:
            self.raw.fill_rectangle(x, y, w, h)
        else:
            self.raw.fill_rectangle(x, y, w, h, color)

    def pixel(self, x, y, color=None):
        self.fill_rectangle(x, y, 1, 1, color)

    def print(self, text, scale=1, numeric=None):
        text = str(text)
        if numeric is None:
            numeric = _numeric(text)
        # The device's own big-number renderer when we have it and the text is
        # numeric; otherwise the font-sized path, which always works.
        # draw_number(text, font, x, y, scale, color) - the device's own
        # scaled renderer, against a 3x5 font. Native, so far cheaper than
        # any glyph loop we could write in Python.
        if scale > 1 and numeric and self._draw_number and self._font:
            x, y = getattr(self, "_pos", (0, 0))
            try:
                self._draw_number(text, self._font, x, y, scale, self._fg)
                return
            except Exception:
                pass          # fall through rather than lose the frame
        self.raw.print(text)

    def chars(self, text, scale=1, numeric=None):
        self.print(text, scale, numeric)

    def next_line(self):
        pass

    def reset_scroll(self):
        self.raw.reset_scroll()


def _numeric(t):
    for c in t:
        if c not in "0123456789.- ":
            return False
    return True


def attach():
    """Wrap the live display. Import-time work is kept out of module scope so
    this file can be read on a host that has no frozen modules."""
    import frozen.display as fd
    try:
        import frozen.display_util as du
        return DeviceDisplay(fd.DISPLAY, getattr(du, "draw_number", None),
                             getattr(du, "number_dimensions", None),
                             getattr(du, "FONT_3X5", None))
    except ImportError:
        return DeviceDisplay(fd.DISPLAY)
