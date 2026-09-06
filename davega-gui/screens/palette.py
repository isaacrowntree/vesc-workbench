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
