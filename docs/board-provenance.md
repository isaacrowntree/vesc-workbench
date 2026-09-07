# This board

One board, one display, one owner's history. Every number in this repo's
defaults comes from here, so it is worth writing down where they came from —
and, more importantly, which of them are *known* and which are inherited from
somebody else's riding.

## Provenance

| | |
|---|---|
| Model | LaCroix Nazaré, FOCBOX Unity, 12s4p |
| Acquired | **2021-04-10, secondhand** |
| Condition | Already well used when bought. Mileage before that date is unknown and unrecoverable. |

That last row matters more than it looks. The Unity keeps a lifetime
tachometer, but it was not zeroed when the board changed hands and the
DAVEGA's own counter started from nothing — so **no odometer on this board
measures its life**, only its life since something was reset. Any wear figure
derived from them is a lower bound.

## Parts, and when they went on

From the LaCroix order confirmations (`isaac@rowntree.me`):

| Part | Ordered | Delivered | Order |
|---|---|---|---|
| **Falcon™ gear drive** | 2021-01-24 | 2021-03-24 | #2830 ($921) |
| Enclosure washers, M5 | 2021-01-24 | 2021-03-24 | #2830 |
| Ultra Fast charger, 12 A | 2021-01-24 | 2021-03-24 | #2830 |
| **HyperRims™ LeMans** | 2021-05-13 | 2021-06-18 | #3505 ($399) |
| Charger (replacement, first arrived damaged) | 2021-05-20 | 2021-06-18 | #3549 |

The gear drive is the one that changes how the board should be described:
**this board has no belts.** The DAVEGA's stock wear tracker ships with a
`belts` entry, and on this board it tracks a part that is not fitted.

Motors, battery and the ESC are original to the board and predate ownership.

## The ESC, identified

The FOCBOX Unity has no real-time clock and stores no manufacture date. What
it does have is the STM32's 96-bit unique id, readable over the display's UART
with `COMM_FW_VERSION`:

```
raw   4b003b001251383136353134
fw    7.00
hw    UNITY
```

Decoded against RM0090's layout for the STM32F4:

| | |
|---|---|
| Lot number | **Q816514** (7 ASCII characters) |
| Wafer number | 18 |
| Die X / Y on the wafer | 75 / 59 |

**This is not a date.** ST's documentation is explicit that the unique id
carries lot, wafer and die coordinates and nothing else; the year/week code is
printed on the package at the packaging site and is not in the register. The
widely repeated claim that a manufacturing date can be decoded from the UID is
wrong. The only way to date this ESC is to open the enclosure and read the
marking on the chip.

What the id *is* good for is identity: it distinguishes this controller from
any other, which is what you want on a bench where configurations get copied
between boards.

## What this means for the defaults

- `wheel_diameter_mm = 200`, `wheel_pulley_teeth = 84`, `motor_pulley_teeth = 20`
  — corrected. The display had shipped with 175 mm on 72/16, which under-read
  speed by 18 %.
- `motor_count = 2`, and the second controller answers on CAN id 124.
- `battery_mah = 17000`, 12s4p, `battery_usable_capacity = 0.8`.
- `wh_per_km` — the rate the range estimate falls back on before a ride has
  measured its own. A road number is optimistic for a board ridden on grass.
- Part wear: every `new_km` is 0, which is honest rather than accurate. The
  parts went on before anything was counting.
