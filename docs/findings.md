# Findings

Firmware behaviour that cost time to work out. **The tooling in this repo
already handles the first two** — they are here because you will hit them the
moment you write your own scripts, and because the symptoms point somewhere
else entirely.

## uart-start permanently flashes app_to_use = APP_NONE

The single most important thing to know before running any LispBM script that
calls `uart-start`. From `bldc/lispBM/lispif_vesc_extensions.c`, `ext_uart_start`:

```c
app_configuration *appconf = mempools_alloc_appconf();
conf_general_read_app_configuration(appconf);
if (appconf->app_to_use == APP_UART ||
        appconf->app_to_use == APP_PPM_UART ||
        appconf->app_to_use == APP_ADC_UART) {
    appconf->app_to_use = APP_NONE;
    conf_general_store_app_configuration(appconf);   // written to FLASH
    app_set_configuration(appconf);
}
```

With `app_to_use` set to **UART (3)**, **PPM and UART (4)** or **ADC and UART
(5)**, calling `uart-start` silently and permanently disables your input app. A
reboot does not restore it — the stored value is now `APP_NONE`, and only a
config write brings it back. On a skateboard that is a dead throttle.

It also explains a symptom that is easy to misdiagnose: config writes appearing
not to persist. They persisted fine — the next `uart-start` overwrote them.

> **Now live again.** With the DAVEGA proxy retired, `app_to_use` is back to
> **4 (PPM and UART)** so the ESC answers telemetry with its own firmware
> rather than through a Lisp shim. That re-arms this hazard: any LispBM script
> that calls `uart-start` will silently kill the throttle. The flight recorder
> does not touch the UART, and the guard below still stands.
>
> **Handled.** `make upload-lisp` checks the script for `uart-start` and reads
> `app_to_use` before uploading. The firmware is going to clear that value
> either way, so the tooling moves it somewhere sane first: **4 → 1** (PPM only)
> and **5 → 2** (ADC only). `3` is UART-only, where `APP_NONE` is the honest
> result, so it is left alone.

Verified on hardware: with `app_to_use = 1` and the proxy running, the PPM
decoder reads a live 1.4990–1.5020 ms pulse; with `4`, it reads 0.0000.

## PPM config writes need ctrl_type to be non-zero first

While `app_ppm_conf.ctrl_type` is `0` (control type "None"), writes to the PPM
block do not stick: `loadXml` loads them correctly, `setAppConf` sends them, and
the ESC reads back defaults. Top-level appconf fields (`app_to_use`,
`can_status_msgs_r1`, `controller_id`) persist fine throughout. Once `ctrl_type`
is a real control type, XML writes to the same block work and survive a reboot.

This matters because `ctrl_type = 0` leaves the remote decoding but never driving
the motors — a dead throttle you cannot configure your way out of by the normal
route.

> **Handled.** `make apply-appconf` reads `ctrl_type` first and, if it is `None`,
> does a priming write to establish a control type before applying the real
> config.

If you are doing it by hand, LispBM is the way in: `conf-set` reaches a subset of
PPM parameters and `conf-store` persists them.

```clj
(conf-set 'ppm-ctrl-type 3)        ; Current No Reverse With Brake
(conf-set 'ppm-ramp-time-pos 0.3)
(conf-store)
```

Exposed: `ppm-ctrl-type`, `ppm-hyst`, `ppm-pulse-start/end/center`,
`ppm-ramp-time-pos/neg`, and `app-to-use`. Traction control is not among them —
but once `ctrl_type` is sane, the XML path handles it. `tools/fix-ppm.lisp` does
this and reports before/after values via globals.

## Traction control does not affect braking

A widely repeated warning is that VESC traction control is dangerous under
braking because "if one wheel stops spinning, they all stop spinning". For the
**PPM app** that is not what the firmware does. From `applications/app_ppm.c`:

```c
if (current_mode_brake) {
    mc_interface_set_brake_current(fabsf(current));
    comm_can_set_current_brake_rel(msg->id, fabsf(servo_val));   // no TC
} else {
    ... traction control lives entirely in this branch ...
}
```

TC sits exclusively in the non-brake branch, so braking is unaffected. It also
disengages on any fault and only re-engages once wheel speeds converge:

```c
if (mc_interface_get_fault() != FAULT_CODE_NONE) { autoTCdisengaged = true; }
```

What it actually does is taper drive current linearly, reaching **zero** at
`tc_max_diff`:

```c
current_out = utils_map(diff, 0.0, config.tc_max_diff, current, 0.0);
```

So `tc_max_diff` is a wheel-speed *difference* in ERPM at which that motor is cut
entirely. Convert it for your board before choosing a value:

    km/h = tc_max_diff / pole_pairs / gear_ratio * pi * wheel_dia * 60 / 1000

