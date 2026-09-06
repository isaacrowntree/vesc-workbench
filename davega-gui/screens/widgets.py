"""Drawing helpers that know what is already on the glass.

The expensive habit on an SPI display is repainting a region to change one
character inside it. `text` compares against what was drawn there last time and
touches only the character cells that actually differ.
"""

CHAR_W, CHAR_H = 8, 8
NUM_W, NUM_H, NUM_GAP = 3, 5, 1


def _numeric(t):
    for c in t:
        if c not in "0123456789.- ":
            return False
    return True


def cell_size(text, scale):
    """Must agree with harness.display.glyph_size - the device uses a 3x5
    font for scaled numbers and an 8x8 cell for everything else."""
    if scale > 1 and _numeric(text):
        return (NUM_W + NUM_GAP) * scale, NUM_H * scale
    return CHAR_W * scale, CHAR_H * scale


def text(d, x, y, old, new, scale=1, color=0xFFFF, bg=0x0000):
    """Draw `new` at (x, y), given that `old` is already there.

    Returns `new`, so callers can store it as the new previous value.
    """
    # Clear using the wider of the two cells: if the old text used the 8x8
    # path and the new one uses the narrow 3x5 numeric path (or the reverse),
    # clearing at the new width leaves a column of the old glyph behind.
    numeric = _numeric(new)
    cw_new, ch_new = cell_size(new, scale)
    cw_old, ch_old = cell_size(old, scale) if old is not None else (cw_new, ch_new)
    cw, ch = max(cw_new, cw_old), max(ch_new, ch_old)
    if old is None:                       # nothing known: draw the lot
        d.set_color(color, bg)
        d.set_pos(x, y)
        d.print(new, scale=scale, numeric=numeric)
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
            d.print(c, scale=scale, numeric=numeric)
    return new
