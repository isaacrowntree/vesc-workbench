# Ours vs theirs

A read of the open-source DAVEga firmware (`janpom/davega`, GPL-3.0) against
what we built, in both directions. Their code is the reference implementation of
this exact problem by the person who designed the hardware; ignoring it was a
mistake that cost an evening of guessing at signatures.

## What we took from theirs

| | |
|---|---|
| **The wire protocol** | `02 01 04 40 84 03`, and every field offset in `vesc_comm_standard.cpp`. Our CRC over `[0x04]` computes to `0x4084`, matching their constant - two independent confirmations the framing is right. |
| **`get_battery_current() * VESC_COUNT`** | Each ESC reports only its own draw. We were under-reporting pack current on a dual board by half. |
| **`UPDATE_DELAY = 50 ms`** | Their loop period, and the natural render cadence. We had guessed at telemetry rates. |
| **`COUNTER_RESET_TIME = 3000 ms`** | Their hold threshold. Ours was 600 ms - a shorter hold would eventually fire the reset gesture riders already have. |
| **`INPUT_PULLUP` / `LOW` means pressed** | Active low, confirmed from source rather than inferred from sn8ke. |
| **`heartbeat(duration_ms, successful_vesc_read)`** | Every screen is told, every pass, whether the read worked. We computed staleness in the runner and then never showed it. Now in the frame as `link_ok`, with an indicator on the riding screen. |
| **The Unity's packet shape** | A FOCBOX Unity answers with *both* motors in one reply at its own offsets, which they average. An open question for us until we read it. |

## What theirs has that ours does not

- **Configurable screen contents.** `t_screen_item` is an enum and a text
  screen takes a list of them, so a rider chooses what appears. Ours are fixed
  layouts. Worth adopting: our region model would take it almost directly.
- **`per_cell_voltage`, `use_fahrenheit`, `imperial_units`** as first-class
  display options. We have themes but not units.
- **It runs.** Theirs is a shipping product on real hardware; ours has never
  read a live number.

## What ours has that theirs does not

- **Differential rendering.** They repaint the screen on `update()`. We repaint
  only regions whose value changed, and within them only the character cells
  that differ - 754 ms down to 23 ms on the same panel. Their target was an
  ATmega with a small display; ours is a 240x320 where a full repaint is a
  third of a second.
- **A measured cost model.** ~2.7 ms per draw call, ~8.6 ms per character,
  pixels nearly free. Every budget in the tests is derived from that rather
  than from intuition.
- **Tests that run without hardware.** Golden images, region-overlap checks,
  per-field sweeps, differential-vs-full convergence, a scripted ride through
  the flight recorder, and a fake UART that dribbles bytes. Their firmware is
  tested by flashing it.
- **Themes and enforced contrast.** Ten palettes, and text colour must clear
  4.5:1 against its own ground - which failed on six of ten before it was a
  test.
- **An explicit state machine.** Sweep, screen, menu, with one `tick()` that
  reports whether another frame is owed, so animation is not the caller's
  problem.

## The honest summary

Their code is the better source of truth about the hardware and the protocol.
Ours is the better place to change a dashboard. The overlap is small: they
solved talking to a VESC, we are solving drawing on this particular screen
quickly and provably.

Every hour spent guessing at something their source already answers is an hour
wasted, and that has now happened twice.
