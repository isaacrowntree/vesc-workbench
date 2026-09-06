"""Colour on an ILI9341.

The panel is RGB565 — 65,536 colours, not the two the stock layout mostly uses.
Colour is free: it costs the same two bytes per pixel whatever the value. What
is *not* free is the number of pixels you repaint to change one, which is why
gradients live in the palette and not in a per-pixel loop.
"""


def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def unpack(c):
    return (((c >> 11) & 0x1F) * 255 // 31,
            ((c >> 5) & 0x3F) * 255 // 63,
            (c & 0x1F) * 255 // 31)


def lerp(a, b, t):
    """Blend two RGB565 colours. t is clamped to 0..1."""
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    ar, ag, ab = unpack(a)
    br, bg, bb = unpack(b)
    return rgb(int(ar + (br - ar) * t),
               int(ag + (bg - ag) * t),
               int(ab + (bb - ab) * t))


def ramp(stops, t):
    """Sample a multi-stop gradient. stops is ((pos, colour), ...) sorted."""
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if t <= p1:
            span = p1 - p0
            return lerp(c0, c1, 0.0 if span <= 0 else (t - p0) / span)
    return stops[-1][1]


# -- the palette -------------------------------------------------------------

BLACK = 0x0000
WHITE = 0xFFFF
INK = rgb(232, 236, 244)      # off-white; pure white glares at night
DIM = rgb(96, 104, 122)       # labels and furniture
LINE = rgb(38, 42, 54)        # hairlines and inactive track

CYAN = rgb(64, 220, 255)
GREEN = rgb(64, 220, 130)
AMBER = rgb(255, 186, 64)
RED = rgb(255, 76, 76)
VIOLET = rgb(168, 130, 255)

# State of charge: green through amber to red, so the colour alone tells you
# how much is left without reading the number.
SOC_RAMP = ((0.0, RED), (0.25, AMBER), (0.55, GREEN), (1.0, GREEN))

# Temperature: calm until it matters, then unmissable.
TEMP_RAMP = ((0.0, CYAN), (0.5, GREEN), (0.8, AMBER), (1.0, RED))

# Power: regen reads cool, drive reads warm, coasting is quiet.
POWER_RAMP = ((0.0, CYAN), (0.5, DIM), (0.75, AMBER), (1.0, RED))


def soc_color(pct):
    return ramp(SOC_RAMP, pct)


def temp_color(t, start, end):
    return ramp(TEMP_RAMP, (t - 20.0) / max(1.0, end - 20.0))


def power_color(amps, limit):
    return ramp(POWER_RAMP, (amps + limit) / (2.0 * max(1.0, limit)))


# -- contrast ---------------------------------------------------------------
# A dash is read in daylight, at speed, through sunglasses, while it vibrates.
# Grey-on-black is unreadable in those conditions no matter how good it looks
# on a monitor, so contrast is a hard constraint here rather than a taste.

def luminance(c):
    """WCAG relative luminance of an RGB565 colour."""
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = unpack(c)
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(fg, bg):
    """WCAG contrast ratio, 1.0 (invisible) to 21.0 (black on white)."""
    a, b = luminance(fg), luminance(bg)
    if a < b:
        a, b = b, a
    return (a + 0.05) / (b + 0.05)


# WCAG AA for large text is 3.0 and for body text 4.5. A vibrating 2.8" panel
# in sunlight is a harsher environment than either, so:
MIN_PRIMARY = 7.0     # speed, battery percentage - the things you must read
MIN_LABEL = 4.5       # labels and secondary values


# -- colour blindness --------------------------------------------------------
# Red and green are the pair that fails, and a state-of-charge ramp running
# green through amber to red is the textbook case. Semantic colours therefore
# have to be separable for the most common form of colour blindness, not just
# to someone with full colour vision.

def deuteranope(c):
    """Approximate how an RGB565 colour appears with deuteranopia."""
    r, g, b = [v / 255.0 for v in unpack(c)]

    def lin(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = lin(r), lin(g), lin(b)
    L = 17.8824 * r + 43.5161 * g + 4.11935 * b
    M = 3.45565 * r + 27.1554 * g + 3.86714 * b        # noqa: F841
    S = 0.0299566 * r + 0.184309 * g + 1.46709 * b
    M2 = 0.494207 * L + 1.24827 * S
    out = (0.0809 * L - 0.1305 * M2 - 0.1167 * S,
           -0.0102 * L + 0.0540 * M2 + 0.1136 * S,
           -0.0003 * L - 0.0041 * M2 + 0.6935 * S)
    return tuple(0.0 if v < 0 else 1.0 if v > 1 else v for v in out)


def separation(a, b):
    """How far apart two colours look, roughly 0-100."""
    ar, ag, ab = unpack(a)
    br, bg, bb = unpack(b)
    return (((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2) ** 0.5) / 4.42


def separation_cb(a, b):
    """The same, as a deuteranope sees it."""
    x, y = deuteranope(a), deuteranope(b)
    return (sum((p - q) ** 2 for p, q in zip(x, y)) ** 0.5) * 57.7


# A rider glancing down has to tell these apart at speed, in sunlight.
MIN_SEPARATION = 20        # warn vs danger, accent vs ink
MIN_SEPARATION_CB = 14     # the same, with deuteranopia

# On a light ground every warm colour darkens toward the same brown, and
# under deuteranopia amber and red share a hue - so danger is driven much
# darker than the contrast bar requires. Lightness is the channel that still
# works when hue does not.
DANGER_LIGHT = 11.0


def toward_hue(c, hue, amount=0.7):
    """Rotate a colour toward a target hue, keeping saturation and value.

    Used for danger on light themes: a deuteranope sees amber and red as the
    same hue, so red is pulled toward crimson-magenta, which they can still
    separate. It still reads as danger to everyone else.
    """
    h, s, v = _to_hsv(c)
    d = ((hue - h + 540) % 360) - 180
    return _from_hsv((h + d * amount) % 360, min(1.0, s + 0.1), v)


DANGER_HUE = 335.0


# -- deriving a light variant ------------------------------------------------
# A dark dash is right at dusk and wrong at noon. Rather than hand-author ten
# more palettes and hope they hold, each light variant is derived from its dark
# one and then held to exactly the same tests - contrast, semantic separation,
# and colour blindness. Anything that fails is a bug in the derivation, not a
# matter of taste.

def mix(c, target, t):
    ar, ag, ab = unpack(c)
    br, bg, bb = unpack(target)
    return rgb(int(ar + (br - ar) * t),
               int(ag + (bg - ag) * t),
               int(ab + (bb - ab) * t))


def _to_hsv(c):
    r, g, b = [v / 255.0 for v in unpack(c)]
    mx, mn = max(r, g, b), min(r, g, b)
    v = mx
    s = 0.0 if mx == 0 else (mx - mn) / mx
    if mx == mn:
        h = 0.0
    elif mx == r:
        h = (60 * ((g - b) / (mx - mn)) + 360) % 360
    elif mx == g:
        h = 60 * ((b - r) / (mx - mn)) + 120
    else:
        h = 60 * ((r - g) / (mx - mn)) + 240
    return h, s, v


def _from_hsv(h, s, v):
    i = int(h / 60) % 6
    f = h / 60 - int(h / 60)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = ((v, t, p), (q, v, p), (p, v, t),
               (p, q, v), (t, p, v), (v, p, q))[i]
    return rgb(int(r * 255), int(g * 255), int(b * 255))


def deepen_until(c, ground, target_ratio, limit=40):
    """Darken a colour until it clears `target_ratio`, keeping its hue.

    Mixing toward black also drains saturation, and on a light ground that
    makes every warm colour converge on the same brown - which is how eight of
    ten derived light themes ended up unable to tell "warm" from "fault".
    Dropping value while raising saturation keeps a theme's orange orange and
    its red red.
    """
    h, s0, v0 = _to_hsv(c)
    for i in range(limit + 1):
        t = i / float(limit)
        out = _from_hsv(h, min(1.0, s0 + t * 0.6), v0 * (1 - t * 0.9))
        if contrast(out, ground) >= target_ratio:
            return out
    return _from_hsv(h, 1.0, 0.08)


def darken_until(c, ground, target_ratio, limit=40):
    return deepen_until(c, ground, target_ratio, limit)


def lighten_until(c, ground, target_ratio, limit=40):
    for i in range(limit + 1):
        out = mix(c, WHITE, i / float(limit))
        if contrast(out, ground) >= target_ratio:
            return out
    return WHITE


def paper(tint, amount=0.06):
    """A light ground with a little of the theme's own colour in it.

    Pure white reads as unconsidered and glares; a ground carrying a trace of
    the accent reads as chosen and sits better under the same accent.
    """
    return mix(WHITE, tint, amount)
