# The DAVEGA shim

## Problem

A DAVEGA X on VESC firmware 7 shows:

> supported vesc firmware versions 5.x to 6.x - press any button to restart

DAVEGA development stopped in 2023 (last firmware v5.06); the shop closed in
May 2024 and the DAVEGA X firmware was never open-sourced, so there is no
official or community fix.

## Why it is fixable

`tests/protocol-diff.sh` diffs bldc `6.00` against `master`. The
`COMM_GET_VALUES` payload is byte-identical (25 fields, same types and order)
and the fields DAVEga reads sit at identical offsets.

The `COMM_FW_VERSION` **response is not structurally identical**: 7.x appends a
`buffer_append_uint32(send_buffer, main_calc_hw_crc(), &ind)` that 6.00 does not
have (added upstream in `38f44a7227`). It does not break the shim - DAVEga reads
major/minor at fixed offsets 1-2 and the length byte covers the extra bytes - but
the earlier claim of an identical structure was wrong, and
`tests/protocol-diff.sh` missed it because its grep only matched
`send_buffer[ind++]`, `memcpy` and `strcpy`, not `buffer_append_*`.

The display parses fine. It refuses to talk, on two bytes.

## Design

```
DAVEGA ──UART──> [ LispBM proxy ] ──cmds-proc──> VESC firmware
                        │                              │
                        └──── patch FW_VERSION ─────────┘
                             (report 6.00) then uart-write
```

`cmds-proc` hands bytes to the firmware's real packet decoder; replies arrive
framed on `event-cmds-data-tx`. The proxy rewrites the two version bytes and
recomputes the CRC. Everything else passes through untouched, so commands we
have never seen still work.

## Three things that made it hard

**Blocking-thread commands.** `62, 66-72, 80, 83, 90, 116, 125, 158` are
deferred to a blocking thread and reply via `send_func_blocking`, never
`event-cmds-data-tx`. Forwarding them produces no response *and* leaves
`is_blocking` set, which can wedge later commands. They are intercepted;
`COMM_PING_CAN` is answered with a precomputed constant frame.

**Frame alignment.** Reading arbitrary UART chunks means the buffer rarely
starts on a frame boundary. `cmds-proc` tolerates that; command *inspection*
does not. Reading header-then-payload took the reply rate from ~6% to ~70%.

**`uart-start` stops the app owning the UART pins.** "PPM and UART" is one
combined app, so running the shim with `app_to_use = 4` takes the PPM decoder
down too and you lose throttle — and stopping the script does not bring it back,
only a reboot or config write does. **Use `app_to_use = 1` (PPM only).**

## LispBM gotchas found the hard way

- Symbols are **case-insensitive**: a function `W` collides with an alias `w`
  and silently recurses.
- `(crc16 arr optLen)` takes **no start offset** — build the payload in its own
  buffer.
- `(uart-write arr)` takes **no length** and writes the whole array — resize to
  the exact frame length first.
- `(uart-read arr num optOffset optStopAt optTimeout)` — timeout is the **fifth**
  argument.
- `(member elem list)` takes the element first.

Each of these was caught by the test suite before reaching the board, except the
last two which were caught by instrumenting the script and reading its globals.

## Verifying

```sh
make davega-debug SECS=60
```

Reports frames in/out, malformed frames, command mix and a verdict. A reply rate
around 70% is expected: the DAVEGA scans CAN ids by forwarding
`COMM_FW_VERSION` to each, and ids with no device never answer.
