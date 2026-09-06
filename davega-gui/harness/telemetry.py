"""The telemetry a screen renders from, and the envelope it has to survive.

The 14 fields are exactly what the DAVEGA parses - read off `VESC_VALUES_DESCR`
on the device itself, not guessed. The bounds come from configuration read back
from the ESC and verified, so fixtures are derived rather than invented, and
there is no capture step.

    board = Board()                 # the reference Nazare
    frame = board.nominal()         # a plausible mid-ride frame
    for f in board.envelope():      # every extreme worth rendering
        ...
"""
import math

# name -> (kind, scale) as the device's uctypes descriptor lays them out.
FIELDS = (
    ("temp_fet_filtered", "i16", 10.0),
    ("temp_motor_filtered", "i16", 10.0),
    ("duty", "i16", 1000.0),
    ("input_voltage", "i16", 10.0),
    ("avg_motor_current", "i32", 100.0),
    ("avg_input_current", "i32", 100.0),
    ("rpm", "i32", 1.0),
    ("amp_hours", "i32", 10000.0),
    ("amp_hours_charged", "i32", 10000.0),
    ("watt_hours", "i32", 10000.0),
    ("watt_hours_charged", "i32", 10000.0),
    ("tachometer_abs_value", "i32", 1.0),
    ("fault", "u8", 1.0),
    ("can_id", "u8", 1.0),
)

# The display's own fault names, read out of its firmware image.
FAULTS = (
    "NONE", "OVER VOLTAGE", "UNDER VOLTAGE", "DRV", "ABS OVER CURRENT",
    "OVER TEMP FET", "OVER TEMP MOTOR", "GD OVER VOLTAGE", "GD UNDER VOLTAGE",
    "MCU UNDER VOLTAGE", "WATCHDOG RESET", "ENCODER SPI FAULT",
    "SINCOS BELOW MIN", "SINCOS ABOVE MAX", "FLASH CORRUPTION",
    "CURRENT SENSOR 1", "CURRENT SENSOR 2", "CURRENT SENSOR 3",
    "UNBLNCD CURRENT",
)


# Offsets and widths straight off the device's VESC_VALUES_DESCR: the uctypes
# descriptor encodes kind in the top bits and offset in the low ones.
#   0x18000000 | off -> INT16 (big endian)   0x28000000 | off -> INT32
LAYOUT = (
    ("temp_fet_filtered", 0, 2, 10.0),
    ("temp_motor_filtered", 2, 2, 10.0),
    ("avg_motor_current", 4, 4, 100.0),
    ("avg_input_current", 8, 4, 100.0),
    ("duty", 12, 2, 1000.0),
    ("rpm", 14, 4, 1.0),
    ("input_voltage", 18, 2, 10.0),
    ("amp_hours", 20, 4, 10000.0),
    ("amp_hours_charged", 24, 4, 10000.0),
    ("watt_hours", 28, 4, 10000.0),
    ("watt_hours_charged", 32, 4, 10000.0),
    ("tachometer_abs_value", 36, 4, 1.0),
    ("fault", 40, 1, 1.0),
    ("can_id", 41, 1, 1.0),
)
VALUES_SIZE = 42


def encode(frame):
    """Pack a Frame into the 42 bytes the display parses.

    Lets a host-built frame be pushed into the device's own Vesc object, so
    the stock screens can be asked to render it and their drawing captured.
    """
    buf = bytearray(VALUES_SIZE)
    for name, off, width, scale in LAYOUT:
        v = int(round(frame[name] * scale))
        if width == 1:
            buf[off] = v & 0xFF
            continue
        lo = -(1 << (width * 8 - 1))
        hi = (1 << (width * 8 - 1)) - 1
        v = max(lo, min(hi, v))
        buf[off:off + width] = (v & ((1 << (width * 8)) - 1)).to_bytes(width, "big")
    return bytes(buf)


