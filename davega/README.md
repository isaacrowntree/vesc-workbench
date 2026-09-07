# davega

A replacement UI for the DAVEGA X, and — more to the point — a way to develop
one without uploading to a 2.8″ screen and squinting at it.

```sh
make gui-test      # golden images, draw budget, field sweeps
make gui-golden    # re-record the golden images after an intended change
```

No device, no hardware, no image library. Runs in CI.

## Why this can exist

The stock app is frozen bytecode and cannot be edited. It does not need to be.
`exec_custom_start` runs **before** `boot_fw` ([boot
order](../docs/findings.md#the-davegas-boot-order-and-why-startpy-is-safe)), so
a `start.py` can take the screen entirely — which is exactly what
[sn8ke](https://github.com/janpom/sn8ke) does.

The device hands us everything needed:

| | |
|---|---|
| `frozen.display.DISPLAY` | ILI9341, 240×320, `fill_rectangle` / `print` / `set_color` / `set_pos` |
| `frozen.vesc_comm.VescComm` | the telemetry layer — `get_values`, `fwd_get_values`, `can_ping` |
| `frozen.vesc_data` | `VESC_VALUES_DESCR`, the 14 fields the display parses |
| `frozen.colors`, `frozen.image`, `frozen.buttons` | the rest of the UI kit |

**A custom UI also sidesteps the firmware-7 version gate**, because the gate
lives in `frozen/run_standard.py` — the stock app — and `VescComm` has no
version check of its own. Our own screen never calls it.

## The pieces

```
harness/display.py     host stand-in for the ILI9341: records every draw call,
                       rasterises to RGB, and fails on anything out of frame
harness/telemetry.py   the 14 fields, and the envelope derived from verified
                       board configuration
harness/png.py         stdlib PNG writer, so CI needs no image library
screens/riding.py      baseline screen - a port of the stock layout
tests/test_screens.py  golden images, draw budget, per-field sweeps
```

## What the tests actually check

**Golden images.** Each frame in the envelope renders to a PNG committed to the
repo. A layout change shows up as an image diff in review.

**A drawing budget.** The harness counts draw calls, because an ESP32 pushing
hundreds of `fill_rectangle`s per frame will feel slow no matter how it looks.
The budget is a design constraint, enforced in CI rather than discovered on the
board.

**Field sweeps.** Every one of the 14 fields is swept across its full range and
the screen must stay inside 240×320. This catches "fine until the number reaches
three digits" without anyone having to think of the case.

## Performance is a test, not a hope

A full repaint of the riding screen pushes **96k pixels — 1.26x the frame area**,
because erasing paints everything and the content then paints over it. At two
bytes a pixel that is ~193 kB down the SPI bus to change, usually, one digit.

So screens are described as regions with values, and rendering repaints only
the regions whose value moved — then only the *character cells* within them
that differ. Measured by the harness:

| | pixels | SPI bytes | bus time @40 MHz |
|---|---|---|---|
| First paint | 96,388 | 193 kB | ~39 ms |
| Steady frame (speed ticks over) | 4,320 | 8.6 kB | ~1.7 ms |
| Nothing changed | 0 | 0 | 0 |

**22x cheaper** in the case that happens every frame.

The dangerous failure mode for partial redraw is stale pixels — a new value
narrower than the old one, leaving part of the previous value on the glass. So
the suite renders **every transition between envelope frames (81 of them)**
differentially and asserts the result is byte-identical to a full repaint. That
test is what makes the optimisation safe to rely on, and it earned its keep
immediately: it caught the fault banner staying on screen after the ESC
recovered.

The budgets are ratchets. Tighten them as the numbers improve.

## Fixtures are derived, not recorded

There is no capture step. The bounds come from configuration read back from the
ESC and verified — 12s4p, 17 Ah, 80 A/side motor, 30/−8 A/side battery, 4.2:1,
200 mm wheels — so `Board()` generates frames a real ride rarely produces:
thermal derate at 100 °C, full regen near a full pack, a fault at speed.

Change `Board(...)` for your own hardware and the whole envelope moves with it.

## Writing a screen

A screen is a pure function of `(display, frame, board)` — no I/O, no globals —
so the same code runs in the harness and on the device.

```python
def render(d, frame, board):
    d.set_color(WHITE, BLACK)
    d.erase()
    d.set_pos(6, 24)
    d.print("%3d" % round(board.kph_for_erpm(frame.rpm)), scale=6)
```

## Design

[DESIGN.md](DESIGN.md) — the measured constraints, the rule they imply
(digits snap, gauges sweep), and where the layout ideas come from.

`screens/palette.py` has gradient ramps for state of charge, temperature and
power flow; `screens/anim.py` has easing and a `Tweened` value that follows a
target over frames. Both are covered by tests: ramps must stay inside RGB565,
and an animation must stay inside the per-frame bus budget *and* land
pixel-identical to a static render of its end value.

## Themes

Ten themes, each a palette plus a layout name — `screens/themes.py`. Every
screen in every theme, day and night, at true device size, is in
[mockups/index.html](mockups/index.html) — `make mockups` regenerates it from
the code the device runs. All ten are selectable from the display's own menu;
the list comes from the registry, so a theme added to `themes.py` shows up
there without a second edit.

```sh
make davega-theme THEME=nazare    # writes /data/config.json on the display
```

`nazare` is the default: the best idea from each of the other nine and nothing
else. Every theme goes through the same harness as the default —
`tests/test_themes.py` renders all nine envelope frames per theme, asserts the
differential path matches a full repaint across all 81 transitions, and holds
each to the drawing budget. It also checks every colour declared in
`themes.py` appears in the mockups, so the pictures cannot drift from what the
device draws.

## Measured on the device

Five screens, ten themes, rendered on a real DAVEGA X:

| | |
|---|---|
| Full screen paint | 472-763 ms |
| Settled frame (speed moves) | **23-29 ms** |
| Free RAM after imports | ~36 kB |

Large digits go through the device's own `draw_number` against its 3x5 font,
which is native and roughly three times cheaper than the character path - that
alone took a settled frame from 82 ms to 25 ms.

The cost model behind the tests came from measuring the panel, not from theory:
a draw call costs ~2.7 ms of interpreter overhead whatever its size, and a
character ~8.6 ms. Pixels are nearly free. Optimising a screen means drawing
fewer characters, then making fewer calls.

## Status

Working: five screens, ten themes, buttons and the menu, all of it rendering on
hardware and covered by 129 host-side assertions.

Not done: **live telemetry**. `VescComm(uart, False)` constructs and
`get_values(can_id)` sends on tx 16 / rx 17, but the ESC does not answer yet, so
every screen is still drawing an injected frame. Until that lands there is no
persistent on-device app either - the renderer is driven from the host.
