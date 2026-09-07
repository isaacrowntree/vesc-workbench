"""The four screens beside the riding view.

Each is sparse on purpose. A character costs ~8.6 ms on this hardware, so a
screen crowded with numbers is a screen that updates in lurches - the same
lesson the UART reader taught, in a different place.
"""
from . import bigfont, widgets
from .base import (RegionScreen, MARGIN, W, H, col_x, BODY_TOP, VALUE, LABEL)

# The body runs from under the header to above the page dots. Rows are spread
# across all of it: the first cut of these screens stopped two thirds down and
# left the rest black, which on a 2.8 inch panel is most of what you are
# looking at.
BODY_BOT = H - 22
# The grid's own columns, so the panels line up with every other screen.
COL_L, COL_R = col_x(0), col_x(1)
# Four characters at scale 8 is 128 px, and the right column starts at 124 -
# so the widest value has to fit 116. Scale 6 gives 24 x 30 a character, which
# still dwarfs the 16 px text this replaced.
VAL_S = 6


ROW_H = 12 + bigfont.char_h(VAL_S)      # label above value


def _rows(n):
    """Row tops, spread so the LAST row's value ends at the bottom of the body.

    Dividing the height by the row count leaves a row's worth of black under
    the final row, which is what made the first cut of these screens look like
    they stopped two thirds of the way down.
    """
    if n < 2:
        return [BODY_TOP]
    step = (BODY_BOT - BODY_TOP - ROW_H) // (n - 1)
    return [BODY_TOP + i * step for i in range(n)]

MIN_MS = 60 * 1000
HOUR_MS = 60 * MIN_MS


MAX_CHARS = 4          # what a column can hold at VAL_S without overflowing


