# Dash design

What the hardware will actually allow, and where the ideas come from.

## The constraints, measured

| | |
|---|---|
| Panel | ILI9341, 240×320 portrait, **RGB565 — 65,536 colours** |
| Full repaint | 96k px ≈ **39 ms** of SPI bus at 40 MHz |
| Steady frame | 4.3k px ≈ **1.7 ms** |
| Worst animating frame | 8.6k px ≈ **3.5 ms** |
| Telemetry arrival | ~5 Hz per motor — the ESC is polled every 100 ms, alternating |

Two things fall out of that and shape everything else.

**Colour is free.** Two bytes per pixel regardless of value, so a gradient costs
the same as flat grey. There is no reason for this display to be mostly white
text on black.

**Motion is affordable, but only locally.** 3.5 ms a frame leaves room for
60 fps with the CPU almost idle. What is *not* affordable is animating the whole
screen, and what is *not useful* is animating faster than 5 Hz data arrives —
tweening exists to make 5 Hz data feel continuous, not to invent detail.

## The rule that follows: digits snap, gauges sweep

Animating three large digits costs 8,640 px. Animating a bar segment costs a few
hundred. That is also what every good dash already does — the needle sweeps, the
odometer ticks. A tweened numeric readout looks like a slot machine and reads
worse.

So: **the analogue element carries the motion, the digital element carries the
truth.** `anim.Tweened` drives gauges; numbers are set directly.

## Where the ideas come from

**Toyota** — the power-flow bar. A centre-zero horizontal meter with charge to
the left and power to the right tells you what the drivetrain is doing without a
single number. It maps exactly onto motor current: regen left in cyan, drive
right through amber to red. This is the single most useful borrowed idea,
because on an eskate the thing you most want to feel is how hard you are pulling
from the pack.

**Tesla** — ruthless hierarchy. One number dominates; everything else is
secondary until it matters. No unit labels cluttering the hero element, no
chrome for its own sake. On a 240 px width that is not minimalism as taste, it
is the only way to make speed readable at a glance while moving.

**BMW** — the outer arc. A sweeping arc pinned to the edge of the display gives
an analogue read of speed without consuming the middle of the screen, and only
the changed segment needs repainting, so it is cheap. Angular, high-contrast
accents rather than skeuomorphic dials.

**Mercedes** — depth and restraint. Thin rings, generous negative space, subtle
gradient fills instead of hard blocks. The lesson is that a dark background with
a few saturated accents reads as expensive; a screen full of coloured boxes
reads as a debug view.

**Ebike (Bosch Kiox, Specialized)** — the honest battery. A segmented bar plus
percentage plus estimated remaining range, and an unmissable colour block for
assist mode. The Hoyt Puck has three modes; that belongs on screen as a bold,
glanceable state, not a number in a corner.

## One instrument, not five views

Five screens sharing a palette still read as five screens. What makes them one
instrument is a shared skeleton, and it is enforced by tests rather than by
discipline:

- **One grid.** `col_x(i)`, `row_y(n)`, one margin, one gutter. A value in the
  left column sits at the same x on every screen, so switching screens does not
  move the furniture. A test asserts every region starts on a grid column.
- **One type scale.** Hero, primary, value, label - four sizes, used the same
  way. A test asserts nothing draws at a size outside it.
- **A status strip on every screen.** Screen name on the left, charge and link
  health on the right, always in the same place. You never lose your bearings.
- **Page dots.** Which of the set you are on, so the screens read as a sequence.
  A test asserts the lit dot follows the position.

The pair that proves it: the ride screen and the lifetime screen show different
timescales of the same six ideas, in the same two columns, in the same order.

## Proposed layout, 240×320 portrait

```
┌────────────────────────────┐
│ ▏                       ⚡3 │  mode block (Puck gear), top right
│ ▏                          │  left edge: speed arc, sweeps
│ ▏      2 8                 │  hero speed, snaps
│ ▏         km/h             │
│ ▏                          │
│ ▏  ◀━━━━━━╋━━━━━━━━━▶      │  power flow: regen ◀ cyan | amber ▶ drive
│ ▏                          │
│  ████████████░░░░░░  68%   │  battery, colour-ramped, segmented
│  32 km range               │
│                            │
│  FET 42°   MOT 48°  12.4Ah │  dim until abnormal, then coloured
└────────────────────────────┘
│        FAULT: DRV          │  full width, red, only when real
└────────────────────────────┘
```

Everything above is drawn from regions the differential renderer already
understands, so a redesign does not cost a rewrite.

## What still needs building

**A real font.** The device ships `glcdfont` — an 8×8 bitmap scaled by integers,
which is why the stock display looks like 2013. Nothing stops us rendering a
modern face to a bitmap offline and shipping it as data; that is the single
biggest visual upgrade available and it is a build-time job, not a runtime one.

**Arc and segment primitives.** Drawing an arc as a series of `fill_rectangle`
spans, precomputed at build time so the device does no trigonometry.

**The stock capture, finished.** `capture/capture.py` records what the stock
screens draw — useful as a reference baseline. It currently gets the chrome;
`ScreenValues.update` still needs the module-level `VESCS` populated rather than
a list passed in.
