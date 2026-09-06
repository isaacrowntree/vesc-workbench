# DAVEGA X vs VESC firmware 7.x — feasibility of a shim

**Question:** the DAVEGA X stops working on VESC FW 7. Can it be made to work
without downgrading the ESC?

**Short answer: yes, and it is a much smaller job than expected — because the
protocol did not change. Only the reported version number did.**

## Evidence

Reproduce with `./tests/protocol-diff.sh` (diffs bldc tag `6.00`, the last version
DAVEGA supports, against `master` = 7.x).

| Surface | 6.00 | 7.x | Same? |
|---|---|---|---|
| `COMM_FW_VERSION` packet id | 0 | 0 | ✅ |
| `COMM_GET_VALUES` packet id | 4 (implicit ordinal) | 4 (explicit) | ✅ |
| `COMM_GET_VALUES` payload | 25 fields | 25 fields | ✅ **byte-identical** |
| `COMM_FW_VERSION` response structure | — | — | ✅ **identical** |
| `FW_VERSION_MAJOR` / `MINOR` | **6 / 00** | **7 / 01** | ❌ the only difference |

The telemetry packet the DAVEGA actually renders is unchanged: same fields, same
types, same order. So the display is not failing to *parse* anything — it is
refusing to *talk*, on the strength of two bytes in the version handshake.

## Options, best first

### 1. Serial man-in-the-middle (recommended)
A small MCU (ESP32 / Pi Pico / ATmega) inline on the UART between the Unity and
the DAVEGA:

- pass every byte through untouched, **except**
- when a `COMM_FW_VERSION` **response** goes ESC → DAVEGA, rewrite the two version
  bytes from `7,01` to `6,00` and recompute the packet CRC16.

Everything else is a transparent pipe, because everything else is identical.
That is roughly 100 lines. It needs the VESC packet framing (start byte, length,
payload, CRC16, stop byte 3) to find packet boundaries — nothing more.

Cost: one small board and a cable splice. Zero firmware risk to the ESC.

### 2. LispBM script on the ESC
VESC 6+ ships LispBM with `uart-start` / `uart-read` / `uart-write`, and the Unity
hwconf does not disable it. But taking the UART from LispBM **replaces** the normal
UART comm app, so the script would have to reimplement the whole protocol — framing,
CRC, and rebuilding all 25 telemetry fields from LispBM getters. Feasible, but far
more work than option 1, and it runs on the thing you cannot afford to break.

### 3. Patch FW_VERSION in a custom firmware build
One-line change, but it lies to VESC Tool too — which then mis-matches the config
parameter set. Do not.

## Not viable
- No community VESC 7 DAVEGA firmware exists. All forks of `janpom/davega` are dead
  (best is `charclo/roxie-firmware`, last commit 2022, tops out at "vesc 5.03
  compatibility").
- DAVEGA **X** firmware was never open-sourced — the public repo is the original
  Arduino DAVEga, different hardware. Nobody *can* patch the X.
- DAVEGA shop closed May 2024 (team merged into Voyage Systems). Cloud and support
  continue; firmware development does not. Last release v5.06, 2023-05-15.

## Aside: the Unity is one MCU, not two ESCs
`hwconf/other/hw_unity.h:21` defines `HW_HAS_DUAL_MOTORS`, and `commands.c` does:

    if (mc_interface_get_motor_thread() == 2) {
        send_buffer[ind - 1]++;   // increment last UUID byte for motor 2
    }

That is why this board reports UUIDs `...134` and `...135` — same STM32, second
motor gets the incremented id. So firmware is a single upload to a single MCU,
and the two "CAN devices" are two motor threads on one chip.
