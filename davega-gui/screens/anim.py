"""Animation, within a budget the SPI bus can actually pay.

Measured on this hardware: a full repaint is ~96k pixels, about 39 ms of bus
time at 40 MHz. Animating the whole screen is therefore never on. Animating a
*region* is: a 240x18 bar is 4,320 px, about 1.7 ms, which leaves room for 30 fps
with the CPU free to do other things.

So animation here is explicitly bounded. A tween yields intermediate values;
the screen redraws only the region that changed; the harness asserts every
frame of the animation stays inside the per-frame budget, and that the last
frame is pixel-identical to drawing the end state directly.
"""


def ease_out_cubic(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    f = t - 1.0
    return f * f * f + 1.0


def ease_in_out(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def linear(t):
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def tween(a, b, frames, ease=ease_out_cubic):
    """Yield `frames` values from a to b. The last is exactly b, so an
    animation always lands on the true value rather than near it."""
    if frames < 1:
        frames = 1
    for i in range(1, frames + 1):
        t = i / frames
        yield b if i == frames else a + (b - a) * ease(t)


class Tweened:
    """Follows a target value over time, one step per rendered frame.

    Keeps animation out of the screen's drawing code: the screen asks for the
    current display value, and this decides how fast it gets there.
    """

    def __init__(self, value=0.0, frames=8, ease=ease_out_cubic, snap=0.5):
        self.value = float(value)
        self.target = float(value)
        self.frames = frames
        self.ease = ease
        self.snap = snap          # below this difference, just jump
        self._step = 0
        self._from = float(value)

    def set(self, target):
        target = float(target)
        if abs(target - self.value) <= self.snap:
            self.value = self.target = target
            self._step = self.frames
            return self
        self.target = target
        self._from = self.value
        self._step = 0
        return self

    @property
    def settled(self):
        return self._step >= self.frames

    def advance(self):
        """One animation step. Returns the value to draw."""
        if self.settled:
            self.value = self.target
            return self.value
        self._step += 1
        t = self._step / self.frames
        self.value = (self.target if self._step >= self.frames
                      else self._from + (self.target - self._from) * self.ease(t))
        return self.value