class Frame(dict):
    """One telemetry sample, in real units."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


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

    def frame(self, **over):
        f = Frame(
            temp_fet_filtered=25.0, temp_motor_filtered=25.0, duty=0.0,
            input_voltage=self.v_nominal, avg_motor_current=0.0,
            avg_input_current=0.0, rpm=0.0, amp_hours=0.0,
            amp_hours_charged=0.0, watt_hours=0.0, watt_hours_charged=0.0,
            tachometer_abs_value=0, fault=0, can_id=123,
            # Session and lifetime aggregates. The ESC does not send these -
            # the display accumulates them - but screens render them, so they
            # belong in the frame the screens are tested against.
            max_erpm=0.0, avg_erpm=0.0, time_riding_ms=0,
            lifetime_tacho=0, lifetime_wh=0.0)
        f.update(over)
        return f

    def nominal(self):
        """Cruising: the frame most of a ride looks like."""
        return self.frame(
            rpm=self.erpm_for_kph(25.0), duty=0.45,
            avg_motor_current=18.0, avg_input_current=9.0,
            input_voltage=self.v_nominal, temp_fet_filtered=42.0,
            temp_motor_filtered=48.0, amp_hours=self.amp_hours * 0.35,
            watt_hours=self.watt_hours * 0.35, tachometer_abs_value=120000,
            max_erpm=self.erpm_for_kph(41.0), avg_erpm=self.erpm_for_kph(19.0),
            time_riding_ms=42 * 60 * 1000,
            lifetime_tacho=9_400_000, lifetime_wh=612.0)

    def envelope(self):
        """Every extreme worth rendering, named. A real ride produces few of
        these; a screen still has to survive all of them."""
        top = self.erpm_for_kph(45.0)
        return [
            ("standstill", self.frame()),
            ("cruise", self.nominal()),
            ("full_throttle", self.frame(
                rpm=top, duty=0.95, avg_motor_current=self.motor_current,
                avg_input_current=self.battery_current,
                input_voltage=self.v_empty + 2.0, temp_fet_filtered=72.0,
                temp_motor_filtered=80.0, amp_hours=self.amp_hours * 0.7,
                watt_hours=self.watt_hours * 0.7)),
            ("hard_regen", self.frame(
                rpm=self.erpm_for_kph(30.0), duty=-0.3,
                avg_motor_current=-self.motor_current,
                avg_input_current=self.regen_current,
                input_voltage=self.v_full - 0.5,
                amp_hours=self.amp_hours * 0.2,
                amp_hours_charged=self.amp_hours * 0.05,
                watt_hours_charged=self.watt_hours * 0.05)),
            ("thermal_derate", self.frame(
                rpm=self.erpm_for_kph(20.0), duty=0.6,
                avg_motor_current=40.0, avg_input_current=20.0,
                temp_fet_filtered=self.temp_derate_end,
                temp_motor_filtered=self.temp_derate_end)),
            ("battery_empty", self.frame(
                rpm=self.erpm_for_kph(8.0), duty=0.3,
                input_voltage=self.v_empty, avg_motor_current=12.0,
                avg_input_current=6.0, amp_hours=self.amp_hours,
                watt_hours=self.watt_hours,
                tachometer_abs_value=999999)),
            ("battery_full", self.frame(input_voltage=self.v_full)),
            ("fault_drv", self.frame(
                rpm=top, duty=0.9, fault=3,
                avg_motor_current=self.motor_current)),
            ("second_motor", self.frame(
                can_id=124, rpm=self.erpm_for_kph(25.0), duty=0.45,
                avg_motor_current=18.0)),
        ]

    def sweep(self, field, steps=9):
        """Every value of one field across its full range, for property tests.
        The class of bug this catches is 'fine until the number reaches three
        digits', which nobody thinks to write a case for."""
        lo, hi = self.range_of(field)
        for i in range(steps):
            v = lo + (hi - lo) * i / (steps - 1)
            yield v, self.frame(**{field: v})

    def range_of(self, field):
        return {
            "temp_fet_filtered": (-20.0, self.temp_derate_end + 20),
            "temp_motor_filtered": (-20.0, self.temp_derate_end + 20),
            "duty": (-1.0, 1.0),
            "input_voltage": (self.v_empty - 4, self.v_full),
            "avg_motor_current": (-self.motor_current, self.motor_current),
            "avg_input_current": (self.regen_current, self.battery_current),
            "rpm": (-self.erpm_for_kph(50.0), self.erpm_for_kph(50.0)),
            "amp_hours": (0.0, self.amp_hours),
            "amp_hours_charged": (0.0, self.amp_hours),
            "watt_hours": (0.0, self.watt_hours),
            "watt_hours_charged": (0.0, self.watt_hours),
            "tachometer_abs_value": (0, 9999999),
            "fault": (0, len(FAULTS) - 1),
            "can_id": (0, 253),
            "max_erpm": (0.0, self.erpm_for_kph(60.0)),
            "avg_erpm": (0.0, self.erpm_for_kph(50.0)),
            "time_riding_ms": (0, 99 * 3600 * 1000),
            "lifetime_tacho": (0, 99_999_999),
            "lifetime_wh": (0.0, 99999.0),
        }[field]