def _hhmm(ms):
    """h:mm while it fits, whole hours once it does not.

    A lifetime figure of 27:00 is five characters, and five characters at this
    size runs off the right edge of the panel.
    """
    h = ms // HOUR_MS
    if h >= 10:
        # Past ten hours the minutes stop mattering, and "27:00" is five
        # characters where a column holds four. The label says HOURS.
        return "%d" % h
    return "%d:%02d" % (h, (ms % HOUR_MS) // MIN_MS)


def _km(tacho, b):
    return b.km_for_tacho(tacho)


def _hot_session(f, b, t):
    return t.temp_color(f["s_max_fet"], b.temp_derate_start)


def _hot(f, b, t):
    # A frame is a dict, not an object. Attribute access here raised only when
    # the FET reading crossed into the warning band, which is the one moment
    # the screen has something urgent to say.
    return t.temp_color(f["temp_fet_filtered"], b.temp_derate_start)


class Panel(RegionScreen):
    """Label/value pairs in two columns, filling the height.

    Values are drawn with bigfont: at scale 8 a digit is 32x40, which is
    readable at arm's length. The old small text was not.
    """

    PAIRS = ()

    def chrome(self, d):
        RegionScreen.chrome(self, d)
        ys = _rows(len(self.PAIRS))
        for y, pair in zip(ys, self.PAIRS):
            for x, (label, _) in zip((COL_L, COL_R), pair):
                if label:
                    self.label(d, x, y, label)

    @staticmethod
    def _fit(fn):
        """Keep a value inside the column it was given.

        Every cell is `MAX_CHARS` wide because that is what fits at this size.
        A longer value does not clip, it draws past the edge of the panel - so
        the decimals go first, and then the number itself is clamped. A trip
        of 9999 km reading 9999 is wrong in a way nobody will ever see; a trip
        of 9999 km painting over the bezel is a crash.
        """
        def value(f, b):
            v = str(fn(f, b))
            if len(v) <= MAX_CHARS:
                return v
            if "." in v:
                v = v.split(".", 1)[0]
                if len(v) <= MAX_CHARS:
                    return v
            neg = v.startswith("-")
            digits = MAX_CHARS - 1 if neg else MAX_CHARS
            return ("-" if neg else "") + "9" * digits
        return value

    def _val(self, key, x, y, fn, colour=None):
        def paint(d, f, b, v):
            col = colour(f, b, self.t) if colour else self.t.ink
            # A field going red without its characters changing must still
            # repaint - the same rule the small-text painter follows.
            forced = self._colours.get(key) != col
            self._colours[key] = col
            widgets.big(d, x, y + 12, self._drawn.get(key), v, VAL_S, col,
                        self.t.ground, force=forced)
        return (key, x, y + 12, bigfont.width("0000", VAL_S),
                bigfont.char_h(VAL_S), self._fit(fn), paint)

    def _build_regions(self):
        out = list(self.status_regions())
        ys = _rows(len(self.PAIRS))
        for y, pair in zip(ys, self.PAIRS):
            for x, (label, spec) in zip((COL_L, COL_R), pair):
                if spec is None:
                    continue
                key, fn, colour = spec
                out.append(self._val(key, x, y, fn, colour))
        return tuple(out)


class RangeScreen(Panel):
    """How far is left, and what it is costing."""

    title = "RANGE"

    PAIRS = (
        (("RANGE KM", ("remain", lambda f, b: ("%d" % round(f["s_range_km"]))
                       if f.get("s_range_km") else "--", None)),
         ("CHARGE", ("soc", lambda f, b: "%d" % round(
             100 * b.soc_for_voltage(f["input_voltage"])), None))),
        (("TRIP KM", ("trip", lambda f, b: "%.1f" % f["s_trip_km"], None)),
         ("Wh USED", ("wh", lambda f, b: "%d" % round(f["s_wh_spent"]), None))),
        (("Wh / KM", ("whkm", lambda f, b: ("%.1f" % f["s_wh_per_km"])
                      if f["s_wh_per_km"] else "--", None)),
         ("VOLTS", ("volts", lambda f, b: "%.1f" % f["input_voltage"], None))),
        (("MOVING", ("time", lambda f, b: _hhmm(f["s_riding_ms"]), None)),
         ("SAG V", ("sag", lambda f, b: ("%.1f" % f["s_min_voltage"])
                    if f["s_min_voltage"] else "--", None))),
    )


class OverviewScreen(Panel):
    """Everything at once, for standing still and having a look."""

    title = "OVERVIEW"

    PAIRS = (
        (("KM/H", ("speed", lambda f, b: "%.0f" % abs(b.kph_for_erpm(f["rpm"])), None)),
         ("VOLTS", ("volts", lambda f, b: "%.1f" % f["input_voltage"], None))),
        (("MOTOR A", ("motor", lambda f, b: "%.0f" % f["avg_motor_current"], None)),
         ("PACK A", ("pack", lambda f, b: "%.0f" % f["avg_input_current"], None))),
        (("FET C", ("fet", lambda f, b: "%.0f" % f["temp_fet_filtered"], _hot)),
         ("MOTOR C", ("mot", lambda f, b: "%.0f" % f["temp_motor_filtered"], None))),
        (("DUTY %", ("duty", lambda f, b: "%.0f" % (100 * f["duty"]), None)),
         ("TRIP KM", ("trip", lambda f, b: "%.1f" % f["s_trip_km"], None))),
    )


class SessionScreen(Panel):
    """This ride, including every field their firmware left as TODO."""

    title = "THIS RIDE"

    PAIRS = (
        (("DIST KM", ("dist", lambda f, b: "%.1f" % f["s_trip_km"], None)),
         ("MOVING", ("time", lambda f, b: _hhmm(f["s_riding_ms"]), None))),
        (("TOP", ("top", lambda f, b: "%.0f" % f["s_max_kph"], None)),
         ("AVG", ("avg", lambda f, b: "%.0f" % f["s_avg_kph"], None))),
        (("PEAK A", ("peak", lambda f, b: "%.0f" % f["s_max_current"], None)),
         ("FET C", ("maxfet", lambda f, b: "%.0f" % f["s_max_fet"], _hot_session))),
        (("Wh", ("wh", lambda f, b: "%.0f" % f["s_wh_spent"], None)),
         ("REGEN A", ("regen", lambda f, b: "%.0f" % f["s_min_current"], None))),
    )


class LifetimeScreen(Panel):
    """Everything the board has ever done, in the same shape as the ride."""

    title = "LIFETIME"

    PAIRS = (
        (("DIST KM", ("km", lambda f, b: "%.0f" % f["l_trip_km"], None)),
         ("HOURS", ("time", lambda f, b: _hhmm(f["l_riding_ms"]), None))),
        (("TOP", ("top", lambda f, b: "%.0f" % f["l_max_kph"], None)),
         ("PEAK A", ("peak", lambda f, b: "%.0f" % f["l_max_current"], None))),
        (("kWh", ("wh", lambda f, b: "%.1f" % (f["l_wh_spent"] / 1000.0), None)),
         ("FET C", ("fet", lambda f, b: "%.0f" % f["l_max_fet"], None))),
        (("SAG V", ("sag", lambda f, b: ("%.1f" % f["l_min_voltage"])
                    if f["l_min_voltage"] else "--", None)),
         (None, None)),
    )


ALL = (("riding", None), ("range", RangeScreen), ("overview", OverviewScreen),
       ("session", SessionScreen), ("lifetime", LifetimeScreen))
