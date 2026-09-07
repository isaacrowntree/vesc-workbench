# End-to-end, in the interpreter the display runs

`make test-device`

Everything in `davega/tests/` runs under CPython, which is fast and convenient
and does not tell you whether the code will start on the board. This does: the
real modules, in **MicroPython 1.14** — the version the DAVEGA reports — with
the panel, the buttons and the UART faked, driven through a whole ride.

Same argument as `lisp/tests/`: test the code in the interpreter that will
execute it, not in a host language that resembles it.

## What is real and what is faked

| | |
|---|---|
| The interpreter | **Real.** MicroPython 1.14, built from source, `framebuf` compiled in. |
| The dashboard | **Real.** `davega/gui/` is imported unmodified. |
| The telemetry | **Recorded.** Two frames captured off a FOCBOX Unity on firmware 7.00 — one per controller — plus a ride built to order for the states you cannot safely capture on request. |
| The panel, buttons, UART | Faked, and thin. They record rather than simulate. |

The fakes are real modules on the path under the names the firmware uses
(`frozen.display`, `frozen.buttons`, `machine`), so `gui` imports exactly what
it imports on the board and has no idea it is being tested.

## What it catches that the CPython suite cannot

- **Language and library.** CPython accepts syntax and calls MicroPython does
  not, and the failure lands as a dead screen on a deck rather than a red test.
- **`framebuf`.** `bands` composes curves into a real framebuffer on the device
  and into a Python stand-in everywhere else. The two are rendered side by side
  and compared byte for byte — which is how we found that MicroPython stores an
  RGB565 pixel with a native 16-bit write, so on a little-endian MCU the low
  byte lands first, while the ILI9341 wants the high byte first and
  `writeblock` streams the buffer untouched. Every curve would have reached the
  panel with its colours reversed.
- **Allocation.** The board has 98 kB of heap and rides for hours. A frame that
  allocates a little each time boots fine, looks fine, and dies on the way
  home. Two consecutive 400-frame windows are measured, because one cannot tell
  a leak from a warm-up.
- **The loop.** Buttons through the real debounce and hold thresholds, the menu,
  a theme change, a controller that stops answering, and the recovery.

Absolute byte counts are reported, not asserted: this is the unix port on a
64-bit host, where every reference is twice the width. What carries is drift.

## Adding a frame

`frames.build(...)` assembles a `COMM_GET_VALUES` reply at the offsets in
`vesc_comm_standard.cpp`. The two recorded frames are checked against their own
CRC at import, because a recording that has been retyped by hand is worth
nothing if a byte moved, and a silently wrong fixture is worse than none.
