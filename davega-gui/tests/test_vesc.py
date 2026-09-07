#!/usr/bin/env python3
"""The ESC wire protocol.

Offsets and scaling come from janpom/davega's vesc_comm_standard.cpp, so these
tests build a reply the way the ESC would and assert we read back exactly what
went in. That is the check that matters: a field read from the wrong offset
still produces a plausible number.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from screens import vesc                                  # noqa: E402

fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


def build(**vals):
    """Assemble a COMM_GET_VALUES reply the way an ESC would."""
    payload = bytearray(54)
    payload[0] = vesc.COMM_GET_VALUES
    for name, off, fmt, div in vesc.STANDARD:
        if name not in vals:
            continue
        raw = int(round(vals[name] * div))
        struct.pack_into(fmt, payload, off - 2, raw)
    if "fault" in vals:
        payload[vesc.FAULT_OFFSET - 2] = vals["fault"]
    frame = bytearray()
    frame.append(vesc.START_SHORT)
    frame.append(len(payload))
    frame += payload
    crc = vesc.crc16(bytes(payload))
    frame.append((crc >> 8) & 0xFF)
    frame.append(crc & 0xFF)
    frame.append(vesc.STOP)
    return bytes(frame)


def main():
    print("== the request packet is the documented one")
    check("bytes", vesc.GET_VALUES == bytes((2, 1, 4, 0x40, 0x84, 3)))
    check("its crc is self-consistent", vesc.crc16(bytes([4])) == 0x4084)

    print()
    print("== a reply round-trips through the real offsets")
    sent = dict(temp_fet_filtered=42.3, temp_motor_filtered=48.7,
                avg_motor_current=18.25, avg_input_current=9.5,
                duty=0.456, rpm=35094, input_voltage=43.2,
                amp_hours=5.9, amp_hours_charged=0.4,
                tachometer=120000, tachometer_abs_value=120500, fault=3)
    got = vesc.parse(build(**sent))
    check("parses", got is not None)
    if got:
        for k, v in sent.items():
            if k == "fault":
                check("field/%s" % k, got[k] == v, "got %r" % got[k])
            else:
                check("field/%-20s %s" % (k, v), abs(got[k] - v) < 0.051,
                      "got %r" % got[k])

    print()
    print("== negative currents and reverse survive the sign")
    neg = vesc.parse(build(avg_motor_current=-72.5, avg_input_current=-8.25,
                           duty=-0.3, rpm=-12000))
    check("motor regen", abs(neg["avg_motor_current"] + 72.5) < 0.02)
    check("pack charge", abs(neg["avg_input_current"] + 8.25) < 0.02)
    check("reverse duty", abs(neg["duty"] + 0.3) < 0.002)
    check("reverse rpm", neg["rpm"] == -12000)

    print()
    print("== a bad packet is refused rather than half-read")
    good = build(input_voltage=43.2)
    check("truncated", vesc.parse(good[:20]) is None)
    check("wrong start byte", vesc.parse(b"\x09" + good[1:]) is None)
    check("wrong command id",
          vesc.parse(good[:2] + b"\x05" + good[3:]) is None)
    bad_crc = bytearray(good)
    bad_crc[-2] ^= 0xFF
    check("corrupt crc", vesc.parse(bytes(bad_crc)) is None)
    bad_stop = bytearray(good)
    bad_stop[-1] = 0
    check("missing stop byte", vesc.parse(bytes(bad_stop)) is None)
    check("empty", vesc.parse(b"") is None)

    print()
    print("== read() collects exactly one frame from a dribbling uart")

    class Uart:
        """Hands over a few bytes at a time, like a real one."""

        def __init__(self, data, chunk=7):
            self.data, self.chunk, self.pos = data, chunk, 0

        def any(self):
            return len(self.data) - self.pos

        def read(self, n):
            if self.pos >= len(self.data):
                return None
            take = min(n, self.chunk, len(self.data) - self.pos)
            out = self.data[self.pos:self.pos + take]
            self.pos += take
            return out

    clock = [0]

    def ticks():
        clock[0] += 1
        return clock[0]

    frame = build(input_voltage=43.2, rpm=20000)
    u = Uart(frame + b"\x02\x01\x04")          # plus the start of another
    out = vesc.read(u, 500, ticks, lambda a, c: a - c)
    check("stops at the frame boundary", len(out) == len(frame),
          "got %d want %d" % (len(out), len(frame)))
    check("and it parses", vesc.parse(out) is not None)

    print()
    print("== reading the second controller over CAN, and the fallback")
    # Each ESC reports only its own draw - proven on the bench, where 123 and
    # 124 answered with different temperatures and different tachometers. The
    # right answer is to ask both and add; esc_count is what to do when the
    # second one does not reply.
    one = vesc.parse(build(avg_input_current=9.5), esc_count=1)
    two = vesc.parse(build(avg_input_current=9.5), esc_count=2)
    check("single esc unchanged", abs(one["avg_input_current"] - 9.5) < 0.02)
    check("dual esc doubles", abs(two["avg_input_current"] - 19.0) < 0.02)
    check("motor current stays per-motor, as in the reference",
          abs(vesc.parse(build(avg_motor_current=18.0),
                         esc_count=2)["avg_motor_current"] - 18.0) < 0.05)

    a = vesc.parse(build(avg_motor_current=18.0, avg_input_current=9.5,
                         amp_hours=1.5, temp_fet_filtered=40.0, rpm=1000))
    b = vesc.parse(build(avg_motor_current=14.0, avg_input_current=7.5,
                         amp_hours=1.2, temp_fet_filtered=52.0, rpm=990))
    both = vesc.combine(a, b)
    check("pack current adds", abs(both["avg_input_current"] - 17.0) < 0.05)
    check("motor current averages", abs(both["avg_motor_current"] - 16.0) < 0.05)
    check("energy adds", abs(both["amp_hours"] - 2.7) < 0.01)
    check("the hotter controller is the one reported",
          abs(both["temp_fet_filtered"] - 52.0) < 0.05)
    check("distance is not counted twice",
          both["tachometer"] == a["tachometer"])
    check("combine survives a missing partner",
          vesc.combine(a, None) is a)

    print()
    print("== energy counters come off the wire at 1e4")
    # Read at 10 they were a thousand times too large, which is why range had
    # nothing sane to divide by: a 0.5 Ah trip looked like 500 Ah.
    e = vesc.parse(build(amp_hours=1.5, watt_hours=63.2))
    check("amp hours", abs(e["amp_hours"] - 1.5) < 0.001)
    check("watt hours are read, not zeroed",
          abs(e["watt_hours"] - 63.2) < 0.01)

    print()
    print("== a uart with no any() still works")
    # Not every port exposes any(); the reader must fall back to blocking
    # reads rather than assuming the fast path exists.
    class Plain:
        def __init__(self, data):
            self.data, self.pos = data, 0

        def read(self, n):
            if self.pos >= len(self.data):
                return None
            out = self.data[self.pos:self.pos + n]
            self.pos += len(out)
            return out

    clock2 = [0]
    out = vesc.read(Plain(frame), 500, lambda: clock2.__setitem__(0, clock2[0] + 1) or clock2[0],
                    lambda a, c: a - c)
    check("reads the frame without any()", vesc.parse(out) is not None)

    print()
    print("== asking the other controller on the CAN bus")
    # Proven on the bench: 123 answered over the wire and 124 through it, with
    # different temperatures, different tachometers and their own controller
    # ids in the reply. The standard packet carries one controller, not two.
    req = vesc.can_request(124)
    check("it is a framed COMM_FORWARD_CAN",
          req[0] == vesc.START_SHORT and req[-1] == vesc.STOP
          and req[2] == vesc.COMM_FORWARD_CAN)
    check("addressed to the right controller, asking for values",
          req[3] == 124 and req[4] == vesc.COMM_GET_VALUES)
    body = req[2:2 + req[1]]
    check("crc covers the payload",
          ((req[-3] << 8) | req[-2]) == vesc.crc16(body))

    print()
    if fails:
        print("%d VESC TESTS FAILED" % len(fails))
        return 1
    print("all vesc tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
