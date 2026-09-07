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


def text(d, x, y, old, new, scale=1, color=0xFFFF, bg=0x0000, force=False):
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
    # A value that switches between numeric and not switches font, and the
    # two have different character pitch. Diffing per character across that
    # boundary compares cells that are not in the same places, and leaves the
    # old glyphs behind at the old spacing. Redraw the whole field instead.
    if force or old is None or (cw_old, ch_old) != (cw_new, ch_new):
        if old is not None:
            d.set_color(bg, bg)
            d.fill_rectangle(x, y, max(len(old) * cw_old, len(new) * cw_new),
                             max(ch_old, ch_new), bg)
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


def big(d, x, y, old, new, scale, colour, bg, force=False):
    """Large digits, repainting only the characters that changed.

    Same idea as `text`, but through `bigfont` - which draws glyphs as filled
    rectangles and so has no size ceiling. A digit costs about six draw calls
    whatever the scale, so redrawing one is cheap and redrawing the field is
    not free.
    """
    from . import bigfont
    ch = bigfont.char_h(scale)

    def offsets(text):
        """Where each character starts. Not a fixed pitch: a colon is narrower
        than a digit, so "0:42" and "1:03" line up but "12.4" and "0:42" do
        not - and diffing across that leaves glyphs at the old spacing."""
        out, cx = [], 0
        for c in text:
            out.append(cx)
            cx += bigfont.width(c, scale)
        return out, cx

    new_off, new_w = offsets(new)
    old_off, old_w = offsets(old) if old is not None else (None, 0)

    if force or old is None or old_off != new_off:
        if old is not None:
            d.fill_rectangle(x, y, max(old_w, new_w), ch, bg)
        bigfont.draw(d, x, y, new, scale, colour)
        return new

    for i, (a, c) in enumerate(zip(old, new)):
        if a == c:
            continue
        cx = x + new_off[i]
        d.fill_rectangle(cx, y, bigfont.width(c, scale), ch, bg)
        bigfont.draw(d, cx, y, c, scale, colour)
    return new
