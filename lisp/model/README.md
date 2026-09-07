# DAVEGA ↔ VESC 7 shim

Lets a **DAVEGA X (fw 5.06)** work with a **VESC running FW 7.x**, with no change
to either device.

## Why this is so small

`../tests/protocol-diff.sh` diffs bldc `6.00` (last version DAVEGA supports)
against `master` (7.x):

- `COMM_GET_VALUES` payload — **byte-identical**, 25 fields, same order
- `COMM_FW_VERSION` response structure — **identical**
- Only `FW_VERSION_MAJOR` / `MINOR` differ: `6/00` vs `7/01`

The DAVEGA isn't failing to parse telemetry. It's refusing to talk, on two bytes.
So the shim rewrites those two bytes (and the CRC) and passes everything else
through untouched.

## Layout

    vesc_packet.py   framing + CRC16, ported from bldc/comm/packet.c and util/crc.c
    shim.py          the translator (streaming, byte-exact)
    test_shim.py     test suite - run: python3 test_shim.py
    firmware/davega_shim.ino   same logic in C++ for ESP32 / RP2040

## Hardware

A microcontroller with two UARTs, inline on the DAVEGA cable. All 3.3V, common ground.

    VESC TX   -> shim UART_VESC RX      shim UART_VESC TX -> VESC RX
    DAVEGA TX -> shim UART_DISP RX      shim UART_DISP TX -> DAVEGA RX
    VESC 5V/GND -> shim VIN/GND

ESP32 pins are set at the top of the .ino (16/17 and 18/19 by default).

## Tests

    python3 test_shim.py

Covers: CRC table matches bldc, framing round-trips (incl. the 255/256 length-byte
boundary), the version rewrite, every other packet id passing through byte-identical,
arbitrary chunk splitting of the byte stream, and corrupt/partial frames being passed
through without loss.

## Two implementations

### A. LispBM on the VESC — no extra hardware  ← preferred
`lisp/davega_shim.lisp`. Runs on the ESC itself. Takes over the UART the DAVEGA is
wired to, answers `COMM_FW_VERSION` claiming 6.00, and rebuilds `COMM_GET_VALUES`
from live values.

Safe on a Unity: `uart-start` binds `HW_UART_DEV` (SD3, USART3 PB10/11) which is the
DAVEGA's port. The internal **BLE module is on SD1 (USART1, 250000 baud)** and is not
touched — so you cannot lock yourself out; stop the script any time from VESC Tool.

Requires `App to Use` = **PPM** (not PPM+UART) so the UART app doesn't fight LispBM.

### B. Inline hardware shim
`firmware/davega_shim.ino` — ESP32/RP2040 spliced into the DAVEGA cable. Only worth
it if the LispBM route is ruled out.

## Confirmed failure mode

The DAVEGA X on VESC 7 shows:

> supported vesc firmware versions 5.x to 6.x - press any button to restart

A pure version gate. Its telemetry parser is fine — `COMM_GET_VALUES` is byte-identical
between 6.00 and 7.x — it just never gets that far.

## Status

- Protocol analysis: **verified** (`../tests/protocol-diff.sh`)
- Byte layout: **cross-validated** against DAVEga's own parser (`test_layout.py`)
- Python reference + tests: **passing** (`test_shim.py`)
- LispBM script: **written, NOT yet run on the board**
- ESP32 sketch: **written, NOT yet run on hardware**
