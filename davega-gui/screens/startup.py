"""The power-on sweep.

Every instrument cluster worth the name runs its needles to the stop and back
when you switch it on. It is a self-test you can see: a gauge that does not
sweep is broken, and you find out before you set off rather than at speed.

It gets its own screen, and that is not decoration. Sweeping the live screen
means every number on it changes every frame, and a character costs ~8.6 ms on
this hardware - measured at 678 ms a frame, which is a slideshow. So the splash
draws its text once as chrome and animates bars only.
"""
from .base import RegionScreen, MARGIN, W


def ease(t):
    """Fast away from the stops, slower into them - how a needle behaves."""
    if t < 0:
        t = 0.0
    elif t > 1:
        t = 1.0
    return 3 * t * t - 2 * t * t * t


class Splash(RegionScreen):
    """Three bars sweeping to the stop and back, and the board's name.

    The bars are the only thing that moves, so a frame costs one clear and one
    fill each - a few milliseconds, not a few hundred.
    """

    BARS = ((96, 20), (132, 14), (160, 10))
    CYCLES = 2
    STEPS = 12
    HOLD = 2

    def __init__(self, theme=None, name="NAZARE"):
        self.name = name
        self._t = 0.0
        self._step = 0
        RegionScreen.__init__(self, theme)

    @property
    def total_steps(self):
        return self.CYCLES * (2 * self.STEPS + self.HOLD)

    def settled(self):
        return self._step >= self.total_steps

    def advance(self):
        """One step of the sweep. Returns the 0..1 position of the needles."""
        if self.settled():
            self._t = 0.0
            return self._t
        cycle = 2 * self.STEPS + self.HOLD
        i = self._step % cycle
        if i < self.STEPS:
            self._t = ease(i / self.STEPS)
        elif i < self.STEPS + self.HOLD:
            self._t = 1.0
        else:
            self._t = ease(1.0 - (i - self.STEPS - self.HOLD) / self.STEPS)
        self._step += 1
        return self._t

    def chrome(self, d):
        d.set_color(self.t.ink, self.t.ground)
        d.set_pos(MARGIN, 40)
        d.print(self.name, scale=2)
        d.set_color(self.t.dim, self.t.ground)
        d.set_pos(MARGIN, 64)
        d.print("SYSTEM CHECK")
        for y, h in self.BARS:
            d.fill_rectangle(MARGIN, y, W - 2 * MARGIN, h, self.t.track)

    def _bar_painter(self, y, h, colour):
        span = W - 2 * MARGIN

        def paint(d, f, b, v):
            d.fill_rectangle(MARGIN, y, span, h, self.t.track)
            if v:
                d.fill_rectangle(MARGIN, y, v, h, colour())
        return paint

    def _build_regions(self):
        span = W - 2 * MARGIN
        colours = (lambda: self.t.accent, lambda: self.t.warn,
                   lambda: self.t.ink)
        out = []
        for i, (y, h) in enumerate(self.BARS):
            out.append(("bar%d" % i, MARGIN, y, span, h,
                        (lambda idx: lambda f, b: int(span * self.advance()
                                                      if idx == 0 else span * self._t))(i),
                        self._bar_painter(y, h, colours[i])))
        return tuple(out)


def play(splash, d, board, frame, on_frame=None):
    """Run the sweep to completion. Returns the number of frames drawn."""
    n = 0
    splash.render(d, frame, board, full=True)
    while not splash.settled() and n < 200:
        splash.render(d, frame, board)
        n += 1
        if on_frame:
            on_frame(n)
    return n
