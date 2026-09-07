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
from screens.session import Session, Resistance         # noqa: E402

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
    print("== internal resistance, the Rint model's R0")
    # V_terminal = OCV(SoC) - I*R0. Recovering R0 from the data we already
    # sample is what lets the charge gauge stop flinching under throttle.
    r = Resistance(b.cells)
    truth = 0.040
    check("says nothing from a single sample",
          r.update(48.0, 0.0) == 0.0)
    check("still nothing without a spread of current",
          r.update(47.9, 2.0) == 0.0)
    for cur in (0.0, 5.0, 12.0, 28.0, 3.0):
        r.update(48.0 - cur * truth, cur)
    check("recovers R0 from a spread (%.4f vs %.4f)" % (r.value, truth),
          near(r.value, truth, 0.004))
    check("reports per-cell milliohms", near(r.milliohms_per_cell, 3.33, 0.4),
          "got %.2f" % r.milliohms_per_cell)

    noisy = Resistance(b.cells)
    for cur in (0.0, 30.0):
        noisy.update(48.0 + cur * 0.01, cur)      # voltage RISING under load
    check("refuses a negative resistance", noisy.value == 0.0)

    print()
    print("== state of charge that does not flinch under throttle")
    loaded_v = 48.0 - 28.0 * truth
    naive = b.soc_for_voltage(loaded_v)
    real = b.soc_loaded(loaded_v, 28.0, truth)
    check("the naive reading is lower under load (%.0f%% vs %.0f%%)"
          % (100 * naive, 100 * real), real > naive)
    check("compensated matches the resting reading",
          near(real, b.soc_for_voltage(48.0), 0.02),
          "%.3f vs %.3f" % (real, b.soc_for_voltage(48.0)))
    check("at rest the two agree",
          near(b.soc_loaded(48.0, 0.0, truth), b.soc_for_voltage(48.0), 0.001))

    print()
    print("== a falling pack costs power and range together")
    check("full pack is full power", near(b.power_fraction(b.v_full), 1.0, 0.001))
    check("power falls with voltage",
          b.power_available_w(40.0) < b.power_available_w(45.8) < b.power_available_w(50.4))
    check("power at 40 V is about four fifths of full",
          0.78 < b.power_fraction(40.0) < 0.81,
          "got %.3f" % b.power_fraction(40.0))
    check("a full pack costs nothing extra", near(b.sag_factor(1.0), 1.0, 0.001))
    check("an empty pack costs much more per km", b.sag_factor(0.0) > 1.8,
          "got %.2f" % b.sag_factor(0.0))
    check("the cost rises monotonically as it empties",
          all(b.sag_factor(x / 10.0) >= b.sag_factor((x + 1) / 10.0)
              for x in range(10)))

    print()
    print("== sag-aware range is shorter than the naive estimate")
    # The naive answer divides remaining energy by today's rate. Today's rate
    # is not what the last kilometres will cost, so it flatters the rider -
    # which is the wrong direction for a number people plan a route around.
    naive = b.usable_watt_hours * b.soc_for_voltage(45.8) / 18.7
    real = b.range_km(18.7, 45.8)
    check("shorter than naive (%.1f vs %.1f km)" % (real, naive), real < naive)
    check("not absurdly shorter", real > naive * 0.6,
          "%.1f vs %.1f" % (real, naive))
    check("a full pack goes further than a half one",
          b.range_km(18.7, b.v_full) > b.range_km(18.7, 43.2))
    check("no consumption, no answer", b.range_km(0.0, 45.8) == 0.0)
    check("an empty pack offers nothing", b.range_km(18.7, b.v_empty) < 0.5,
          "got %.2f" % b.range_km(18.7, b.v_empty))

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
    print("== range answers from cold, on a borrowed rate")
    # The moment a rider most wants a range is before they have ridden far
    # enough to have measured one. Two dashes at the kerb is the failure this
    # guards against.
    b = Board()
    cold = Session(b)
    f = b.nominal()
    check("no evidence of its own yet", not cold.measured())
    est = cold.range_km(f, 18.0)
    check("but it still answers %.0f km" % est, est > 0.0)
    check("and says the figure is borrowed", not cold.measured())
    check("with no rate at all it declines rather than invents",
          cold.range_km(f, 0.0) == 0.0)

    print()
    if fails:
        print("%d SESSION TESTS FAILED" % len(fails))
        return 1
    print("all session tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())