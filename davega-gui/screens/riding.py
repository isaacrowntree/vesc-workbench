"""Baseline riding screen.

Deliberately a port of what the stock display shows, not a redesign: it exists
to prove the harness, the telemetry path and the budget before any design work
starts. Redesign against a passing test suite, not a blank page.

A screen is a pure function of (display, frame, board). No I/O, no globals - so
it runs identically on the device and in the harness.
"""

BLACK = 0x0000
WHITE = 0xFFFF
GREY = 0x8410
RED = 0xF800
AMBER = 0xFD20
GREEN = 0x07E0
BLUE = 0x001F

W, H = 240, 320
MARGIN = 6


def soc(board, volts):
    """State of charge from pack voltage. Crude on purpose - under load this
    reads low, which is the honest direction to be wrong in."""
    span = board.v_full - board.v_empty
    return max(0.0, min(1.0, (volts - board.v_empty) / span))


def _cell(d, x, y, w, h, label, value, color=WHITE):
    d.set_color(GREY, BLACK)
    d.set_pos(x, y)
    d.print(label)
    d.set_color(color, BLACK)
    d.set_pos(x, y + 12)
    d.print(value, scale=2)


def render(d, frame, board):
    d.set_color(WHITE, BLACK)
    d.erase()

    # --- speed, the thing you actually look at
    kph = abs(board.kph_for_erpm(frame.rpm))
    d.set_color(WHITE, BLACK)
    d.set_pos(MARGIN, 24)
    d.print("%3d" % round(kph), scale=6)
    d.set_color(GREY, BLACK)
    d.set_pos(MARGIN + 150, 60)
    d.print("km/h")

    # --- battery bar
    pct = soc(board, frame.input_voltage)
    bar_w = W - 2 * MARGIN
    d.set_color(GREY, BLACK)
    d.fill_rectangle(MARGIN, 96, bar_w, 18, GREY)
    fill = int(bar_w * pct)
    if fill:
        col = GREEN if pct > 0.5 else AMBER if pct > 0.2 else RED
        d.fill_rectangle(MARGIN, 96, fill, 18, col)
    d.set_color(WHITE, BLACK)
    d.set_pos(MARGIN, 120)
    d.print("%4.1fV  %3d%%" % (frame.input_voltage, round(pct * 100)))

    # --- the numbers worth a glance
    half = (W - 2 * MARGIN) // 2
    _cell(d, MARGIN, 148, half, 40, "MOTOR A", "%4.0f" % frame.avg_motor_current)
    _cell(d, MARGIN + half, 148, half, 40, "BATT A", "%4.0f" % frame.avg_input_current)

    fet = frame.temp_fet_filtered
    hot = fet >= board.temp_derate_start
    _cell(d, MARGIN, 208, half, 40, "FET C", "%4.0f" % fet,
          RED if hot else WHITE)
    _cell(d, MARGIN + half, 208, half, 40, "USED Ah", "%4.1f" % frame.amp_hours)

    # --- fault banner, only when there is one
    if frame.fault:
        d.set_color(WHITE, RED)
        d.fill_rectangle(0, 272, W, 24, RED)
        d.set_pos(MARGIN, 280)
        d.print("FAULT %d" % frame.fault)
