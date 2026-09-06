# vesc-workbench

A scripted workbench for **VESC** motor controllers: read, write and verify
configuration, drive LispBM, and diagnose problems — all over a phone's
Bluetooth bridge, with **no USB and no opening the enclosure**.

Built while getting a LaCroix Nazaré (FOCBOX Unity) onto firmware 7 and keeping
a discontinued DAVEGA X display working. That shim ships here as the worked
example, but the tooling is the point.

Maintained by Isaac Rowntree. MIT. Contributions welcome —
see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## What it gives you

### Scripted config over BLE — no USB

VESC Tool's CLI is serial-only (`--vescPort` calls `connectSerial()`; TCP and a
socat PTY are both rejected). But `--loadQml` runs arbitrary QML with `VescIf` in
scope, and `VescIf.connectTcp()` is invokable — so the whole config API is
reachable over the phone's TCP bridge.

```sh
make pull      # read both motor sides' configs to XML
make apply     # write them back, then verify by reading them again
```

> [!IMPORTANT]
> `setMcconf(true)` is required — with `check=false` the ESC silently ignores the
> write. And **wait for the ESC to settle after a reboot before reading back**;
> mid-boot reads return transient values that look exactly like corruption.

### A LispBM development workflow

```sh
make upload-lisp LISP=path/to/script.lisp   # upload and run
make lisp-stats                             # heap, CPU, globals
make lisp-stop / lisp-erase                 # stop or remove
make test-lisp                              # run it in the real interpreter
```

Scripts are tested by running them in the **upstream LispBM REPL** (Docker),
not by transcribing them into another language. `tools/minify-lisp.py` strips
them before upload, because upload happens in 384-byte chunks with a 1-second
per-chunk timeout and size genuinely matters.

Globals double as a telemetry channel: `lispGetStats` returns them, so a script
can report internal counters without needing print output to work.

### Diagnostics

```sh
make davega-debug SECS=60   # health check with a verdict
make ppm-watch              # live remote readout, prints only on change
make ppm-cal                # guided calibration: neutral / full throttle / full brake
```

`ppm-watch` distinguishes "the remote is not transmitting" from "the decoder is
not running" — both look identical in a GUI.

### Safety affordances

```sh
make motors-off / motors-on   # app-disable-output, no config write
make reboot                   # stop LispBM and restart the app layer
make lisp-erase               # back to stock behaviour
make check                    # bridge up? desktop VESC Tool closed?
```

`motors-off` lets you work on a live board with the display running and the
motors inert, without touching configuration.

## The DAVEGA shim (worked example)

A DAVEGA X on VESC 7 refuses to start:

> supported vesc firmware versions 5.x to 6.x - press any button to restart

The telemetry protocol **did not change** — `tests/protocol-diff.sh` proves it
against upstream on every CI run:

| Surface | 6.00 | 7.x | Same? |
|---|---|---|---|
| `COMM_GET_VALUES` payload | 25 fields | 25 fields | ✅ byte-identical |
| `COMM_FW_VERSION` structure | — | — | ✅ identical |
| `FW_VERSION_MAJOR`/`MINOR` | 6/00 | 7/01 | ❌ the only difference |

So the display is not failing to parse anything. It is refusing to talk, on two
bytes. The shim proxies every command to the firmware's own decoder via
`cmds-proc` and rewrites only those two, recomputing the CRC. ~60 lines of Lisp.

See [docs/davega-shim.md](docs/davega-shim.md).

## Requirements

- VESC firmware **6.06+** for `cmds-proc` (developed on 7.00)
- VESC Tool desktop (driven headlessly; macOS and Linux paths both handled)
- Docker for the Lisp tests
- A phone running VESC Tool, connected over BLE, Start page → **Wireless Bridge
  to Computer (TCP)** → Activate Bridge. Desktop VESC Tool must be closed; the
  bridge takes one client.

## Quick start

```sh
make help
make check
make test
make davega-debug PROFILE=profiles/nazare-unity.mk
```

## Board profiles

`profiles/` holds one file per known-good setup — connection details and the
second motor's CAN id. Deliberately **not** motor tuning: current limits and
gearing are specific to your hardware and copying someone else's is how motors
and packs get damaged. Run the detection wizard.

## Status

| | |
|---|---|
| Config read/write/verify over BLE | ✅ |
| LispBM upload, test, diagnose | ✅ |
| DAVEGA version gate bypass | ✅ telemetry live on a Unity, FW 7.00 |
| `COMM_FORWARD_CAN` to a second motor | ⚠️ unverified — [known issues](docs/known-issues.md) |
| Hardware tested | FOCBOX Unity only |

## Safety

This writes motor controller configuration and can enable or disable motor
output. Wheels off the ground for anything involving detection, app config or
`app-disable-output`. Verify the throttle before riding.

## Credits

VESC and LispBM by Benjamin Vedder. DAVEGA by Jan Pomikalek. This project is not
affiliated with either.
