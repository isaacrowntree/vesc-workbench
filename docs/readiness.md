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

### 1. Live telemetry — blocking

Every screen still draws an injected frame. `VescComm(uart, False)` constructs,
the pins are tx 16 / rx 17, and `get_values(can_id)` sends — but the ESC does
not answer.

Until this works, dropping the proxy makes the display strictly worse than it
is today: the stock app would refuse firmware 7 and ours would show frozen
numbers.

Untested hypotheses, cheapest first:

- `get_values` may want a **list index**, not a CAN id. `VESCS` is a list and
  the argument is compared against an int; 0 and 1 have not been tried.
- The **LispBM proxy owns the ESC's UART**. It answers the stock app's polling,
  so the link works; whether it also answers an unsolicited request from a
  second reader is unknown. `make lisp-stop` tests this reversibly.
- The display's UART may need `swap_tx_rx` true rather than false.

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
