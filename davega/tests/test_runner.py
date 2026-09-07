#!/usr/bin/env python3
"""The main loop, with fakes for the board.

The loop is where the awkward decisions live: what to draw when telemetry
stops, whether a button still works when the ESC has gone quiet, and whether
one bad packet is allowed to take the dashboard down.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from harness.display import Display                    # noqa: E402
from harness.telemetry import Board                     # noqa: E402
from gui import vesc                                # noqa: E402
from gui.app import App, SWEEP, SCREEN, MENU        # noqa: E402
from gui.input import Buttons, DOWN, ENTER          # noqa: E402
from gui.riding import Riding                       # noqa: E402
from gui.panels import RangeScreen                  # noqa: E402
from gui.runner import Runner, STALE_MS                     # noqa: E402
from gui.session import Session, Resistance          # noqa: E402

fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


def build(**vals):
    payload = bytearray(54)
    payload[0] = vesc.COMM_GET_VALUES
    for name, off, fmt, div in vesc.STANDARD:
        if name in vals:
            struct.pack_into(fmt, payload, off - 2, int(round(vals[name] * div)))
    frame = bytearray([vesc.START_SHORT, len(payload)]) + payload
    crc = vesc.crc16(bytes(payload))
    frame += bytes(((crc >> 8) & 0xFF, crc & 0xFF, vesc.STOP))
    return bytes(frame)


class FakeUart:
    def __init__(self, reply=None):
        self.reply = reply
        self.written = []
        self.pending = b""

    def write(self, data):
        self.written.append(data)
        self.pending = self.reply if self.reply is not None else b""

    def read(self, n):
        if not self.pending:
            return None
        out, self.pending = self.pending[:n], self.pending[n:]
        return out


class Clock:
    """A clock that only moves when something asks it to - so a loop that
    depends on time passing is caught rather than hanging the suite."""

    def __init__(self, rig):
        self.rig = rig

    def __call__(self):
        self.rig.t += 1
        return self.rig.t


class Rig:
    def __init__(self, reply=None, screens=None, sweep=False):
        self.t = 0
        self.pins = [False, False, False]
        self.board = Board()
        self.d = Display()
        self.uart = FakeUart(reply)
        self.app = App(screens or (("riding", Riding), ("range", RangeScreen)),
                       self.board, "nazare", sweep=sweep)
        self.buttons = Buttons(lambda: tuple(self.pins), lambda: self.t)
        clock = Clock(self)
        self.session = Session(self.board)
        self.lifetime = Session(self.board, lifetime=True)
        self.resistance = Resistance(self.board.cells)
        self.runner = Runner(self.app, self.d, self.uart, self.board,
                             self.buttons, clock, lambda a, c: a - c,
                             self.advance, vesc, esc_count=2,
                             session=self.session, lifetime=self.lifetime,
                             resistance=self.resistance)

    def advance(self, ms):
        self.t += ms


def main():
    print("== a good reply reaches the screen")
    r = Rig(reply=build(input_voltage=43.2, rpm=20000, avg_motor_current=18.0))
    r.runner.step()
    check("requested values", r.uart.written and r.uart.written[0] == vesc.GET_VALUES)
    check("frame updated", abs(r.runner.frame["input_voltage"] - 43.2) < 0.05,
          "got %r" % r.runner.frame["input_voltage"])
    check("not stale", not r.runner.stale)
    check("drew something", len(r.d.calls) > 0)

    print()
    print("== pack current is scaled for a dual board")
    r = Rig(reply=build(avg_input_current=9.5))
    r.runner.step()
    check("9.5 A per esc reads as 19 A",
          abs(r.runner.frame["avg_input_current"] - 19.0) < 0.05,
          "got %r" % r.runner.frame["avg_input_current"])

    print()
    print("== silence is reported, not papered over with stale numbers")
    r = Rig(reply=b"")
    for _ in range(3):
        r.runner.step()
        r.advance(600)
    check("marked stale", r.runner.stale)
    check("counted the bad reads", r.runner.bad == r.runner.reads,
          "%d/%d" % (r.runner.bad, r.runner.reads))

    print()
    print("== the screen is told when the link dies, and when it comes back")
    r = Rig(reply=b"")
    for _ in range(3):
        r.runner.step()
        r.advance(600)
    check("frame says the link is down", r.runner.frame["link_ok"] is False)
    d_down = Display()
    Riding("nazare").render(d_down, r.runner.frame, r.board, full=True)
    ok_frame = r.board.frame()      # a Frame, not a bare dict
    ok_frame.update(r.runner.frame)
    ok_frame["link_ok"] = True
    d_up = Display()
    Riding("nazare").render(d_up, ok_frame, r.board, full=True)
    check("and it looks different on screen", d_down.pixels != d_up.pixels)

    r.uart.reply = build(input_voltage=43.2)
    r.runner.step()
    check("recovers when replies return", r.runner.frame["link_ok"] is True)

    print()
    print("== a corrupt packet is dropped, and the loop keeps running")
    # 49.9 V, deliberately not the default the frame starts at - otherwise
    # "unchanged" and "wrongly accepted" look identical.
    corrupt = bytearray(build(input_voltage=49.9))
    corrupt[-2] ^= 0xFF
    r = Rig(reply=bytes(corrupt))
    before = r.runner.frame["input_voltage"]
    r.runner.step()
    check("frame not poisoned",
          abs(r.runner.frame["input_voltage"] - before) < 0.001
          and abs(before - 49.9) > 1.0)
    check("survived", r.runner.reads == 1 and r.runner.bad == 1)

    print()
    print("== a uart that throws does not take the dashboard down")

    class Angry(FakeUart):
        def write(self, data):
            raise OSError("uart gone")

    r = Rig(reply=build())
    r.runner.uart = Angry()
    r.runner.step()
    check("caught and counted", r.runner.bad == 1)
    check("still drew a frame", len(r.d.calls) > 0)

    print()
    print("== buttons still work when the ESC is silent")
    r = Rig(reply=b"")
    r.runner.step()
    start = r.app.key
    r.pins[1] = True                 # down
    r.advance(100)
    r.runner.step()
    check("screen changed with no telemetry", r.app.key != start)

    print()
    print("== a hold reaches the menu through the loop")
    r = Rig(reply=build())
    r.runner.step()
    r.pins[2] = True                 # enter, pressed
    r.advance(100)
    r.runner.step()
    r.pins[2] = False                # released -> enter
    r.advance(100)
    r.runner.step()
    check("entered the menu", r.app.state == MENU)

    print()
    print("== the loop drains an animation instead of leaving it half done")
    r = Rig(reply=build(input_voltage=43.2), sweep=True)
    check("boots into the sweep", r.app.state == SWEEP)
    steps = 0
    while r.app.state == SWEEP and steps < 200:
        r.runner.step()
        r.advance(50)
        steps += 1
    check("sweep completed through the loop (%d steps)" % steps,
          r.app.state == SCREEN and steps < 200)

    print()
    print("== the session and the Rint model are wired into the loop")
    r = Rig(reply=build(input_voltage=48.0, rpm=20000, avg_input_current=0.0,
                        temp_fet_filtered=44.0))
    r.runner.step()
    r.advance(1000)
    r.uart.reply = build(input_voltage=46.88, rpm=20000,
                         avg_input_current=28.0, temp_fet_filtered=52.0)
    for _ in range(4):
        r.runner.step()
        r.advance(1000)
    check("session accumulated", r.runner.frame["s_elapsed_ms"] > 0)
    check("peak temperature reached the frame",
          r.runner.frame["s_max_fet"] >= 52.0,
          "got %r" % r.runner.frame["s_max_fet"])
    check("internal resistance estimated (%.4f ohm)" % r.resistance.value,
          r.resistance.value > 0.0)
    check("charge is compensated, not the raw terminal reading",
          r.runner.frame["soc"] > r.board.soc_for_voltage(46.88),
          "%.3f vs %.3f" % (r.runner.frame["soc"] or 0,
                            r.board.soc_for_voltage(46.88)))

    print()
    print("== run() is bounded when asked to be")
    r = Rig(reply=build())
    n = r.runner.run(forever=False, limit=5)
    check("ran exactly five passes", n == 5)
    check("clock advanced by the update period", r.t >= 5 * 50 - 50)

    print()
    if fails:
        print("%d RUNNER TESTS FAILED" % len(fails))
        return 1
    print("all runner tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
