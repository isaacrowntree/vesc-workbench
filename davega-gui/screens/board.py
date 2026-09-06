"""Board geometry and the conversions that depend on it.

Device-side code: kept small deliberately, because everything imported here
costs ESP32 RAM. The envelope, sweeps and fixture machinery live in
`harness/telemetry.py`, which never goes near the device.

Every conversion below was checked against the display's own
`frozen.screen_values` rather than derived and hoped for.
"""
import math


# The DAVEGA's own Li-ion discharge curve, read off frozen.screen_values on the
# device: eleven cell voltages from empty to full. State of charge is piecewise
# linear between them, which is a great deal closer to how a pack behaves than
# a straight line from cutoff to full.
DISCHARGE_TICKS = {
    "liion": (3.2, 3.39, 3.48, 3.57, 3.66, 3.75, 3.84, 3.93, 4.02, 4.11, 4.2),
    "lipo": (3.4, 3.5, 3.64, 3.71, 3.78, 3.85, 3.92, 3.99, 4.06, 4.13, 4.2),
    "lifepo4": (2.7, 3.1, 3.16, 3.18, 3.2, 3.22, 3.24, 3.26, 3.28, 3.3, 3.6),
}


class Board:
    """A board's configuration, which is what turns raw fields into bounds.

    Defaults are the reference Nazare, every value read back from the ESC and
    the display rather than assumed:
      12s4p, 17 Ah, 80 A/side motor, 30/-8 A/side battery, 4.2:1, 200 mm.
    """

    def __init__(self, cells=12, parallel=4, cell_ah=4.25,
                 cell_full=4.2, cell_nominal=3.6, cell_empty=3.0,
                 motor_current=80.0, battery_current=30.0, regen_current=-8.0,
                 pole_pairs=7, gear_ratio=4.2, wheel_m=0.2,
                 temp_derate_start=85.0, temp_derate_end=100.0, usable=0.8):
        self.cells = cells
        self.parallel = parallel
        self.cell_ah = cell_ah
        self.v_full = cells * cell_full
        self.v_nominal = cells * cell_nominal
        self.v_empty = cells * cell_empty
        self.motor_current = motor_current
        self.battery_current = battery_current
        self.regen_current = regen_current
        self.pole_pairs = pole_pairs
        self.gear_ratio = gear_ratio
        self.wheel_m = wheel_m
        self.usable = usable
        self.temp_derate_start = temp_derate_start
        self.temp_derate_end = temp_derate_end

    # -- derived ----------------------------------------------------------

    @property
    def amp_hours(self):
        return self.parallel * self.cell_ah

    @property
    def watt_hours(self):
        return self.amp_hours * self.v_nominal

    def km_for_tacho(self, tacho):
        """Tachometer steps to kilometres.

        Six steps per electrical revolution, matching the device's own
        tachometer_to_km - checked against it rather than derived from first
        principles, because the first-principles version was out by two.
        """
        revs = tacho / (self.pole_pairs * 6.0) / self.gear_ratio
        return revs * math.pi * self.wheel_m / 1000.0

    def soc_for_voltage(self, volts, cell_type="liion"):
        """State of charge from pack voltage, along the discharge curve."""
        ticks = DISCHARGE_TICKS[cell_type]
        v = volts / self.cells
        if v <= ticks[0]:
            return 0.0
        if v >= ticks[-1]:
            return 1.0
        span = 1.0 / (len(ticks) - 1)
        for i in range(len(ticks) - 1):
            if v <= ticks[i + 1]:
                lo, hi = ticks[i], ticks[i + 1]
                return span * (i + (v - lo) / (hi - lo))
        return 1.0

    @property
    def usable_watt_hours(self):
        """What the display calls max_wh: capacity times the usable fraction."""
        return self.amp_hours * self.v_nominal * self.usable

    # -- what a falling pack actually costs -------------------------------
    #
    # Two things get worse together as a pack empties, and a range estimate
    # that assumes a constant cost per kilometre misses both:
    #
    #   Power is V x I, and the battery current limit does not move. At 50.4 V
    #   a 60 A limit is 3.0 kW; at 40 V the same limit is 2.4 kW. You lose a
    #   fifth of the punch without touching a setting.
    #
    #   Sag deepens as the pack empties, because cell internal resistance
    #   rises at low state of charge. So the voltage you actually get under
    #   load falls faster than the resting voltage does, and to make the same
    #   mechanical power you draw more current - and I^2R losses grow with the
    #   square of it.
    #
    # The result is that the last third of a pack costs noticeably more per
    # kilometre than the first third.

    @property
    def power_limit_w(self):
        """Full-pack power at the battery current limit, both sides."""
        return self.v_full * self.battery_current * 2

    def power_available_w(self, volts):
        return volts * self.battery_current * 2

    def power_fraction(self, volts):
        """How much of the board's full punch is left, 0..1."""
        return max(0.0, min(1.0, volts / self.v_full))

    # The standard model for this is the Rint equivalent circuit:
    #
    #     V_terminal = OCV(SoC) - I * R0
    #
    # An open-circuit voltage that depends only on state of charge, minus the
    # drop across an internal resistance. Everything below is that, rather
    # than a curve fitted to intuition. (The Thevenin model adds an RC pair
    # for polarisation transients; at a 5 Hz sample rate on a skateboard that
    # is detail we cannot resolve and do not need.)

    def ocv(self, volts, current, r_internal):
        """Recover open-circuit voltage from a reading taken under load.

        This is the fix for the complaint every rider has: the battery gauge
        dropping while you accelerate and recovering when you coast. It was
        never the charge moving - it was the sag.
        """
        return volts + current * r_internal

    def soc_loaded(self, volts, current, r_internal, cell_type="liion"):
        """State of charge that does not flinch under throttle."""
        return self.soc_for_voltage(self.ocv(volts, current, r_internal),
                                    cell_type)

    def sag_factor(self, soc, r_internal=None, current=None):
        """How much worse each kilometre gets as the pack empties.

        With a measured R0 this is the real thing: the extra energy is the
        I^2*R0 heat, and the current needed for a given power rises as voltage
        falls. Without one it falls back to the voltage ratio squared, which
        has the right shape and no calibration.
        """
        soc = 0.0 if soc < 0 else 1.0 if soc > 1 else soc
        v = self.v_empty + (self.v_full - self.v_empty) * soc
        ratio = self.v_full / max(1.0, v)
        if not r_internal or not current:
            return ratio * ratio
        # Power held constant, so current scales with the voltage ratio; the
        # resistive share of the draw grows with the square of it.
        i_now = current * ratio
        useful = v * i_now
        loss = i_now * i_now * r_internal
        base_loss = current * current * r_internal
        base = self.v_full * current
        if useful <= 0 or base <= 0:
            return ratio * ratio
        return ((useful + loss) / useful) / ((base + base_loss) / base) * ratio

    def range_km(self, wh_per_km_now, volts, cell_type="liion"):
        """Remaining range, taking the rising cost into account.

        Integrates the pack downward in ten steps rather than dividing the
        remaining energy by today's rate, because that rate is not what the
        last kilometres will cost.
        """
        if wh_per_km_now <= 0.0:
            return 0.0
        soc = self.soc_for_voltage(volts, cell_type)
        remaining = self.usable_watt_hours * soc
        # today's rate, normalised back to what it would be at a full pack
        base = wh_per_km_now / self.sag_factor(soc)
        km = 0.0
        steps = 10
        for i in range(steps):
            s = soc * (1.0 - i / float(steps))
            chunk = remaining / steps
            km += chunk / (base * self.sag_factor(s))
        return km

    def erpm_for_kph(self, kph):
        rev_per_km = 1000.0 / (math.pi * self.wheel_m)
        wheel_rpm = kph * rev_per_km / 60.0
        return wheel_rpm * self.gear_ratio * self.pole_pairs

    def kph_for_erpm(self, erpm):
        wheel_rpm = erpm / self.pole_pairs / self.gear_ratio
        return wheel_rpm * 60.0 * math.pi * self.wheel_m / 1000.0

    # -- frames -----------------------------------------------------------
