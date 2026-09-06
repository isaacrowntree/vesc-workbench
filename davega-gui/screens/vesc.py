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
    ("amp_hours", 31, ">i", 10.0),
    ("amp_hours_charged", 35, ">i", 10.0),
    ("tachometer", 47, ">i", 1.0),
    ("tachometer_abs_value", 51, ">i", 1.0),
)
FAULT_OFFSET = 55

# The FOCBOX Unity answers with BOTH motors in one packet, at its own offsets,
# and the display averages the pairs. Kept for completeness: a Unity on VESC 7
# speaks the standard layout, and the second motor is reached over CAN.
UNITY_PAIRS = (
    ("temp_fet_filtered", (3, 5), ">h", 10.0),
    ("temp_motor_filtered", (7, 9), ">h", 10.0),
    ("avg_motor_current", (11, 15), ">i", 100.0),
    ("duty", (39, 41), ">h", 1000.0),
    ("rpm", (43, 47), ">i", 1.0),
)


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

    `esc_count` scales pack current: each ESC reports only what it draws, so a
    dual-motor board draws twice what one packet says. The reference firmware
    does the same (`get_battery_current() * VESC_COUNT`), and without it a
    dual board under-reports its pack draw by half.
    """
    if not valid(packet):
        return None
    out = {}
    for name, off, fmt, div in STANDARD:
        (raw,) = struct.unpack(fmt, packet[off:off + struct.calcsize(fmt)])
        out[name] = raw / div if div != 1.0 else raw
    out["avg_input_current"] *= esc_count
    out["fault"] = packet[FAULT_OFFSET] if len(packet) > FAULT_OFFSET else 0
    # Fields the ESC does not send, which screens still render.
    out["watt_hours"] = 0.0
    out["watt_hours_charged"] = 0.0
    out["can_id"] = 0
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
    while ticks_diff(ticks_ms(), start) < deadline_ms and spins < max_spins:
        spins += 1
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
