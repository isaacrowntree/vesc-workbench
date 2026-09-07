"""The device, faked, for MicroPython running off the board.

Everything the dashboard touches that is hardware: the panel, the three
buttons, the UART to the ESC, and the flash it keeps settings on. The
interpreter is real - that is the whole point of this suite - so these fakes
are deliberately thin, and they record rather than simulate.

They install themselves into `sys.modules` under the names the firmware uses,
so `gui` imports exactly what it imports on the board and has no idea it is
being tested.
"""
import sys


# -- the panel -----------------------------------------------------------

class Display:
    """Records draw calls and keeps a real framebuffer.

    Pixels are tracked because that is what proves a screen drew something
    where it said it would. Calls are counted because on this hardware they
    are the cost - 2.9 ms each, whatever their size.
    """

    #: The log is capped. A soak test runs hundreds of frames, and a recorder
    #: that grows without limit runs the interpreter out of memory and then
    #: reports it as though the dashboard had leaked.
    MAX_CALLS = 1500

    def __init__(self, width=240, height=320):
        self.width = width
        self.height = height
        self.calls = []
        self.n_calls = 0
        self.px = bytearray(width * height * 2)
        self.fg = 0xFFFF
        self.bg = 0x0000
        self.pos = (0, 0)
        self.font = None

    # what the driver offers, and nothing else
    def _log(self, *call):
        self.n_calls += 1
        if len(self.calls) < self.MAX_CALLS:
            self.calls.append(call)

    def erase(self):
        self._log("erase")
        self._fill(0, 0, self.width, self.height, self.bg)

    def set_color(self, fg, bg=None):
        self.fg = fg
        if bg is not None:
            self.bg = bg

    def set_font(self, f):
        self.font = f

    def set_pos(self, x, y):
        self.pos = (x, y)

    def fill_rectangle(self, x, y, w, h, colour=None):
        self._log("fill_rectangle", x, y, w, h)
        self._bounds(x, y, w, h, "fill_rectangle")
        self._fill(x, y, w, h, self.fg if colour is None else colour)

    def pixel(self, x, y, colour=None):
        self.fill_rectangle(x, y, 1, 1, colour)

    def writeblock(self, x0, y0, x1, y1, buf):
        w, h = x1 - x0 + 1, y1 - y0 + 1
        self._log("writeblock", x0, y0, w, h)
        self._bounds(x0, y0, w, h, "writeblock")
        if len(buf) != w * h * 2:
            raise ValueError("writeblock buffer is %d bytes, wants %d"
                             % (len(buf), w * h * 2))
        for row in range(h):
            src = row * w * 2
            dst = ((y0 + row) * self.width + x0) * 2
            self.px[dst:dst + w * 2] = buf[src:src + w * 2]

    def print(self, text):
        x, y = self.pos
        text = str(text)
        self._log("print", x, y, text)
        # The panel's font is opaque: the cell is filled with the background
        # whether or not the glyph covers it.
        self._bounds(x, y, 8 * len(text), 8, "print %r" % text)
        self._fill(x, y, 8 * len(text), 8, self.bg)
        for i, ch in enumerate(text):
            if ch != " ":
                self._fill(x + i * 8, y, 7, 8, self.fg)
        self.pos = (x + 8 * len(text), y)

    def chars(self, text, *a):
        self.print(text)

    def next_line(self, *a):
        pass

    def reset_scroll(self):
        pass

    def scrdef(self, *a):
        pass

    def scrset(self, *a):
        pass

    # -- helpers ---------------------------------------------------------

    def _bounds(self, x, y, w, h, what):
        if x < 0 or y < 0 or x + w > self.width or y + h > self.height:
            raise ValueError("%s at (%d,%d) %dx%d leaves the %dx%d panel"
                             % (what, x, y, w, h, self.width, self.height))

    def _fill(self, x, y, w, h, colour):
        hi, lo = (colour >> 8) & 0xFF, colour & 0xFF
        row = bytes((hi, lo)) * w
        for j in range(h):
            o = ((y + j) * self.width + x) * 2
            self.px[o:o + w * 2] = row

    def at(self, x, y):
        o = (y * self.width + x) * 2
        return (self.px[o] << 8) | self.px[o + 1]

    def lit(self):
        """How many pixels are not the ground colour. A screen that drew
        nothing and a screen that drew everything in black look identical
        through the call log alone."""
        n = 0
        for o in range(0, len(self.px), 2):
            if (self.px[o] << 8) | self.px[o + 1]:
                n += 1
        return n

    def reset(self):
        self.calls = []
        self.n_calls = 0


# -- the buttons ---------------------------------------------------------

class Pin:
    """Active low, as on the board: pressed reads 0."""

    def __init__(self, value=1):
        self._v = value

    def value(self):
        return self._v

    def press(self):
        self._v = 0

    def release(self):
        self._v = 1


# -- the ESC -------------------------------------------------------------

class UART:
    """Replays recorded replies.

    `script` is a list of (request_predicate, reply_bytes). The dashboard
    writes a request; the next read gets the matching reply. Requests it does
    not recognise get nothing, which is exactly what a real bus does when
    a controller is not there - and is the case the runner has to survive.
    """

    #: As with the panel's call log: a soak test writes two requests a frame,
    #: and a record of every one of them is a leak in the instrument rather
    #: than in the thing being measured.
    MAX_WRITES = 200

    def __init__(self, *a, **kw):
        self.written = []
        self.n_writes = 0
        self.rx = b""
        self.script = []
        self.unanswered = 0

    def write(self, data):
        self.n_writes += 1
        if len(self.written) < self.MAX_WRITES:
            self.written.append(bytes(data))
        for match, reply in self.script:
            if match(bytes(data)):
                self.rx += reply
                return len(data)
        self.unanswered += 1
        return len(data)

    def any(self):
        return len(self.rx)

    def read(self, n=None):
        if not self.rx:
            return None
        if n is None or n >= len(self.rx):
            out, self.rx = self.rx, b""
        else:
            out, self.rx = self.rx[:n], self.rx[n:]
        return out


# The stubs in stubs/ import the classes above; there is no module-building
# helper here because MicroPython will not construct a module object, and real
# files on the path are a better stand-in anyway.


def wire():
    """Hand back the pieces a test drives, once the stubs are importable."""
    import frozen.display
    import frozen.buttons
    import machine
    return {"display": frozen.display.DISPLAY,
            "buttons": frozen.buttons,
            "uart": machine.UART()}
