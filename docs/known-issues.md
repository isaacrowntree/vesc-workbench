# Known issues

Open problems only. Firmware behaviour the tooling already handles, and things
since confirmed on hardware, are in [findings.md](findings.md).

## Speed reads from one motor

Speed is derived from one motor's ERPM, gear ratio and wheel diameter; it is not
summed across motors. Spinning one wheel by hand only moves the reading if it is
the motor that owns the calculation. On the ground both wheels turn together and
it reads correctly.

## Hardware coverage is one board

Everything here has been exercised on a single FOCBOX Unity with a single
DAVEGA X. The connection layer and the config workflow are not Unity-specific,
but nobody has proved that on other hardware. Reports welcome.

---

Resolved and moved to [findings.md](findings.md): `COMM_FORWARD_CAN` to a second
motor, the DAVEGA refresh rate, traction control in motion, and needing a button
press on the display after reloading the shim.
