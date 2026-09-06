# Known issues

## COMM_FORWARD_CAN to a second motor is unverified

The DAVEGA discovers devices by sending `COMM_FORWARD_CAN` (34) with an inner
`COMM_FW_VERSION` to each CAN id in turn. Observed live: it probes ids
sequentially (`dbg-fwid` was 10 when sampled), and ids with no device behind them
never reply. That accounts for most of the gap between frames in and replies out,
and is expected rather than broken.

For a real second motor, the firmware handles it locally on dual-motor hardware:

```c
case COMM_FORWARD_CAN: {
    send_func_can_fwd = reply_func;
#ifdef HW_HAS_DUAL_MOTORS
    if (data[0] == utils_second_motor_id()) {
        mc_interface_select_motor_thread(2);
        commands_process_packet(data + 1, len - 1, reply_func);   // same reply_func
        mc_interface_select_motor_thread(1);
    } else {
        comm_can_send_buffer(data[0], data + 1, len - 1, 0);
    }
#endif
} break;
```

Because it reuses the same `reply_func`, the reply *should* return through
`event-cmds-data-tx` and be patched normally. **This has not been confirmed on
hardware** — the display stopped polling before a forward to the real second
motor id could be captured. Treat dual-motor telemetry as unproven.

If you can test this, the counters to watch are `dbg-fw124` (forwards aimed at
the real second motor) and `dbg-fwmax` (highest id probed).

## The display needs a restart after reloading the shim

Reloading the script re-runs `uart-start` mid-session. The DAVEGA drops to its
error screen and waits for a button press. Expect to press a button on the
display after every upload.

## Speed reads from one motor

Speed is a single value derived from one motor's ERPM, gear ratio and wheel
diameter — it is not summed across motors. Spinning one wheel by hand only moves
the reading if it is the motor that owns the calculation. On the ground both
wheels turn together and it reads correctly.

## Reply rate sits around 70%

See the CAN scan above. A rate near 100% would actually be surprising.

## Battery current is set conservatively pending pack confirmation

The reference board runs `l_in_current_max 30` / `l_in_current_min -8` per side
(60 A / -16 A total) rather than the 45 / -12 the 12s6p formula gives, because
the pack size is not confirmed from a label.

Rationale: if the pack is 6P, 45 A/side is exactly at cell spec and dropping to
30 costs only top-end power. If it is 4P, 45 A/side is ~22.5 A per cell against
a ~15 A rated cell. The asymmetry favours the conservative number until the pack
is read. Low-speed torque is unaffected either way - that comes from motor
current, which stays at 80 A/side.

Formula for reference (dual motor, per ESC):
    battery max   = (parallel groups x 15) / 2
    battery regen = (parallel groups x -4) / 2

## uart-start PERMANENTLY flashes app_to_use = APP_NONE

The single most important thing to know before running any LispBM script that
calls `uart-start` on an ESC.

From `bldc/lispBM/lispif_vesc_extensions.c`, `ext_uart_start`:

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

So with `app_to_use` set to **UART (3)**, **PPM and UART (4)** or **ADC and UART
(5)**, calling `uart-start` **silently and permanently disables your input app**.
A reboot does not restore it — the stored value is now `APP_NONE`, and only a
config write brings it back. On a skateboard that is a dead throttle.

**Use `app_to_use = 1` (PPM only).** `APP_PPM` is not in that branch, so the
setting is left untouched and the PPM decoder keeps running alongside the shim.
Verified on hardware: with `app_to_use = 1` and the proxy running, the PPM
decoder reads a live 1.4990-1.5020 ms pulse; with `4`, it reads 0.0000.

This also explains a symptom that is easy to misdiagnose: config writes appearing
not to persist. They persisted fine — the next `uart-start` overwrote them.

## PPM sub-config writes need ctrl_type to be non-zero

While `app_ppm_conf.ctrl_type` is `0` (control type "None"), writes to the PPM
block do not stick. Top-level appconf fields persist normally throughout. Once
`ctrl_type` is a real control type, XML writes to the same block work and survive
a reboot.

