# Changelog

## Unreleased

Reframed as a general VESC workbench; the DAVEGA shim is the worked example.

### Added
- LispBM pass-through proxy: firmware handles every command via `cmds-proc`,
  the shim rewrites only the two version bytes in a `COMM_FW_VERSION` reply
- `make davega-debug` health check with per-command counters and a verdict
- Config tooling over a phone's TCP bridge: pull, apply, verify, PPM watch and
  calibration, bench mode (`motors-off`/`motors-on`), reboot and lisp-erase
- Test suite: Python reference plus the shipped Lisp run in the upstream LispBM
  REPL, asserting framed bytes against DAVEga's own parser offsets
- Board profiles (`profiles/`) and CI
- Integration harness (`tests/lisp/harness.lisp`): a fake UART with a scriptable
  per-call byte budget, driving the real reader
- `make upload-lisp` moves `app_to_use` off UART-combined apps before running a
  script that calls `uart-start`, instead of letting the firmware zero it
- `make apply-appconf` primes `ppm ctrl_type` when it is `None`, so PPM writes
  stick on the first run

### Fixed
- Frame desync in the DAVEGA proxy: the reader asked for both header bytes in
  one call and dropped short payload reads, losing whole request/reply round
  trips. The display showed this as a readout updating in lurches

### Known
- `COMM_FORWARD_CAN` to a real second motor is unverified — see
  `docs/known-issues.md`
- Traction control is enabled but untested in motion
- Tested only on a FOCBOX Unity
