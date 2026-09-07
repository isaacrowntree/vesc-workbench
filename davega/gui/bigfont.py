"""Big digits, drawn as rectangles.

The display ships a 3x5 digit font and a `draw_number` that renders it - but
that routine builds the glyph in the panel's 3300-byte framebuffer, which holds
1650 pixels. A single digit at scale 12 needs 2160, so it silently overflows
and produces a handful of stray pixels rather than a number. Anything large
enough to read while riding is over that budget.

So we draw them ourselves. Each column of the glyph becomes one or two filled
rectangles - a run of set bits is one call - which costs about six draw calls a
digit at any size, and has no buffer to overflow.

Bit i of each column byte is row i, top to bottom.
"""

# Bytes lifted from frozen.display_util.FONT_3X5 on the device, so the digits
# match the ones the stock display draws.
FONT = bytearray(b"\x1f\x11\x1f\x00\x00\x1f\x1d\x15\x17\x11\x15\x1f\x07\x04\x1f"
                 b"\x17\x15\x1d\x1f\x15\x1d\x01\x01\x1f\x1f\x15\x1f\x17\x15\x1f")

# The stock '1' is the right-hand column and nothing else, which at speed
# reads as a stray bar rather than a numeral - "12" looks like "2" with a
# tally mark beside it. Give it a flag and a foot, the way a 1 is drawn
# everywhere else, so two digits read as two digits.
FONT[3], FONT[4], FONT[5] = 0b10010, 0b11111, 0b10000

COLS, ROWS = 3, 5
GAP = 1                       # columns of space between digits


def char_w(scale):
    return (COLS + GAP) * scale


def char_h(scale):
    return ROWS * scale


def width(text, scale):
    """Pixel width, accounting for the narrow colon."""
    return sum(2 * scale if ch == ":" else char_w(scale) for ch in str(text))


def _runs(column):
    """Vertical runs of set bits: (start_row, length) pairs.

    One rectangle per run rather than per pixel - a digit is three columns and
    rarely more than two runs each, so a glyph costs about six calls however
    big it is.
    """
    out = []
    row = 0
    while row < ROWS:
        if column & (1 << row):
            start = row
            while row < ROWS and column & (1 << row):
                row += 1
            out.append((start, row - start))
        else:
            row += 1
    return out


def draw_digit(d, x, y, digit, scale, colour):
    """One digit. Returns the x to draw the next one at."""
    base = digit * COLS
    for c in range(COLS):
        for start, length in _runs(FONT[base + c]):
            d.fill_rectangle(x + c * scale, y + start * scale,
                             scale, length * scale, colour)
    return x + char_w(scale)


def draw(d, x, y, text, scale, colour, bg=None):
    """Draw a numeric string. Anything that is not a digit is spacing.

    `-` and `.` get their own minimal glyphs so a negative or fractional value
    still reads; everything else advances without drawing.
    """
    for ch in str(text):
        if "0" <= ch <= "9":
            x = draw_digit(d, x, y, ord(ch) - 48, scale, colour)
        elif ch == "-":
            d.fill_rectangle(x, y + 2 * scale, COLS * scale, scale, colour)
            x += char_w(scale)
        elif ch == ".":
            d.fill_rectangle(x, y + 4 * scale, scale, scale, colour)
            x += char_w(scale)
        elif ch == ":":
            # Narrower than a digit: a colon between hours and minutes should
            # not cost the width of a numeral.
            d.fill_rectangle(x, y + scale, scale, scale, colour)
            d.fill_rectangle(x, y + 3 * scale, scale, scale, colour)
            x += 2 * scale
        else:
            x += char_w(scale)
    return x


def clear(d, x, y, text, scale, bg):
    d.fill_rectangle(x, y, width(text, scale), char_h(scale), bg)