On the reference board (7 pole pairs, 4.2:1, 0.2 m) the default 3000 is only
~3.8 km/h, which is tight for surfaces where some slip is normal — the symptom
is power surging, not a crash. 6000 (~7.7 km/h) is the value in use here for
grass.

## A UART hands you what has arrived, not what you asked for

The proxy's original read loop asked for both frame header bytes in one call and
treated a short payload read as a corrupt frame. Both cost whole request/reply
round trips, which the DAVEGA showed as a readout updating in lurches.

`tests/lisp/test_reader.lisp` drives the real reader through a fake UART that
can split a header across reads. Against the old loop, one 1-byte short read at
the head of a 10-frame stream lost **all ten frames**.

> **Fixed.** The reader hunts for the start byte one byte at a time, and `rdn`
> accumulates until the requested count arrives or the line goes quiet.

`make davega-debug` reports `resync skips` and a `telemetry rate` in commands per
second — what the display actually refreshes at. A healthy Unity sits well above
3/s. Some slowdown is inherent, since the proxy adds a LispBM round trip the
native UART app does not have, but it should not be visible.

## COMM_FORWARD_CAN to a second motor works

Previously listed as unverified. Confirmed on hardware from the proxy's own
counters, over a single uptime on a FOCBOX Unity with the DAVEGA polling:

```
dbg-in     3227      frames read from the display
dbg-out    2641      replies forwarded
dbg-c50    1319      GET_VALUES_SELECTIVE, local side
dbg-fw124  1320      FORWARD_CAN aimed at the real second motor
dbg-c51       1
dbg-c0        1
```

`1319 + 1320 + 1 + 1 = 2641`, exactly `dbg-out`. **Every answerable request was
answered**, including every forward to the second motor — so a reply to a
`COMM_FORWARD_CAN` does come back through `event-cmds-data-tx` and gets patched
like any other, as the firmware source suggested it would.

The remaining 586 frames are the display's CAN discovery scan (`dbg-fwmax` 173),
probing ids with nothing behind them. Those cannot be answered by anyone, which
is why a "reply rate" below 100% is the healthy state rather than a defect.

## What the framing fix costs, measured

The safe reader is not free. Measured on a Unity over three 40-45s windows each,
with the same display polling the same board:

| Reader | Frames in | Telemetry | LispBM CPU |
|---|---|---|---|
| Original (one 2-byte header read, short reads ignored) | 12.3/s | 5.1/s | 5.5% |
| Byte-at-a-time start hunt | 11.3/s | 4.5/s | 7.9% |
| 2-byte fast path, explicit recovery | 11.8/s | 4.8/s | 7.3% |
| **Current** (as above, plus one read for the frame body) | **12.0/s** | **5.0/s** | **5.6%** |

The byte-at-a-time version was correct and needlessly slow: it paid an extra
UART call on every frame to defend against a case that happens rarely. The
current reader keeps the single 2-byte header read as the fast path and handles
both misalignments explicitly, recovering most of the difference.

The last row is the interesting one. `tests/lisp/bench_reader.lisp` runs
candidate readers over the same wire and counts UART calls, which is what the
interpreter actually pays for. It showed the shipped reader spending **three
reads per frame** - header, payload, then crc and stop byte - when the length
byte already says how much is coming. Fetching the frame body in one call takes
that to **two reads per frame**, a third fewer:

```
A three reads   frames=20 replies=20 uart-reads=100
B two reads     frames=20 replies=20 uart-reads=80
C two + fast    frames=20 replies=20 uart-reads=80
```

Candidate C also skips `rdn`'s accumulating loop when the first read already
delivered everything, which the bench cannot count but the board can: on
hardware it came out at **5.6% CPU**, below the original unsafe reader's 5.5%
within measurement noise, with the framing guarantees intact.

So the safety did not have to cost anything. It cost something only while the
reader was doing more UART calls than the protocol requires.

Note that no desync was observed on this board either before or after:
`dbg-bad` was 0 throughout and every answerable request was answered. The fix
is insurance, not a cure for something that was happening.

## What actually sets the DAVEGA's refresh rate

Measured on a Unity: 12.3 frames/s in, 10.1 replies/s out, of which ~5.1/s are
telemetry for each of the two motors. The display alternates between the local
side and the second motor almost exactly 1:1.

So each motor's numbers refresh about five times a second, and that is not the
shim's ceiling - LispBM sat at 5.5% CPU. The DAVEGA has its own
`update_interval_ms` setting in `/config.json` ([davega-x](davega-x.md)), and
that is the thing to change if the readout feels slow.

