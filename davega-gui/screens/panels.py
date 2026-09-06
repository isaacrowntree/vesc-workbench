"""The four screens beside the riding view.

Each is sparse on purpose. A character costs ~8.6 ms on this hardware, so a
screen crowded with numbers is a screen that updates in lurches - the same
lesson the UART reader taught, in a different place.
"""
from .base import (RegionScreen, MARGIN, W, col_x, row_y, BODY_TOP,
                   HERO, PRIMARY, VALUE)

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

    title = "RANGE"

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        self.label(d, col_x(0), BODY_TOP, "RANGE KM")
        for i, name in enumerate(("Wh", "CHARGE")):
            self.label(d, col_x(i), row_y(3), name)
        for i, name in enumerate(("TRIP", "Wh/KM")):
            self.label(d, col_x(i), row_y(5), name)

    def _build_regions(self):
        def remaining(f, b):
            left = max(0.0, 1.0 - (f.watt_hours / max(1.0, b.usable_watt_hours)))
            done = _km(f.tachometer_abs_value, b)
            if f.watt_hours < 1 or done < 0.1:
                return "--"
            return "%3d" % round(done * left / max(0.01, 1 - left))
        return self.status_regions() + (
            ("remain", col_x(0), BODY_TOP + 14, 200, 48, remaining,
             self.value_painter("remain", col_x(0), BODY_TOP + 14, scale=HERO)),
            ("used", col_x(0), row_y(3) + 12, 100, 24,
             lambda f, b: "%5.0f" % f.watt_hours,
             self.value_painter("used", col_x(0), row_y(3) + 12, scale=VALUE)),
            ("soc", col_x(1), row_y(3) + 12, 100, 24,
             lambda f, b: "%4d%%" % round(100 * b.soc_for_voltage(f.input_voltage)),
             self.value_painter("soc", col_x(1), row_y(3) + 12, scale=VALUE)),
            ("trip", col_x(0), row_y(5) + 12, 100, 24,
             lambda f, b: "%5.1f" % _km(f.tachometer_abs_value, b),
             self.value_painter("trip", col_x(0), row_y(5) + 12, scale=VALUE)),
            ("eff", col_x(1), row_y(5) + 12, 100, 24,
             lambda f, b: ("%5.0f" % (f.watt_hours / max(0.1, _km(f.tachometer_abs_value, b)))
                           if f.tachometer_abs_value else "  --"),
             self.value_painter("eff", col_x(1), row_y(5) + 12, scale=VALUE)),
        )


class OverviewScreen(RegionScreen):
    """Everything at once, for standing still and having a look."""

    ROWS = (("SPEED", "speed"), ("BATTERY", "volts"), ("MOTOR A", "motor"),
            ("PACK A", "pack"), ("FET", "fet"), ("MOTOR C", "mot"))

    title = "OVERVIEW"

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        for i, (label, _) in enumerate(self.ROWS):
            self.label(d, col_x(0), BODY_TOP + i * 44, label)

    def _build_regions(self):
        vals = {
            "speed": lambda f, b: "%5.1f" % abs(b.kph_for_erpm(f.rpm)),
            "volts": lambda f, b: "%5.1f" % f.input_voltage,
            "motor": lambda f, b: "%5.0f" % f.avg_motor_current,
            "pack": lambda f, b: "%5.0f" % f.avg_input_current,
            "fet": lambda f, b: "%5.0f" % f.temp_fet_filtered,
            "mot": lambda f, b: "%5.0f" % f.temp_motor_filtered,
        }
        out = list(self.status_regions())
        for i, (_, key) in enumerate(self.ROWS):
            y = BODY_TOP + i * 44
            colour = _hot if key == "fet" else None
            out.append((key, col_x(1), y, 108, 26, vals[key],
                        self.value_painter(key, col_x(1), y, scale=VALUE,
                                           color=colour)))
        return tuple(out)


class SessionScreen(RegionScreen):
    """This ride, including every field their firmware left as TODO.

    Two columns, three rows: what you did, what it cost, what it survived.
    The bottom row is the one their TODO list was about - peak temperature,
    peak draw, deepest sag - and it is the row you look at after a ride that
    went wrong.
    """

    title = "THIS RIDE"

    PAIRS = (("DIST KM", "MOVING"),
             ("TOP", "AVG"),
             ("Wh", "Wh/KM"),
             ("PEAK A", "FET C"))

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        for r, pair in enumerate(self.PAIRS):
            for i, label in enumerate(pair):
                self.label(d, col_x(i), row_y(r) - 2, label)

    def _v(self, key, r, i, fn):
        return (key, col_x(i), row_y(r) + 10, 100, 22, fn,
                self.value_painter(key, col_x(i), row_y(r) + 10, scale=VALUE))

    def _build_regions(self):
        hot = lambda f, b, t: t.temp_color(f["s_max_fet"], b.temp_derate_start)
        return self.status_regions() + (
            self._v("dist", 0, 0, lambda f, b: "%4.1f" % f["s_trip_km"]),
            self._v("time", 0, 1, lambda f, b: _hhmm(f["s_riding_ms"])),
            self._v("top", 1, 0, lambda f, b: "%4.1f" % f["s_max_kph"]),
            self._v("avg", 1, 1, lambda f, b: "%4.1f" % f["s_avg_kph"]),
            self._v("wh", 2, 0, lambda f, b: "%4.0f" % f["s_wh_spent"]),
            self._v("whkm", 2, 1,
                    lambda f, b: ("%4.1f" % f["s_wh_per_km"]
                                  if f["s_wh_per_km"] else "  --")),
            self._v("peak", 3, 0, lambda f, b: "%4.0f" % f["s_max_current"]),
            ("maxfet", col_x(1), row_y(3) + 10, 100, 22,
             lambda f, b: "%4.0f" % f["s_max_fet"],
             self.value_painter("maxfet", col_x(1), row_y(3) + 10,
                                scale=VALUE, color=hot)),
        )


class LifetimeScreen(RegionScreen):
    """Everything the board has ever done. Same shape as the ride screen, so
    the pair read as two views of one thing rather than two designs."""

    title = "LIFETIME"

    PAIRS = (("DIST KM", "MOVING"),
             ("TOP", "Wh"),
             ("PEAK A", "FET C"))

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        for r, pair in enumerate(self.PAIRS):
            for i, label in enumerate(pair):
                self.label(d, col_x(i), row_y(r * 2) - 2, label)

    def _v(self, key, r, i, fn, scale=VALUE):
        return (key, col_x(i), row_y(r * 2) + 10, 104, 26, fn,
                self.value_painter(key, col_x(i), row_y(r * 2) + 10, scale=scale))

    def _build_regions(self):
        return self.status_regions() + (
            self._v("km", 0, 0, lambda f, b: "%5.0f" % f["l_trip_km"]),
            self._v("time", 0, 1, lambda f, b: _hhmm(f["l_riding_ms"])),
            self._v("top", 1, 0, lambda f, b: "%5.1f" % f["l_max_kph"]),
            self._v("wh", 1, 1, lambda f, b: "%5.0f" % f["l_wh_spent"]),
            self._v("peak", 2, 0, lambda f, b: "%5.0f" % f["l_max_current"]),
            self._v("fet", 2, 1, lambda f, b: "%5.0f" % f["l_max_fet"]),
        )


ALL = (("riding", None), ("range", RangeScreen), ("overview", OverviewScreen),
       ("session", SessionScreen), ("lifetime", LifetimeScreen))
