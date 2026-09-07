"""Talking to the ESC directly.

The display's own `VescComm` exists, but its signatures are undocumented and
guessing at them cost an evening. This does the whole job instead, because the
protocol is small and the open-source DAVEga firmware documents it exactly:

    request  02 01 04 40 84 03      start, len, COMM_GET_VALUES, crc16, stop
    reply    02 <len> 04 <payload> <crc-hi> <crc-lo> 03

Two things the reference firmware cannot tell you, because it predates them:
the reply from firmware 7 is 79 bytes, not the 70 its buffer allows - the
payload grew as fields were appended - and on this display the UART is
tx 17 / rx 16, which is the reverse of what `VescComm`'s own attributes
suggest. Both were found by asking the board.

Field offsets below are lifted from `vesc_comm_standard.cpp` in janpom/davega
(GPL-3.0) - read, not reverse-engineered. Offsets count from the start byte, so
the command id sits at 2 and the first field at 3.
"""
import struct

START_SHORT = 2
STOP = 3
COMM_GET_VALUES = 4

# The whole request, CRC included: it never varies, so it never needs computing.
GET_VALUES = bytes((0x02, 0x01, 0x04, 0x40, 0x84, 0x03))

# name -> (offset, struct format, divisor)
STANDARD = (
    ("temp_fet_filtered", 3, ">h", 10.0),
    ("temp_motor_filtered", 5, ">h", 10.0),
    ("avg_motor_current", 7, ">i", 100.0),
    ("avg_input_current", 11, ">i", 100.0),
    ("duty", 23, ">h", 1000.0),
    ("rpm", 25, ">i", 1.0),
    ("input_voltage", 29, ">h", 10.0),
    # Energy counters go out at 1e4, not 1e1. DAVEga's own
    # get_amphours_discharged() divides by 10 and the result is used directly
    # as *milliamp* hours - so the wire scale is Ah x 10^4, and reading it at
    # 10 makes a 0.5 Ah trip look like 500 Ah. lisp/tests pins the layout.
    ("amp_hours", 31, ">i", 10000.0),
    ("amp_hours_charged", 35, ">i", 10000.0),
    ("watt_hours", 39, ">i", 10000.0),
    ("watt_hours_charged", 43, ">i", 10000.0),
    ("tachometer", 47, ">i", 1.0),
    ("tachometer_abs_value", 51, ">i", 1.0),
)
FAULT_OFFSET = 55

CAN_ID_OFFSET = 60
COMM_FORWARD_CAN = 34


def can_request(can_id):
    """The GET_VALUES request, wrapped so the local ESC forwards it to another
    controller on the CAN bus.

    A Unity is two controllers in one case (123 and 124 here) and the standard
    reply carries only the one that answered - its own temperature, its own
    motor current, its own tachometer. Asking the second one directly is the
    difference between reading the board and reading half of it.
    """
    payload = bytes((COMM_FORWARD_CAN, can_id, COMM_GET_VALUES))
    c = crc16(payload)
    return bytes((START_SHORT, len(payload))) + payload + bytes(
        (c >> 8, c & 0xFF, STOP))


