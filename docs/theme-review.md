# Are the themes fit for purpose?

A dashboard is read at speed, in sunlight, through a helmet, by someone whose
attention belongs on the path. "Looks good on a monitor" is not the bar. This
is what the ten themes were measured against, and what four of them failed.

## What was measured

| Property | Why it matters | Bar |
|---|---|---|
| Contrast of primary text vs its ground | The number you must read | 7:1 |
| Contrast of labels and semantic colours | Everything else | 4.5:1 |
| Separation of **warn** from **danger** | "Getting warm" must not look like "fault" | 20 |
| The same, **with deuteranopia** | Red and green are the pair that fails, and a green-amber-red charge ramp is the textbook case | 14 |
| Separation of **accent** from **ink** | If they match, nothing can be highlighted - "this value matters" becomes unsayable | 12 |

All five are now tests. A theme cannot regress past them.

## What failed, and why it mattered

**rosso** — `warn` and `danger` were the same red. Separation **0**. On the
screen that means the temperature going amber and the ESC faulting are
indistinguishable at a glance, which is exactly the moment a glance is all you
get. Warn is now amber (`#FFB43C`), keeping red for faults only.

**papaya** — orange `warn` against red `danger` measured 20 in normal vision
but **9.6 under deuteranopia**: for a red-green colour blind rider the warning
and the fault were the same colour. Danger is now pink (`#FF6BB0`), which
survives the simulation at 28 and differs in lightness as well as hue, so it
does not rely on colour perception alone.

**minimal** and **silver** — `accent` was identical to `ink`. Separation **0**.
A "minimal" palette that cannot emphasise anything is not minimal, it is
incomplete: the battery bar, the selected menu row and the charge readout all
had nothing to say. Minimal now accents with a cold blue (`#7FC4FF`), silver
with a steel blue (`#7FAAD8`), both chosen to clear contrast while staying in
character.

## Where the ten stand now

Six were already sound: **nevera** (60 / 52) and **motorsport** (45 / 64) have
the widest semantic separation, **toro** and **hybrid** are close behind, and
**nazare** - the default - sits comfortably clear on every measure.

The weakest passing theme is **silver**, at 21 / 21 / 20. It scrapes every bar
because restraint is its whole idea; that is a deliberate trade rather than an
oversight, and the tests keep it honest.

## What is still not measured

- **Sunlight.** Contrast ratios assume a viewer sees the panel's full range. A
  2.8" TFT in direct sun does not deliver it. Every theme here is dark-ground,
  which is right for dusk and wrong for noon - a light theme for daylight is a
  real gap.
- **Motion.** All of this is measured on a still frame. Whether a value stays
  readable while the deck vibrates is not something a contrast ratio answers.
- **The font.** Legibility is a property of letterforms as much as colour, and
  the device draws a 3x5 bitmap. The best palette in the world cannot fix a
  glyph you cannot resolve at a glance.