## Traction control, confirmed in motion

Enabled with `tc_max_diff` 6000 (~7.7 km/h of wheel-speed difference on the
reference board's 7 pole pairs, 4.2:1 gearing and 0.2 m wheels), ridden hard on
grass at a golf course. It works, and it does not intrude.

That closes the loop on the [braking
correction](#traction-control-does-not-affect-braking): the widely repeated
warning describes behaviour the PPM path does not have, and riding it bears
that out. The default 3000 would have been about 3.8 km/h, tight enough that
normal grass slip would keep triggering the taper — which is the "power
surging" people describe, and probably where the folklore comes from.

## Reloading the shim does not disturb the display

Previously listed as an issue: reloading the script re-runs `uart-start`
mid-session, so the expectation was that the DAVEGA would drop to its error
screen and need a button press after every upload.

It does not. Observed across repeated `make motors-on` uploads with the display
attached and running: the UART blips, the display re-handshakes, the proxy
answers `COMM_FW_VERSION` with 6.00 as it always does, and telemetry resumes on
its own. No button press needed.

## Speed reading from one motor is a display setting

Previously listed as a limitation: speed is derived from one motor's ERPM, so
spinning the other wheel by hand moves nothing.

That is a DAVEGA setting, not a constraint. Firmware v5.06 added
**`rpm_from_esc2`** — "RPM from ESC 2" in the display's Experimental Settings
menu, and a key in `/config.json`. The changelog entry is "optionally read RPM
from second ESC"; the string is absent from v5.01 and present in v5.06, which
dates it exactly.

It was always plausible that the display had the data: the proxy counters show
it polling both motors almost exactly 1:1 (1319 local, 1320 forwarded to CAN
124). It was only ever a question of which one it used for the calculation.

## The DAVEGA's boot order, and why start.py is safe

`frozen/main.py` names its boot steps in order:

```
load_license_key
is_button_press_and_hold
should_factory_reset
maybe_factory_reset
maybe_webrepl
exec_custom_start
boot_fw
```

Two things follow, and both matter:

1. **`maybe_webrepl` runs before `exec_custom_start`.** WebREPL is entered
   before any user code executes, so a broken `start.py` cannot lock you out of
   the device. Hold UP+DOWN at boot and you get a REPL regardless of what you
   left on the filesystem.
2. **`exec_custom_start` runs before `boot_fw`.** User code runs before the
   application starts — which is exactly the ordering the [version-gate
   patch](davega-x.md#can-you-patch-the-version-gate-itself) needs to work.

## The pack is 12s4p, and the cautious limit was the right one

Battery current was set to **30 A / -8 A per side** (60 / -16 total) while the
pack size was unconfirmed, rather than the 45 / -12 a 6P pack would allow. The
reasoning was asymmetric risk: if the pack were 6P, 30 A/side costs only
top-end power; if it were 4P, 45 A/side would be roughly 22.5 A per cell against
a ~15 A rated cell.

The pack is **12s4p**. Running the formula for 4P:

```
battery max   = (4 x 15) / 2 = 30 A per side
battery regen = (4 x -4) / 2 = -8 A per side
```

Which is exactly what was already set. The conservative choice was not merely
safe, it was correct — and the 45 A/side figure would have been a real
over-draw, not a theoretical one.

Two independent things pointed at 4P before it was confirmed. The DAVEGA's own
`battery_mah` was **17000** — the 4P number — and had been set before any of
this work started, so it was not contaminated by our guess. Meanwhile the ESC's
`si_battery_ah` had been set to 25.5 from an assumption made in the same
session. When a device you have not touched disagrees with a value you entered
yourself, the device is usually the better witness.

`si_battery_ah` is now 17 on both sides. It affects range and consumption
reporting only; the current limits were already right.

## The 70-byte truncation was ours, not the ESC's

For a while the display could read the ESC but every reply arrived truncated at
70 of its 79 bytes, so the CRC could not be checked. The proxy looked guilty
and was, though not in the way expected.

Stopping it did not fix the truncation - it removed the replies entirely. Zero
bytes, not 70. Because `app_to_use` was **1 (PPM only)**, set months earlier
precisely so the LispBM proxy could own the UART, **nothing on the ESC was
listening to that port at all**. The 70 bytes had never come from the firmware;
they were the proxy answering, and truncating in its own reply path.

The fix is `app_to_use = 4`, so the ESC's own UART comms answer. Two things
made that safe only now: the proxy is gone, and the flight recorder that
replaced it never calls `uart-start`.

Worth noting how the write behaved: setting `app_to_use` alone read back as
unchanged, and setting it alongside a second field a moment later stuck. The
value was not being rejected - the read-back was racing the store.
