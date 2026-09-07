"""The parts every layout is built from.

A layout is an arrangement, not a renderer. The pieces here - a segmented bar,
a centre-zero meter, a rail, a sweeping arc, a big numeral - are the vocabulary
all nine share, so a new treatment is a composition rather than another
thousand lines of drawing code.

Most of them repaint the *difference* between the old value and the new. That
is not an optimisation detail, it is the constraint the whole design sits
inside: a draw call costs 2.9 ms whatever its size, so a meter that repaints
itself costs the frame and a meter that repaints its tip costs nothing.
"""
from .. import widgets, bigfont, bands


def _ceil(x):
    n = int(x)
    return n if n == x or x < 0 else n + 1


def soc(board, volts, frame=None):
    """State of charge, preferring the runner's Rint-compensated figure -
    which does not sag every time the rider accelerates."""
    if frame is not None and frame.get("soc") is not None:
        return frame["soc"]
    return board.soc_for_voltage(volts)


def kph(f, b):
    return abs(b.kph_for_erpm(f["rpm"]))


def speed_text(f, b):
    return "%2d" % round(kph(f, b))


def charge_text(f, b):
    return "%d" % round(100 * soc(b, f["input_voltage"], f))


def fit(value, digits=2):
    """A number in at most `digits` characters, clamped rather than overflowed.

    A region is a fixed box: its width is decided when the layout is built,
    from the widest value the designer expected. A value one digit wider does
    not wrap or clip, it draws off the side of the panel - which is a crash in
    the harness and a smear of pixels on the glass. Clamping is the honest
    failure: 99 km of range left when there are 140 is wrong by less than the
    estimate's own error, and it stays inside its box.
    """
    n = int(round(value))
    if n < 0:
        n = 0
    ceiling = 10 ** digits - 1
    return "%d" % (ceiling if n > ceiling else n)


def range_text(f, b):
    return fit(f["s_range_km"]) if f.get("s_range_km") else "--"


def fault_text(f, b):
    return ("FAULT %d" % f["fault"]) if f["fault"] else ""


# -- painters -------------------------------------------------------------

def big(s, key, x, y, scale, colour=None, bg=None):
    """A large numeral that repaints only the digits that changed."""
    def paint(d, f, b, v):
        if v == "":
            return                      # something else owns this block
        col = colour(f, b, s.t) if colour else s.t.ink
        # Forced means a curve has just painted ground over these digits. The
        # old value is still remembered, so the redraw has to clear as well as
        # draw or the previous glyph shows through the gaps in the new one.
        forced = key in s._force
        s._force.discard(key)
        widgets.big(d, x, y, s._drawn.get(key), v, scale, col,
                    s.t.ground if bg is None else bg, force=forced)
    return paint


def vrail(s, key, x, y0, y1, w, colour=None):
    """A vertical bar that grows upward from y1. Only the delta is painted:
    clearing and refilling the track flashes, and this runs every frame."""
    def paint(d, f, b, v):
        t = s.t
        col = colour(f, b, t) if colour else t.accent
        prev = s._drawn.get(key, 0) or 0
        # A shift light changes colour without changing length. Diffing on the
        # length alone leaves the bar the colour it used to be.
        if s._colours.get(key) != col:
            s._colours[key] = col
            d.fill_rectangle(x, y1 - v, w, v, col)
            d.fill_rectangle(x, y0, w, (y1 - v) - y0, t.track)
            return
        if v > prev:
            d.fill_rectangle(x, y1 - v, w, v - prev, col)
        elif v < prev:
            d.fill_rectangle(x, y1 - prev, w, prev - v, t.track)
    return paint


def hbar(s, key, x, y, w, h, colour=None):
    """A horizontal bar growing right from x, delta-painted."""
    def paint(d, f, b, v):
        t = s.t
        col = colour(f, b, t) if colour else t.accent
        prev = s._drawn.get(key, 0) or 0
        # Charge changes colour as it empties, and it can do that without the
        # bar's length changing enough to notice.
        if s._colours.get(key) != col:
            s._colours[key] = col
            d.fill_rectangle(x, y, v, h, col)
            d.fill_rectangle(x + v, y, w - v, h, t.track)
            return
        if v > prev:
            d.fill_rectangle(x + prev, y, v - prev, h, col)
        elif v < prev:
            d.fill_rectangle(x + v, y, prev - v, h, t.track)
    return paint


def centre_meter(s, key, x, w, y, h, mid=None):
    """Regen left, drive right, from a hard zero. Only the tip moves."""
    zero = mid if mid is not None else x + w // 2

    def paint(d, f, b, v):
        t = s.t
        prev = s._drawn.get(key, 0) or 0
        if (v >= 0) != (prev >= 0):
            d.fill_rectangle(x, y, w, h, t.track)
            prev = 0
        if v >= 0:
            if v > prev:
                d.fill_rectangle(zero + prev, y, v - prev, h, t.warn)
            elif v < prev:
                d.fill_rectangle(zero + v, y, prev - v, h, t.track)
        else:
            if v < prev:
                d.fill_rectangle(zero + v, y, prev - v, h, t.accent)
            elif v > prev:
                d.fill_rectangle(zero + prev, y, v - prev, h, t.track)
        d.fill_rectangle(zero - 1, y - 4, 2, h + 8, t.ink)
    return paint


