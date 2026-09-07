# The ten layouts, against what the panel can do

The ten themes were designed as ten *layouts*, not ten palettes - a dial, a set
of rings, hexagonal shards, a shift-light rail. Today all ten render the Nazare
arrangement and only the colours change; every theme still declares its
`layout` in `themes.py` and nothing reads the field.

This is the feasibility check before building them: what each design needs,
what the display can actually be asked to draw, and what that costs. The
numbers below were measured on the board, not estimated.

## What the driver gives us

`frozen.ili934xnew.ILI9341` exposes `fill_rectangle`, `pixel`, `print`,
`chars`, `blit`, `writeblock`, `set_font`, `scroll`/`scrdef`/`scrset`, `erase`.

There is **no line, no circle, no polygon**. Every curve and every diagonal has
to be built out of something else.

| Primitive | Measured cost | Notes |
|---|---|---|
| `fill_rectangle` | **2.9 ms** per call | Independent of size. 100 8x8 fills and 100 1x8 fills cost the same. |
| `pixel` | **2.29 ms** per call | Not a cheap way to draw anything. 400 pixels is 914 ms. |
| `print` (8x8 char) | **8.6 ms** per character | Measured previously; unchanged. |
| `writeblock(x0,y0,x1,y1,buf)` | **12 ms for 240x40** | 9,600 px in one transfer - about 1.25 us/px. |
| Free heap | **98 kB** | A 200x100 RGB565 buffer (40 kB) **fails to allocate**. A 240x40 band (19 kB) leaves 77 kB. |

`framebuf` offers `line`, `hline`, `vline`, `rect`, `fill_rect`, `text`,
`blit`, `scroll`, `pixel` - but **no `ellipse`** on this build, so circles are
composed from lines either way.

## The consequence

Drawing a curve as one `fill_rectangle` per column is what the region model
does today, and for a curve it does not work:

    a 96 px-radius arc is ~170 columns  ->  481 ms   as rectangles
                                            914 ms   as pixels

Both are past the 900 ms full-repaint budget on their own, and 4x the 120 ms a
settled frame is allowed.

The way through is `writeblock`. Compose the curve into a `framebuf` band and
push the band in one transfer: a 240x40 band costs 12 ms, so a 200x200 dial
face pushed as five bands with one reused buffer is **~50-60 ms** plus the
framebuf drawing, which is C. That is affordable *once*, on a full repaint,
which is exactly what a dial face is: furniture.

What must stay cheap is the part that moves. A needle sweeping a circle has a
bounding box the size of the dial, so it cannot be a region in the current
sense. It has to be drawn as the **delta** - the arc between the old value and
the new - which is a handful of rectangles, the same trick the rail and the
flow meter already use.

## Verdict per layout

| Theme | Layout | Needs | Verdict |
|---|---|---|---|
| **Ghost** | `bare` | Rectangles and text | **Buildable today.** One enormous numeral and a hairline. No new primitive. |
| **Minimal** | `bare` | Rectangles and text | **Buildable today.** The cheapest of the ten to run. |
| **Nevera** | `flow` | Rectangles and text | **Buildable today.** The centre-zero power meter already exists - this is that idea given the top half. |
| **Motorsport** | `rail` | Rectangles, static slants | **Buildable today.** The slanted block edges are furniture, painted once. |
| **Hybrid** | `eco` | Centre-zero meter, arcs as furniture | **Buildable** once bands land. The moving part is a bar. |
| **Papaya** | `hairline` | Three thin arcs | **Buildable** once bands land. Arcs are furniture; only the readouts change. |
| **Rosso** | `dial` | Full analogue ring, sweeping redline | **Buildable, with the delta arc.** Face and ticks as bands on full repaint (~60 ms); the sweep redraws only the arc between old and new (~8-16 rectangles, 25-45 ms). Inside the settled budget. |
| **Toro** | `shards` | Hexagons, diagonal split, diagonal battery | **Buildable, with a delta bar.** Hexagons and the split are furniture. The diagonal battery cannot repaint all 208 columns (600 ms) - only the columns at the tip that changed. |
| **Silver** | `rings` | Concentric rings, one long red hand | **Buildable with a compromise.** Rings are furniture. A full-length hand means erasing and redrawing ~30-60 short rectangles a frame (90-180 ms), past the settled budget. Either the hand becomes an arc-tip marker, or this theme updates at a lower rate than the others. |

## What building them needs

1. **A band composer.** `framebuf` in, `writeblock` out, one reusable buffer
   sized to the largest band (240x40 = 19 kB, which fits). This is the single
   new capability the curved layouts depend on, and it has to exist in the
   harness too or the mockups will promise what the panel cannot do.
2. **Delta drawing for anything that sweeps.** An arc or a diagonal bar redraws
   the difference between two values, never the whole shape.
3. **A layout hook on the theme.** `layout` is already declared and already
   ignored; the region model takes a per-layout arrangement almost directly.

The nine are all reachable. Six need nothing that does not exist; three need
the band composer, and one of those three (Silver's hand) needs its design
softened or its refresh rate lowered - the only place where the original
drawing asks for something the panel will not give at speed.
