"""VESC replies to feed the fake UART.

Two kinds. The first two are **recorded off the bench** - a FOCBOX Unity on
firmware 7.00, both controllers answering, captured byte for byte. They are
the ground truth: if our parser stops agreeing with these, it has stopped
agreeing with the hardware.

The rest are built to order, because a recording can only show you the board
in the state it was in. Standing still in a workshop is not the interesting
case; 40 km/h under load with a hot FET is, and it is not a state you can
capture safely on request.
"""

CRC_TABLE_POLY = 0x1021


def crc16(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = (((crc << 1) ^ CRC_TABLE_POLY) & 0xFFFF if crc & 0x8000
                   else (crc << 1) & 0xFFFF)
    return crc


def _unhex(s):
    return bytes(int(s[i:i + 2], 16) for i in range(0, len(s), 2))


# --- recorded, 2026-09-07, Unity on fw 7.00, board at rest ---------------
#
# Controller 123 answered over the wire; 124 answered through it over CAN.
# Note they disagree - different FET temperature, different tachometer, their
# own controller id at offset 60 - which is the evidence that the standard
# reply carries one controller and not two.
REAL_123 = _unhex(
    "024a04011801040000000000000000000000000000000000000000000001c900"
    "0000000000000000000000000000000000004a000000dc0013bdb6007b000000"
    "000000000000060000000300991903")
REAL_124 = _unhex(
    "024a04011900ff0000000000000000000000000000000000000000000001c900"
    "0000000000000000000000000000000000004b000000db0001b774007c000000"
    "0000000000000a00000002009c4c03")

# Both are 79 bytes and both carry a valid CRC. Asserted at import, because a
# recording that has been retyped by hand is worth exactly nothing if a byte
# moved, and a silently wrong fixture is worse than no fixture.
for _name, _f in (("REAL_123", REAL_123), ("REAL_124", REAL_124)):
    if len(_f) != 79:
        raise ValueError("%s is %d bytes, recorded 79" % (_name, len(_f)))
    _n = _f[1]
    if ((_f[_n + 2] << 8) | _f[_n + 3]) != crc16(_f[2:2 + _n]):
        raise ValueError("%s fails its own CRC" % _name)


# --- built to order ------------------------------------------------------

FIELDS = (
    ("temp_fet", 3, 2, 10.0, True),
    ("temp_motor", 5, 2, 10.0, True),
    ("motor_current", 7, 4, 100.0, True),
    ("input_current", 11, 4, 100.0, True),
    ("duty", 23, 2, 1000.0, True),
    ("rpm", 25, 4, 1.0, True),
    ("voltage", 29, 2, 10.0, True),
    ("amp_hours", 31, 4, 10000.0, True),
    ("amp_hours_charged", 35, 4, 10000.0, True),
    ("watt_hours", 39, 4, 10000.0, True),
    ("watt_hours_charged", 43, 4, 10000.0, True),
    ("tachometer", 47, 4, 1.0, True),
    ("tachometer_abs", 51, 4, 1.0, True),
)


def _pack(buf, offset, size, value, signed):
    if value < 0:
        value += 1 << (size * 8)
    for i in range(size):
        buf[offset + size - 1 - i] = (value >> (8 * i)) & 0xFF


def build(can_id=123, fault=0, **vals):
    """A COMM_GET_VALUES reply the way an ESC would send one.

    Offsets are frame-relative and match `vesc_comm_standard.cpp`, so a frame
    built here is the same shape as a frame off the wire - which is checked by
    parsing the two recorded ones with the same code.
    """
    payload = bytearray(0x4A)
    payload[0] = 4                                   # COMM_GET_VALUES
    for name, off, size, div, signed in FIELDS:
        if name in vals:
            _pack(payload, off - 2, size,
                  int(round(vals[name] * div)), signed)
    payload[55 - 2] = fault
    payload[60 - 2] = can_id
    c = crc16(bytes(payload))
    return (bytes((2, len(payload))) + bytes(payload)
            + bytes((c >> 8, c & 0xFF, 3)))


def erpm(kph, pole_pairs=7, gear=4.2, wheel_m=0.2):
    """Speed to electrical rpm, using the board's real geometry - 200 mm
    wheels on 84/20, which is what the config says after being corrected."""
    import math
    rev_per_km = 1000.0 / (math.pi * wheel_m)
    return kph * rev_per_km / 60.0 * gear * pole_pairs


#: A ride, as the frames the ESC would have sent. Each entry is
#: (label, primary controller reply, second controller reply).
def ride():
    def pair(**kw):
        second = dict(kw)
        # The second controller does its own share of the work and runs its
        # own temperature. Deliberately not identical to the first.
        second["motor_current"] = kw.get("motor_current", 0.0) * 0.9
        second["input_current"] = kw.get("input_current", 0.0) * 1.1
        second["temp_fet"] = kw.get("temp_fet", 25.0) + 3.0
        return (build(can_id=123, **kw), build(can_id=124, **second))

    return [
        ("standstill", pair(voltage=50.0, rpm=0, temp_fet=26.0,
                            temp_motor=25.0, tachometer_abs=0)),
        ("pulling away", pair(voltage=48.6, rpm=erpm(8), motor_current=42.0,
                              input_current=9.0, temp_fet=31.0,
                              temp_motor=30.0, duty=0.22,
                              amp_hours=0.05, watt_hours=2.4,
                              tachometer_abs=900)),
        ("cruising", pair(voltage=47.9, rpm=erpm(25), motor_current=18.0,
                          input_current=10.0, temp_fet=42.0,
                          temp_motor=48.0, duty=0.55,
                          amp_hours=0.9, watt_hours=43.0,
                          tachometer_abs=42000)),
        ("full throttle", pair(voltage=45.2, rpm=erpm(41), motor_current=79.0,
                               input_current=29.0, temp_fet=68.0,
                               temp_motor=71.0, duty=0.94,
                               amp_hours=2.1, watt_hours=99.0,
                               tachometer_abs=98000)),
        ("hard regen", pair(voltage=51.1, rpm=erpm(19), motor_current=-38.0,
                            input_current=-12.0, temp_fet=61.0,
                            temp_motor=66.0, duty=-0.3,
                            amp_hours=2.0, watt_hours=95.0,
                            tachometer_abs=104000)),
        ("thermal derate", pair(voltage=44.0, rpm=erpm(22), motor_current=30.0,
                                input_current=14.0, temp_fet=88.0,
                                temp_motor=92.0, duty=0.6,
                                amp_hours=3.4, watt_hours=158.0,
                                tachometer_abs=150000)),
        ("drv fault", (build(can_id=123, fault=3, voltage=43.0,
                             rpm=0, temp_fet=79.0, temp_motor=84.0,
                             amp_hours=3.6, watt_hours=168.0,
                             tachometer_abs=151000),
                       build(can_id=124, fault=0, voltage=43.0,
                             rpm=0, temp_fet=82.0, temp_motor=86.0))),
        ("recovered", pair(voltage=43.4, rpm=erpm(12), motor_current=14.0,
                           input_current=6.0, temp_fet=70.0,
                           temp_motor=74.0, duty=0.3,
                           amp_hours=3.7, watt_hours=172.0,
                           tachometer_abs=152000)),
        ("nearly empty", pair(voltage=37.4, rpm=erpm(9), motor_current=11.0,
                              input_current=5.0, temp_fet=52.0,
                              temp_motor=57.0, duty=0.25,
                              amp_hours=12.6, watt_hours=560.0,
                              tachometer_abs=310000)),
    ]
