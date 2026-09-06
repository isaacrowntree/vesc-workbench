# Known issues

Open problems only. Things the tooling now handles for you are in
[findings.md](findings.md) — worth reading if you are writing your own scripts,
but you do not have to act on them.

## COMM_FORWARD_CAN to a second motor is unverified

The DAVEGA discovers devices by sending `COMM_FORWARD_CAN` (34) with an inner
`COMM_FW_VERSION` to each CAN id in turn. Ids with no device behind them never
reply, which is expected rather than broken.

For a real second motor the firmware handles it locally on dual-motor hardware,
reusing the same `reply_func`:

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

So the reply *should* come back through `event-cmds-data-tx` and be patched
normally. **This has not been confirmed on hardware.** Treat dual-motor
telemetry as unproven.

If you can test it, watch `dbg-fw124` (forwards aimed at the real second motor)
and `dbg-fwmax` (highest id probed) in `make davega-debug`.

## The display needs a button press after reloading the shim

Reloading the script re-runs `uart-start` mid-session, and the DAVEGA drops to
its error screen. Nothing to be done from this side — press a button on the
display after every upload.

## Speed reads from one motor

Speed is derived from one motor's ERPM, gear ratio and wheel diameter; it is not
summed across motors. Spinning one wheel by hand only moves the reading if it is
the motor that owns the calculation. On the ground both wheels turn together and
it reads correctly.

## Traction control has not been tested in motion

It is enabled and its behaviour is understood from the source
([findings](findings.md#traction-control-does-not-affect-braking)), but the
reference board has not been ridden hard enough to provoke a slip event and
confirm the taper feels right.