def crc16(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def valid(packet):
    """Is this a complete, correctly framed COMM_GET_VALUES reply?"""
    if len(packet) < 6 or packet[0] != START_SHORT:
        return False
    n = packet[1]
    if len(packet) < n + 5 or packet[2] != COMM_GET_VALUES:
        return False
    if packet[n + 4] != STOP:
        return False
    got = (packet[n + 2] << 8) | packet[n + 3]
    return got == crc16(packet[2:2 + n])


def parse(packet, esc_count=1):
    """Reply bytes to real units. Returns None if the packet is not sound -
    a wrong number rendered confidently is worse than no number.

    `esc_count` scales pack current when only one controller has been read:
    each ESC reports the share of the pack it draws, so a dual board pulls
    twice what one packet says. It is the reference firmware's approximation
    (`get_battery_current() * VESC_COUNT`) and it assumes the two are doing
    equal work. Prefer reading the other controller over CAN and `combine`-ing
    the results; this is the fallback for when that read fails.

    Motor current is deliberately not scaled. It is a per-motor figure in the
    reference too - the Unity path averages the pair rather than adding them -
    because what a motor current means is measured against one motor's limit.
    """
    if not valid(packet):
        return None
    out = {}
    for name, off, fmt, div in STANDARD:
        (raw,) = struct.unpack(fmt, packet[off:off + struct.calcsize(fmt)])
        out[name] = raw / div if div != 1.0 else raw
    if esc_count != 1:
        out["avg_input_current"] *= esc_count
    out["fault"] = packet[FAULT_OFFSET] if len(packet) > FAULT_OFFSET else 0
    out["can_id"] = (packet[CAN_ID_OFFSET]
                     if len(packet) > CAN_ID_OFFSET else 0)
    return out


def combine(primary, other):
    """One board's numbers from two controllers.

    Follows `vesc_comm_unity.cpp`, which is the reference doing this same job
    for a board that answers for both motors in one packet:

    * pack current and the energy counters are **summed** - each controller
      reports only the share it drew, and the pack saw all of it;
    * motor current, duty and rpm are **averaged** - they are per-motor
      quantities, measured against one motor's limits, and the reference
      averages them too;
    * the tachometers each count the same road, so distance comes from the
      primary rather than being added twice.

    Temperature is the one deliberate divergence: the reference averages the
    two, we take the hotter. An average hides the controller that is about to
    derate behind the one that is fine, and the hot one is the one that will
    decide how the rest of the ride goes.
    """
    if not other:
        return primary
    out = dict(primary)
    for k in ("avg_input_current", "amp_hours", "amp_hours_charged",
              "watt_hours", "watt_hours_charged"):
        out[k] = primary[k] + other[k]
    for k in ("avg_motor_current", "duty", "rpm"):
        out[k] = (primary[k] + other[k]) / 2.0
    for k in ("temp_fet_filtered", "temp_motor_filtered"):
        out[k] = max(primary[k], other[k])
    out["fault"] = primary["fault"] or other["fault"]
    out["esc_count"] = 2
    return out


def request(uart):
    """Ask for values. Separate from `read` so a caller can overlap the wait
    with drawing rather than blocking on the round trip."""
    uart.write(GET_VALUES)


def read(uart, deadline_ms, ticks_ms, ticks_diff, max_len=128, max_spins=2000):
    """Collect one reply. Mirrors the reference implementation: read until the
    frame is complete by its own declared length, then stop.

    Bounded by iterations as well as by time. A time-only bound spins forever
    if the clock stops - which is not hypothetical: it hung the test rig, and
    on a board a stalled timer would take the dashboard with it.
    """
    buf = bytearray()
    start = ticks_ms()
    spins = 0
    # MicroPython's uart.read() blocks for the port's whole timeout when no
    # data has arrived, so calling it in a poll loop costs that timeout every
    # pass - measured at 211 ms a read on this board. Asking any() first turns
    # the loop into a real poll and the read into something that returns
    # immediately.
    available = getattr(uart, "any", None)
    while ticks_diff(ticks_ms(), start) < deadline_ms and spins < max_spins:
        spins += 1
        if available is not None and not available():
            continue
        chunk = uart.read(max_len - len(buf))
        if chunk:
            buf += chunk
            if len(buf) >= 2 and buf[0] == START_SHORT:
                want = buf[1] + 5
                if len(buf) >= want:
                    # A chunk can spill past the frame end; keep this frame
                    # and let the next read pick up whatever followed.
                    buf = buf[:want]
                    break
            elif len(buf) >= 2:
                buf = bytearray()       # not a short frame: resync
        if len(buf) >= max_len:
            break
    return bytes(buf)
