# Contributing

The most useful contributions are **board profiles** and **confirmations on
hardware other than a FOCBOX Unity**, which is the only ESC this has run on.

## Adding a board profile

Copy `vesc/profiles/nazare-unity.mk`, edit it, and open a PR. Include in the header
comment: ESC, firmware version, motors, drive ratio, wheel size, battery, remote
and display.

Profiles hold connection details and the second motor's CAN id. They deliberately
do **not** hold motor tuning — current limits, gearing and detection results are
specific to your hardware, and copying someone else's is a good way to damage a
motor or a pack. Run the detection wizard.

## Changing the Lisp

Tests first, please:

```sh
make test-lisp     # runs the shipped script in the upstream LispBM REPL
make test          # everything
```

`lisp/tests/` runs the **real** script, not a transcription of it, and asserts
the framed bytes against offsets taken from DAVEga's own parser. Both the
readable source and the minified artifact are tested, so golfing cannot silently
change the wire format.

Upload happens in 384-byte chunks with a 1-second per-chunk timeout, so size
matters. `lisp/minify.py` strips the script before upload; keep an eye on
the chunk count it prints.

### LispBM gotchas that have already bitten

- **Symbols are case-insensitive.** A function named `W` collides with an alias
  `w` and will silently recurse.
- **`(crc16 arr optLen)` takes no start offset** — it always begins at index 0.
  Build the payload in its own buffer.
- **`(uart-write arr)` takes no length** and writes the whole array. Resize the
  buffer to the exact frame length first.
- **`(uart-read arr num optOffset optStopAt optTimeout)`** — the timeout is the
  *fifth* argument. Putting it fourth sets a stop-character and leaves the
  timeout at 0.
- **`(member elem list)`** takes the element first.

## Testing against hardware

You need VESC Tool on a phone connected over BLE with the TCP bridge active, and
desktop VESC Tool closed. `make check` verifies both.

Never leave a board in an untested state after writing config. `make apply`
reads back and verifies for this reason — and after a reboot, **wait for the ESC
to settle before reading**, or you will capture transient values that look like
corruption.

## Safety

This project writes motor controller configuration and can disable or enable
motor output. Wheels off the ground for anything involving `app-disable-output`,
detection, or app configuration. Verify the throttle behaves before riding.
