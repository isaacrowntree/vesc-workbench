#!/usr/bin/env python3
"""Trip and lifetime accumulation, replayed from a scripted ride.

Includes the five fields the reference firmware left as TODO - max temps,
max/min current, Wh spent and the two derived from them - because those are
the ones you want after a ride that went wrong.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from harness.telemetry import Board                     # noqa: E402
from screens.session import Session                     # noqa: E402

fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


def near(a, c, tol=0.05):
    return abs(a - c) <= tol


def ride(board, session, seconds, kph, motor_a, batt_a, volts, fet, mot,
         tacho, wh, step_ms=1000):
    """Play a stretch of riding, advancing the ESC's counters as it goes."""
    per = board.km_for_tacho(1) or 1
    for _ in range(seconds):
        f = board.frame(rpm=board.erpm_for_kph(kph), avg_motor_current=motor_a,
                        avg_input_current=batt_a, input_voltage=volts,
                        temp_fet_filtered=fet, temp_motor_filtered=mot,
                        tachometer_abs_value=tacho[0], watt_hours=wh[0])
        session.update(f, step_ms)
        # distance the ESC would have counted in this step
        km = kph * (step_ms / 3600000.0)
        tacho[0] += int(km / per)
        wh[0] += batt_a * volts * (step_ms / 3600000.0)
    return f


def main():
    b = Board()

    print("== a real stretch of riding accumulates what you would expect")
    s = Session(b)
    tacho, wh = [1000], [0.0]
    ride(b, s, 600, 25.0, 18.0, 9.0, 43.2, 42.0, 48.0, tacho, wh)   # 10 min
    check("trip is about 4.2 km", near(s.trip_km, 4.17, 0.1),
          "got %.3f" % s.trip_km)
    check("riding time is 10 min", s.riding_ms == 600000)
    check("average speed is the cruise speed", near(s.avg_kph, 25.0, 0.5),
          "got %.2f" % s.avg_kph)
    check("top speed recorded", near(s.max_kph, 25.0, 0.1))

    print()
    print("== the fields their firmware left as TODO")
    ride(b, s, 20, 45.0, 78.0, 29.0, 41.0, 71.0, 83.0, tacho, wh)   # hard pull
    check("max fet temp", near(s.max_fet, 71.0))
    check("max motor temp", near(s.max_motor_temp, 83.0))
    check("max motor current", near(s.max_current, 78.0))
    check("max pack current", near(s.max_batt_current, 29.0))
    check("min voltage under load", near(s.min_voltage, 41.0))
    check("watt hours spent", s.wh_spent > 1.0, "got %.2f" % s.wh_spent)
    check("wh per km is plausible", 5.0 < s.wh_per_km < 60.0,
          "got %.1f" % s.wh_per_km)

    print()
    print("== regen is its own extreme, not folded into the peaks")
    ride(b, s, 10, 30.0, -60.0, -8.0, 49.5, 60.0, 70.0, tacho, wh)
    check("min motor current", near(s.min_current, -60.0))
    check("min pack current", near(s.min_batt_current, -8.0))
    check("max motor current kept", near(s.max_current, 78.0))

    print()
    print("== range needs evidence before it will answer")
    fresh = Session(b)
    f = b.frame(input_voltage=43.2)
    check("no distance, no range", fresh.range_km(f) == 0.0)
    ride(b, fresh, 30, 25.0, 18.0, 9.0, 43.2, 40.0, 45.0, [500], [0.0])
    check("still cautious after 200 m", fresh.range_km(f) == 0.0,
          "got %.1f km from %.3f km of riding" % (fresh.range_km(f), fresh.trip_km))
    check("answers once there is a ride behind it",
          s.range_km(f) > 1.0, "got %.1f" % s.range_km(f))

    print()
    print("== a stop is not riding, but is still elapsed")
    s2 = Session(b)
    ride(b, s2, 60, 0.0, 0.0, 0.0, 43.2, 30.0, 30.0, [100], [0.0])
    check("elapsed counts", s2.elapsed_ms == 60000)
    check("riding does not", s2.riding_ms == 0)
    check("average speed is zero, not a division error", s2.avg_kph == 0.0)

    print()
    print("== a resting pack is not mistaken for a sagging one")
    s3 = Session(b)
    ride(b, s3, 10, 0.0, 0.0, 0.0, 36.4, 25.0, 25.0, [0], [0.0])
    check("no load, no sag recorded", s3.min_voltage == 0.0)
    ride(b, s3, 10, 20.0, 30.0, 15.0, 41.5, 40.0, 45.0, [0], [0.0])
    check("under load it records", near(s3.min_voltage, 41.5))

    print()
    print("== the ESC resetting its counters mid-ride does not corrupt the trip")
    s4 = Session(b)
    tacho4, wh4 = [500000], [120.0]
    ride(b, s4, 60, 25.0, 18.0, 9.0, 43.2, 40.0, 45.0, tacho4, wh4)
    before = s4.trip_km
    tacho4[0] = 0                     # ESC rebooted, counters back to zero
    wh4[0] = 0.0
    ride(b, s4, 60, 25.0, 18.0, 9.0, 43.2, 40.0, 45.0, tacho4, wh4)
    check("trip did not go negative", s4.trip_km >= 0.0)
    check("trip kept accumulating", s4.trip_km > 0.0)
    check("and did not jump wildly", s4.trip_km < before + 1.0,
          "before %.3f after %.3f" % (before, s4.trip_km))

    print()
    print("== a dead link contributes nothing")
    s5 = Session(b)
    dead = b.frame(rpm=b.erpm_for_kph(40.0), temp_fet_filtered=90.0)
    dead["link_ok"] = False
    for _ in range(30):
        s5.update(dead, 1000)
    check("no elapsed time", s5.elapsed_ms == 0)
    check("no phantom top speed", s5.max_kph == 0.0)
    check("no phantom temperature", s5.max_fet == 0.0)

    print()
    print("== lifetime merges sessions without losing the extremes")
    life = Session(b, lifetime=True)
    life.merge(s)
    life.merge(s2)
    check("distance adds", near(life.trip_km, s.trip_km + s2.trip_km, 0.01))
    check("time adds", life.riding_ms == s.riding_ms + s2.riding_ms)
    check("top speed is the highest", near(life.max_kph, max(s.max_kph, s2.max_kph)))
    check("min current is the lowest", near(life.min_current, s.min_current))
    check("min voltage is the lowest seen under load",
          near(life.min_voltage, s.min_voltage))

    print()
    print("== a session round-trips through storage")
    saved = s.to_dict()
    restored = Session(b).load(saved)
    check("every field survives",
          all(near(getattr(restored, k), getattr(s, k), 0.001)
              for k in Session.KEYS),
          "differs")

    print()
    if fails:
        print("%d SESSION TESTS FAILED" % len(fails))
        return 1
    print("all session tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
