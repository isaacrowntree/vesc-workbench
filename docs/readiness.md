# Can we drop the DAVEGA proxy yet?

**No. Three things are missing, and one of them is load-bearing.**

The proxy exists to let the *stock* display app talk to a firmware-7 ESC. Our
own dashboard would make it unnecessary, because the version gate lives in
`frozen/run_standard.py` — the stock app — and `VescComm` has no version check
of its own. So the plan is sound. It is just not finished.

## What is ready

| | |
|---|---|
| Five screens, ten themes | ✅ rendering on the real panel |
| State machine: sweep → screen ↔ menu | ✅ one `tick()`, animation-aware |
| Port layer to the real display | ✅ `screens/device.py`, native 3x5 font |
| Conversions | ✅ pinned to the display's own `frozen.screen_values` |
| Cost model | ✅ measured: 23-29 ms settled, 472-763 ms full paint |
| Contrast | ✅ enforced, 4.5:1 / 7:1 |
| Flight recorder to replace the proxy | ✅ written and tested |
| 394 assertions | ✅ green |

## What is missing

### 1. Live telemetry — written, not yet run on hardware

I spent an evening guessing at `VescComm`'s undocumented signatures. That was
the wrong move: **the protocol is documented in the DAVEga source**, which is
open (GPL-3.0), and reading it took ten minutes.

`screens/vesc.py` now does the whole job itself:

```
request  02 01 04 40 84 03      start, len, COMM_GET_VALUES, crc16, stop
reply    02 <len> 04 <payload> <crc-hi> <crc-lo> 03
```

Field offsets are lifted from `vesc_comm_standard.cpp` rather than derived, and
the tests build a reply the way an ESC would and assert every field reads back
exactly what went in — the check that matters, because a field read from the
wrong offset still produces a plausible number. Bad packets are refused rather
than half-read.

Two things that fell out of reading properly:

- The computed CRC over the payload `[0x04]` is `0x4084`, which is exactly the
  constant in their request packet. Independent confirmation that the framing
  is right.
- **A FOCBOX Unity answers with both motors in one packet**, at its own offsets,
  which the display averages. That is a question I had left open. A Unity on
  firmware 7 speaks the standard layout and the second motor comes over CAN,
  which is what our proxy counters already showed.

What remains is to run it against the ESC. Nothing about it is speculative any
more; it is untested, which is a different thing.

### 2. Buttons are not wired to hardware

`App.press()` takes `"up"` / `"down"` / `"enter"` / `"hold"` and is fully
tested, but nothing reads `frozen.buttons` yet. Until it does, the screens can
be driven from a laptop and not from the deck.

### 3. There is no persistent app

`exec_custom_start` runs a user `start.py` before `boot_fw`, so ours can take
over — but no such file exists. The renderer is driven from the host over
WebREPL. Power-cycle the board and the stock app comes back.

## The order to do them in

1. **Telemetry.** Try `get_values(0)`. If that fails, `make lisp-stop`, retry,
   then `make motors-on` to restore the proxy either way.
2. **Buttons**, once there is something worth pressing them on.
3. **`start.py`**, last — it is the point of no return for the stock app, and
   should not be written until the first two work.

Only after those three is the proxy safe to replace with
[the flight recorder](../davega-shim/lisp/logger.lisp).

## Testing the new views before then

The views can be exercised today without dropping anything: upload the modules
to `/gui/` and drive them from the host with injected frames. That is how every
number in the cost model was measured. It proves rendering, layout, themes and
timing — everything except that the numbers are real.
