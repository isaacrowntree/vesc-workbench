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

    def erpm_for_kph(self, kph):
        rev_per_km = 1000.0 / (math.pi * self.wheel_m)
        wheel_rpm = kph * rev_per_km / 60.0
        return wheel_rpm * self.gear_ratio * self.pole_pairs

    def kph_for_erpm(self, erpm):
        wheel_rpm = erpm / self.pole_pairs / self.gear_ratio
        return wheel_rpm * 60.0 * math.pi * self.wheel_m / 1000.0

    # -- frames -----------------------------------------------------------
