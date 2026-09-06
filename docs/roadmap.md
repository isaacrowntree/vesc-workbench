# Roadmap

Four threads, in dependency order. Thread 2 is gated on a question that is one
command away from being answered; the rest are independent.

---

## 0. The gating question

Everything about repurposing the LispBM depends on one thing: **can the DAVEGA's
version gate be patched from `start.py`?**

We know the shape of it now. `frozen/run_standard.py` exposes
`is_compatible_vesc_version` and `assert_compatible_vesc_version` as ordinary
module-level functions — confirmed live on the device, not inferred. We know
`exec_custom_start` runs before `boot_fw`, so user code executes before the app
starts. And we know `maybe_webrepl` runs before both, so a broken `start.py`
cannot lock us out.

What we do not know is whether the call site resolves those names through the
module at call time or holds its own reference. Rebinding works in the first
case and is a no-op in the second.

**Test:** upload `davega-shim/webrepl/start.py`, reboot with the ESC on
firmware 7, see whether the display talks. Half an hour, fully reversible.

If it works, the proxy shim becomes optional and thread 2 opens up. If it does
not, the shim stays and thread 2 is limited to what a second LispBM context can
do alongside it.

---

## 1. A 2026 GUI for the DAVEGA

### What is actually possible

The stock app is frozen bytecode; it cannot be edited. But it does not need to
be. `start.py` runs before `boot_fw`, and sn8ke proves an app can take the
screen completely. The device gives us:

- `frozen.display` — `DISPLAY`, an ILI9341 at 240×320
- `frozen.colors`, `frozen.image` (`.pic` assets), `frozen.buttons`
- `frozen.vesc_comm`, `frozen.vesc_data` — the telemetry layer, reusable
- MicroPython 1.14, 512 kB RAM, ~4 MB flash

So a custom UI is a `start.py` that owns the screen and drives
`frozen.vesc_comm` itself. Falling back to the stock app is deleting one file.

### The hard part is testing, not drawing

Iterating a GUI by uploading and squinting at a 2.8" screen is not a workflow.
The harness matters more than the first screen does.

**Host-side renderer.** Stub `frozen.display` with a shim that records draw
calls and rasterises them to PNG at true 240×320. Screens become pure functions
of a telemetry snapshot, so a test is: given this `vesc_data`, render, compare
against a golden PNG. Runs in CI with no hardware, catches layout regressions,
and makes review a diff of images.

**Draw-call budget.** The same recording shim counts operations per frame. A
screen that needs 400 `fill_rectangle` calls will be slow on an ESP32 whatever
it looks like, and that is knowable on the host — the same trick as
`bench_reader.lisp`, which found a third of the UART calls were unnecessary.

**On-device timing.** `utime.ticks_ms` around the render, reported the way the
proxy reports counters, collected by `webrepl-run.py`. Gives a real frame time
to hold the host-side budget honest.

**Snapshot fixtures.** Capture real telemetry from the board with the existing
tooling and keep it as JSON. Every screen gets tested against the same
recorded ride: standstill, hard acceleration, regen, fault, low battery.

### Sequence

1. Display shim + PNG renderer + one golden test, no device involved.
2. Port the stock riding screen as a baseline — proves the harness and the
   telemetry path before any design work.
3. Redesign from there, with draw-call budgets enforced in CI.
4. On-device frame timing to confirm the host-side numbers.

---

## 2. Turn the LispBM into a logger

*Gated on thread 0.*

If the proxy is no longer needed, the LispBM context is free — and today
demonstrated exactly what to do with it.

**The problem it solves.** The ESC keeps faults only "since start". After the
golf-course ride the counters had already been zeroed by a reboot, so the one
event we most wanted to look at was gone. `make faults` reads what survives;
nothing preserves it.

**What to log:**

- Fault events with context — the ESC gives voltage, duty, RPM, tacho and
  current at the fault, which is what made today's `FAULT_CODE_DRV` readable as
  stationary rather than a ride event.
- High-water marks per session: max motor and battery current, max FET and
  motor temperature, min voltage under load. Derating and wheelspin feel alike
  to a rider and these tell them apart.
- **Traction control engagement.** Nothing currently reports whether TC ever
  intervened. A counter and a duty-cycle figure would have answered the "lost
  traction near the end" question directly, instead of leaving it to inference.

**Persistence is the design problem.** LispBM has globals, which survive until
reboot, and `conf-store`, which is for configuration and should not be abused as
a log. Options, cheapest first:

1. RAM ring buffer plus a `make log-pull` — loses everything on power-off, but
   covers "what just happened on that ride" if pulled before the next boot.
2. Write to the DAVEGA over the now-free UART, since the display has a
   filesystem and already persists odometers. Elegant, and only possible if the
   proxy is gone.
3. Custom firmware with a flash region. Out of scope.

Start at 1, design for 2.

---

## 3. Rewrite the journal post for what this became

The published post frames the project as a workbench with a display shim as its
origin story. That was accurate when written and is now the smaller half.

What changed: the DAVEGA stopped being a black box. Its firmware is
downloadable, its module structure is readable, its settings are a JSON file we
can edit, and its version gate has a name. The post should follow the shape of
the actual work — tooling, then archaeology, then what the archaeology bought.

Material worth using, all of it verified rather than asserted:

- The vendor is gone but the endpoints resolve, and there is a **v5.07rc3 dated
  2025-03-11** that was never announced.
- Pulling three firmware images to prove no version ever accepted VESC 7 —
  which is the honest justification for the shim existing at all.
- Two bytes in a version handshake, still the neatest part.
- The debugging story worth telling: the display "was not listening" because a
  USB-tethered phone shared 192.168.4.0/24 and won the default route. Ping
  worked, the port refused, and the device was innocent.
- The measurement discipline: a fix that made things slower, a bench that found
  a third of the UART calls were unnecessary, and numbers published for both.

Keep the existing correctness standard: quote the firmware's real strings,
link the real branch, and give figures rather than adjectives.

---

## 4. Reorganise the repo around what people came for

The repo currently reads as one project with a lot of surface. Most arrivals
want exactly one of three things.

### Proposed shape

```
vesc/        driving a VESC over the phone bridge - connecting, config,
             faults, PPM. Useful with no DAVEGA anywhere near it.
davega/      the display - the shim, the WebREPL tooling, the firmware
             archaeology, /data/config.json. Useful with any ESC.
lisp/        the LispBM development workflow - upload, test in the real
             interpreter, bench, minify.
docs/        findings, known issues, roadmap
profiles/    board profiles
```

### The README's job is routing

Three doors, stated in the first screen:

- *"I want to script my VESC without USB"* → `vesc/`, starting at
  `docs/connecting.md`
- *"My DAVEGA X refuses firmware 7"* / *"I want to change its settings"* →
  `davega/`
- *"I want to write LispBM without bricking something"* → `lisp/`

Each directory gets its own README that stands alone, so someone landing there
from a search never has to reconstruct the whole project.

### Also

- Split `Makefile` per area with a thin top-level include, so `make help` is
  readable rather than a wall.
- The `docs/findings.md` entries are mostly VESC firmware behaviour, and belong
  next to the code they warn about.
- CI already covers Python, Lisp and the protocol diff; add the GUI golden
  images when thread 1 lands.

### Sequence

Do this **after** thread 1 has a shape, or the GUI work lands in a layout that
is about to move.