LispBM offers a way in when you are stuck there, since `conf-set` reaches a
subset of PPM parameters and `conf-store` persists them:

```clj
(conf-set 'ppm-ctrl-type 3)        ; Current No Reverse With Brake
(conf-set 'ppm-ramp-time-pos 0.3)
(conf-store)
```

Exposed: `ppm-ctrl-type`, `ppm-hyst`, `ppm-pulse-start/end/center`,
`ppm-ramp-time-pos/neg`, and `app-to-use`. Traction control is not among them.
`tools/fix-ppm.lisp` does this and reports before/after values via globals.

## Battery current is set conservatively pending pack confirmation

The reference board runs `l_in_current_max 30` / `l_in_current_min -8` per side
(60 A / -16 A total) rather than the 45 / -12 the 12s6p formula gives, because
the pack size is not confirmed from a label.

Rationale: if the pack is 6P, 45 A/side is exactly at cell spec and dropping to
30 costs only top-end power. If it is 4P, 45 A/side is ~22.5 A per cell against
a ~15 A rated cell. The asymmetry favours the conservative number until the pack
is read. Low-speed torque is unaffected either way - that comes from motor
current, which stays at 80 A/side.

Formula for reference (dual motor, per ESC):
    battery max   = (parallel groups x 15) / 2
    battery regen = (parallel groups x -4) / 2

## Writing PPM config needs the PPM app in a working state first

An earlier version of this document claimed the nested `app_ppm_conf` block
could not be written via XML at all. **That was wrong** and is corrected here.

What actually happens: while `app_ppm_conf.ctrl_type` is `0` (control type
"None"), writes to the PPM block do not stick — `loadXml` loads them into memory
correctly, `setAppConf` sends them, and the ESC reads back defaults. Top-level
appconf fields (`app_to_use`, `can_status_msgs_r1`, `controller_id`) persist fine
throughout.

Once `ctrl_type` is set to a real control type, XML writes to the same block work
and survive a reboot.

**The way out is LispBM**, which exposes a subset of PPM parameters to `conf-set`
and can persist them with `conf-store`:

```clj
(conf-set 'ppm-ctrl-type 3)        ; Current No Reverse With Brake
(conf-set 'ppm-ramp-time-pos 0.3)
(conf-set 'ppm-ramp-time-neg 0.2)
(conf-store)
```

Exposed PPM params: `ppm-ctrl-type`, `ppm-hyst`, `ppm-pulse-start`,
`ppm-pulse-end`, `ppm-pulse-center`, `ppm-ramp-time-pos`, `ppm-ramp-time-neg`,
plus `app-to-use`. Traction control is **not** among them — but once ctrl_type is
sane, the XML path handles it.

`tools/fix-ppm.lisp` does this and reports before/after values in globals.

Why it matters: `ctrl_type = 0` leaves the remote decoding but never driving the
motors, which presents as a dead throttle, and in that state you cannot configure
your way out through the normal path.

## Traction control does NOT affect braking (correcting common advice)

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
disengages itself on any fault and only re-engages once wheel speeds converge:

```c
if (mc_interface_get_fault() != FAULT_CODE_NONE) { autoTCdisengaged = true; }
```

What TC actually does is taper drive current linearly, reaching **zero** current
at `tc_max_diff`:

```c
current_out = utils_map(diff, 0.0, config.tc_max_diff, current, 0.0);
```

So `tc_max_diff` is a wheel-speed *difference* in ERPM at which that motor is cut
entirely. Convert it for your board before choosing a value:

    km/h = tc_max_diff / pole_pairs / gear_ratio * pi * wheel_dia * 60 / 1000

On the reference board (7 pole pairs, 4.2:1, 0.2 m) the default 3000 is only
~3.8 km/h, which is tight for surfaces where some slip is normal - the symptom is
power surging, not a crash. 6000 (~7.7 km/h) is the value in use here for grass.