def seg_bar(s, x, y, w, h, segs=12, gap=3):
    """The battery, in blocks. Reads at a glance and in peripheral vision in
    a way a continuous bar does not."""
    def paint(d, f, b, v):
        t = s.t
        sw = (w - gap * (segs - 1)) // segs
        colour = t.soc_color(v)
        for i in range(segs):
            lit = (i / float(segs)) < v
            d.fill_rectangle(x + i * (sw + gap), y, sw, h,
                             colour if lit else t.track)
    return paint


def banner(s, x, y, w, h, keys=()):
    """A fault takes a whole block. It is rare and it matters, so it displaces
    what was there rather than squeezing in beside it."""
    def paint(d, f, b, v):
        t = s.t
        if not v:
            if s._fault_shown:
                d.fill_rectangle(x, y, w, h, t.ground)
                for k in keys:
                    s._force.add(k)           # they must redraw, and clear
                s._fault_shown = False
            return
        s._fault_shown = True
        d.fill_rectangle(x, y, w, h, t.danger)
        d.set_color(t.ink, t.danger)
        d.set_pos(x + 8, y + h // 2 - 4)
        d.print(v)
    return paint


def quiet(painter):
    """Wrap a painter so an empty value paints nothing at all.

    A region that blanks because a banner has taken its space must not clear
    itself: the banner is already there, and clearing would punch a hole in
    it. The big-numeral painter does this itself; text regions need wrapping.
    """
    def paint(d, f, b, v):
        if v == "":
            return
        painter(d, f, b, v)
    return paint


# -- curves ---------------------------------------------------------------

def arc_sweep(s, key, cx, cy, r, thickness, a0, a1, colour=None, step=3,
              under=None, forces=(), unlit=None, redline=None, hot=None,
              from_mid=False):
    """A value drawn as an arc.

    `from_mid` fills outward from the middle of the sweep instead of from
    `a0`, for a gauge whose rest position is the centre - regen one way and
    drive the other are two different things, not more and less of one.

    The arc is repainted whole, from `a0` to wherever it reaches, into a band
    that covers only the part of the dial it can occupy. Painting just the
    wedge that changed is cheaper and was what this did first, but an arc
    drawn in three pieces lands on different pixels from the same arc drawn in
    one - quantisation, seams at the joins, colour decided per piece rather
    than per angle - and a differential renderer that disagrees with a full
    repaint is worse than one that costs a few more milliseconds.

    Whole is still cheap: the band is one transfer of about 20k pixels, ~25 ms,
    against 481 ms for the same arc drawn as one rectangle per column.
    """
    dd = min(1.0, 57.3 / max(1, r))

    def paint(d, f, b, v):
        t = s.t
        col = colour(f, b, t) if colour else t.accent
        back = t.track if unlit is None else unlit
        s._colours[key] = col

        # The band: everything between a0 and a1 that this radius can reach.
        xs, ys = [], []
        deg = a0
        while deg <= a1:
            sin, cos = bands.sincos(deg)
            for rr in (r, r - thickness):
                xs.append(cx + int(rr * sin))
                ys.append(cy - int(rr * cos))
            deg += dd
        x0 = max(0, min(xs) - 2)
        y0 = max(0, min(ys) - 2)
        x1 = min(s.d_width - 1, max(xs) + 2)
        y1 = min(s.d_height - 1, max(ys) + 2)

        def draw(c):
            c.fill(t.ground)
            if under:
                under(c, t)
            mid = (a0 + a1) / 2.0
            deg = a0
            while deg <= a1:
                sin, cos = bands.sincos(deg)
                if (mid <= deg <= v or v <= deg <= mid) if from_mid \
                        else deg <= v:
                    shade = col
                    if redline is not None and deg >= redline and hot is not None:
                        shade = hot
                else:
                    shade = back
                c.spoke(cx, cy, r - thickness, r, sin, cos, shade, 2)
                deg += dd
        bands.paint(d, x0, y0, x1 - x0 + 1, y1 - y0 + 1, draw)
        # The band has just replaced everything under it with ground and then
        # this arc. Anything else that lives inside it has to draw itself
        # again, or it stays missing until the next full repaint.
        for k in forces:
            s._force.add(k)
    return paint


def needle(s, key, cx, cy, r0, r1, colour=None, width=2, under=None,
           forces=()):
    """A hand that sweeps, painted as the union of where it was and where it
    is now - with whatever it covers redrawn underneath it.

    A hand is the expensive shape: its bounding box is the whole dial and it
    moves every frame. Painting the union of two positions keeps the box down
    to the wedge between them, and `under` puts the rings back in that wedge so
    the hand does not leave a trail of ground colour through them.
    """
    def paint(d, f, b, v):
        t = s.t
        col = colour(f, b, t) if colour else t.danger
        prev = s._drawn.get(key)
        prev = v if prev is None else prev
        xs, ys = [], []
        deg = min(prev, v)
        last = max(prev, v)
        while True:
            sin, cos = bands.sincos(deg)
            for rr in (r0, r1):
                xs.append(cx + int(rr * sin))
                ys.append(cy - int(rr * cos))
            if deg >= last:
                break
            deg = min(deg + 2.0, last)
        x0 = max(0, min(xs) - 3)
        y0 = max(0, min(ys) - 3)
        x1 = min(s.d_width - 1, max(xs) + 3)
        y1 = min(s.d_height - 1, max(ys) + 3)

        def draw(c):
            c.fill(t.ground)
            if under:
                under(c, t)
            sin, cos = bands.sincos(v)
            c.spoke(cx, cy, r0, r1, sin, cos, col, width)
        bands.paint(d, x0, y0, x1 - x0 + 1, y1 - y0 + 1, draw)
        for k in forces:
            s._force.add(k)
    return paint
