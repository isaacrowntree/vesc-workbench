# Known issues

Open problems only. Things the tooling now handles for you are in
[findings.md](findings.md) — worth reading if you are writing your own scripts,
but you do not have to act on them.

## Traction control has not been tested in motion

It is enabled and its behaviour is understood from the source
([findings](findings.md#traction-control-does-not-affect-braking)), but no slip
event has been captured with instrumentation attached to confirm the taper
feels right.

## The display needs a button press after reloading the shim

Reloading the script re-runs `uart-start` mid-session, and the DAVEGA drops to
its error screen. Nothing to be done from this side — press a button on the
display after every upload.

## Speed reads from one motor

Speed is derived from one motor's ERPM, gear ratio and wheel diameter; it is not
summed across motors. Spinning one wheel by hand only moves the reading if it is
the motor that owns the calculation. On the ground both wheels turn together and
it reads correctly.
