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

### Known
- `COMM_FORWARD_CAN` to a real second motor is unverified — see
  `docs/known-issues.md`
- Tested only on a FOCBOX Unity
