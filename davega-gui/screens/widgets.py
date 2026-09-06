"""Drawing helpers that know what is already on the glass.

The expensive habit on an SPI display is repainting a region to change one
character inside it. `text` compares against what was drawn there last time and
touches only the character cells that actually differ.
"""

CHAR_W, CHAR_H = 8, 8


def text(d, x, y, old, new, scale=1, color=0xFFFF, bg=0x0000):
    """Draw `new` at (x, y), given that `old` is already there.

    Returns `new`, so callers can store it as the new previous value.
    """
    cw, ch = CHAR_W * scale, CHAR_H * scale
    if old is None:                       # nothing known: draw the lot
        d.set_color(color, bg)
        d.set_pos(x, y)
        d.print(new, scale=scale)
        return new

    # Pad so a shorter new value still erases what the longer old one left.
    n = max(len(old), len(new))
    for i in range(n):
        a = old[i] if i < len(old) else " "
        c = new[i] if i < len(new) else " "
        if a == c:
            continue
        cx = x + i * cw
        d.set_color(bg, bg)
        d.fill_rectangle(cx, y, cw, ch, bg)
        if c != " ":
            d.set_color(color, bg)
            d.set_pos(cx, y)
            d.print(c, scale=scale)
    return new
