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

## What actually sets the DAVEGA's refresh rate

Measured on a Unity: 12.3 frames/s in, 10.1 replies/s out, of which ~5.1/s are
telemetry for each of the two motors. The display alternates between the local
side and the second motor almost exactly 1:1.

So each motor's numbers refresh about five times a second, and that is not the
shim's ceiling - LispBM sat at 5.5% CPU. The DAVEGA has its own
`update_interval_ms` setting in `/config.json` ([davega-x](davega-x.md)), and
that is the thing to change if the readout feels slow.
