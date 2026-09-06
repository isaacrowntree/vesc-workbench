"""The four screens beside the riding view.

Each is sparse on purpose. A character costs ~8.6 ms on this hardware, so a
screen crowded with numbers is a screen that updates in lurches - the same
lesson the UART reader taught, in a different place.
"""
from .base import RegionScreen, MARGIN, HALF, W

MIN_MS = 60 * 1000
HOUR_MS = 60 * MIN_MS


def _hhmm(ms):
    h = ms // HOUR_MS
    m = (ms % HOUR_MS) // MIN_MS
    return "%d:%02d" % (h, m)


def _km(tacho, b):
    return b.km_for_tacho(tacho)


def _hot(f, b, t):
    return t.temp_color(f.temp_fet_filtered, b.temp_derate_start)


class RangeScreen(RegionScreen):
    """How far is left. The number you actually plan a ride around."""

    def chrome(self, d):
        self.label(d, MARGIN, 24, "RANGE REMAINING")
        self.label(d, MARGIN, 150, "USED")
        self.label(d, MARGIN + HALF, 150, "PACK")
        self.label(d, MARGIN, 226, "TRIP")
        self.label(d, MARGIN + HALF, 226, "EFFICIENCY")

    def _build_regions(self):
        def remaining(f, b):
            left = max(0.0, 1.0 - (f.watt_hours / max(1.0, b.usable_watt_hours)))
            done = _km(f.tachometer_abs_value, b)
            if f.watt_hours < 1 or done < 0.1:
                return "--"
            return "%3d" % round(done * left / max(0.01, 1 - left))
        return (
            ("remain", MARGIN, 44, 200, 60, remaining,
             self.value_painter("remain", MARGIN, 44, scale=6)),
            ("used", MARGIN, 162, HALF, 30,
             lambda f, b: "%4.0f Wh" % f.watt_hours,
             self.value_painter("used", MARGIN, 162)),
            ("soc", MARGIN + HALF, 162, HALF, 30,
             lambda f, b: "%3d%%" % round(100 * b.soc_for_voltage(f.input_voltage)),
             self.value_painter("soc", MARGIN + HALF, 162)),
            ("trip", MARGIN, 238, HALF, 30,
             lambda f, b: "%5.1f" % _km(f.tachometer_abs_value, b),
             self.value_painter("trip", MARGIN, 238)),
            ("eff", MARGIN + HALF, 238, HALF, 30,
             lambda f, b: ("%4.0f" % (f.watt_hours / max(0.1, _km(f.tachometer_abs_value, b)))
                           if f.tachometer_abs_value else "  --"),
             self.value_painter("eff", MARGIN + HALF, 238)),
        )


class OverviewScreen(RegionScreen):
    """Everything at once, for standing still and having a look."""

    ROWS = (("SPEED", "speed"), ("BATTERY", "volts"), ("MOTOR A", "motor"),
            ("PACK A", "pack"), ("FET", "fet"), ("MOTOR C", "mot"))

    def chrome(self, d):
        for i, (label, _) in enumerate(self.ROWS):
            self.label(d, MARGIN, 30 + i * 46, label)

    def _build_regions(self):
        vals = {
            "speed": lambda f, b: "%5.1f" % abs(b.kph_for_erpm(f.rpm)),
            "volts": lambda f, b: "%5.1f" % f.input_voltage,
            "motor": lambda f, b: "%5.0f" % f.avg_motor_current,
            "pack": lambda f, b: "%5.0f" % f.avg_input_current,
            "fet": lambda f, b: "%5.0f" % f.temp_fet_filtered,
            "mot": lambda f, b: "%5.0f" % f.temp_motor_filtered,
        }
        out = []
        for i, (_, key) in enumerate(self.ROWS):
            y = 30 + i * 46
            colour = _hot if key == "fet" else None
            out.append((key, MARGIN, y + 12, W - 2 * MARGIN, 30, vals[key],
                        self.value_painter(key, 110, y + 8, scale=2, color=colour)))
        return tuple(out)


class SessionScreen(RegionScreen):
    """This ride."""

    def chrome(self, d):
        self.label(d, MARGIN, 24, "THIS RIDE")
        for label, x, y in (("DISTANCE", MARGIN, 60), ("MOVING", MARGIN + HALF, 60),
                            ("TOP", MARGIN, 140), ("AVERAGE", MARGIN + HALF, 140),
                            ("ENERGY", MARGIN, 220), ("REGEN", MARGIN + HALF, 220)):
            self.label(d, x, y, label)

    def _build_regions(self):
        return (
            ("dist", MARGIN, 76, HALF, 34,
             lambda f, b: "%5.1f" % _km(f.tachometer_abs_value, b),
             self.value_painter("dist", MARGIN, 76, scale=2)),
            ("time", MARGIN + HALF, 76, HALF, 34,
             lambda f, b: _hhmm(f.time_riding_ms),
             self.value_painter("time", MARGIN + HALF, 76, scale=2)),
            ("top", MARGIN, 156, HALF, 34,
             lambda f, b: "%5.1f" % b.kph_for_erpm(f.max_erpm),
             self.value_painter("top", MARGIN, 156, scale=2)),
            ("avg", MARGIN + HALF, 156, HALF, 34,
             lambda f, b: "%5.1f" % b.kph_for_erpm(f.avg_erpm),
             self.value_painter("avg", MARGIN + HALF, 156, scale=2)),
            ("wh", MARGIN, 236, HALF, 34,
             lambda f, b: "%5.0f" % f.watt_hours,
             self.value_painter("wh", MARGIN, 236, scale=2)),
            ("regen", MARGIN + HALF, 236, HALF, 34,
             lambda f, b: "%5.0f" % f.watt_hours_charged,
             self.value_painter("regen", MARGIN + HALF, 236, scale=2)),
        )


class LifetimeScreen(RegionScreen):
    """Everything the board has ever done. Changes slowly; costs nothing."""

    def chrome(self, d):
        self.label(d, MARGIN, 24, "LIFETIME")
        for label, y in (("KILOMETRES", 60), ("ENERGY", 140), ("TOP SPEED", 220)):
            self.label(d, MARGIN, y, label)

    def _build_regions(self):
        return (
            ("km", MARGIN, 78, W - 2 * MARGIN, 44,
             lambda f, b: "%6.0f" % _km(f.lifetime_tacho, b),
             self.value_painter("km", MARGIN, 78, scale=4)),
            ("wh", MARGIN, 158, W - 2 * MARGIN, 44,
             lambda f, b: "%6.0f" % f.lifetime_wh,
             self.value_painter("wh", MARGIN, 158, scale=4)),
            ("top", MARGIN, 238, W - 2 * MARGIN, 44,
             lambda f, b: "%6.1f" % b.kph_for_erpm(f.max_erpm),
             self.value_painter("top", MARGIN, 238, scale=4)),
        )


ALL = (("riding", None), ("range", RangeScreen), ("overview", OverviewScreen),
       ("session", SessionScreen), ("lifetime", LifetimeScreen))
