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


from screens.board import Board as _Board, DISCHARGE_TICKS  # noqa: F401


class Board(_Board):
    """The device-side board, plus the fixture machinery tests need."""

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
            lifetime_tacho=0, lifetime_wh=0.0,
            # Link health, and the accumulated session. The runner publishes
            # these under a prefix - s_ for this ride, l_ for lifetime - so a
            # screen reads them like any other field and never holds a
            # reference to an accumulator.
            link_ok=True,
            s_trip_km=0.0, s_riding_ms=0, s_elapsed_ms=0, s_max_kph=0.0,
            s_avg_kph=0.0, s_min_voltage=0.0, s_max_fet=0.0,
            s_max_motor_temp=0.0, s_max_current=0.0, s_min_current=0.0,
            s_max_batt_current=0.0, s_wh_spent=0.0, s_wh_per_km=0.0,
            s_range_km=0.0,
            l_trip_km=0.0, l_riding_ms=0, l_max_kph=0.0, l_wh_spent=0.0,
            l_max_fet=0.0, l_max_current=0.0, l_min_voltage=0.0)
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
            lifetime_tacho=9_400_000, lifetime_wh=612.0,
            s_trip_km=12.4, s_riding_ms=42 * 60 * 1000,
            s_elapsed_ms=51 * 60 * 1000, s_max_kph=41.2, s_avg_kph=17.7,
            s_min_voltage=41.3, s_max_fet=68.0, s_max_motor_temp=79.0,
            s_max_current=78.0, s_min_current=-54.0, s_max_batt_current=28.0,
            s_wh_spent=214.0, s_wh_per_km=17.3, s_range_km=19.8,
            l_trip_km=402.6, l_riding_ms=27 * 3600 * 1000, l_max_kph=46.1,
            l_wh_spent=7120.0, l_max_fet=84.0, l_max_current=80.0,
            l_min_voltage=38.9)

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
            "s_trip_km": (0.0, 999.9), "s_max_kph": (0.0, 60.0),
            "s_avg_kph": (0.0, 50.0), "s_min_voltage": (0.0, 50.4),
            "s_max_fet": (0.0, 120.0), "s_max_motor_temp": (0.0, 120.0),
            "s_max_current": (0.0, 100.0), "s_min_current": (-100.0, 0.0),
            "s_max_batt_current": (0.0, 60.0), "s_wh_spent": (0.0, 9999.0),
            "s_wh_per_km": (0.0, 99.9), "s_range_km": (0.0, 199.9),
            "s_riding_ms": (0, 99 * 3600 * 1000),
            "l_trip_km": (0.0, 99999.0), "l_max_kph": (0.0, 60.0),
            "l_wh_spent": (0.0, 999999.0), "l_max_fet": (0.0, 120.0),
            "l_max_current": (0.0, 100.0), "l_min_voltage": (0.0, 50.4),
            "l_riding_ms": (0, 9999 * 3600 * 1000),
        }[field]
