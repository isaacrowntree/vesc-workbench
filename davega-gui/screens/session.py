"""Trip and lifetime accumulation.

Modelled on `t_davega_session_data` in the DAVEga firmware, which tracks
elapsed time, riding time, top speed, minimum voltage and trip distance - and
carries a TODO list of five more fields the author never got to:

    // TODO:
    // max_motor_temp
    // max_fet_temp
    // max_current
    // min_current
    // wh_spent
    // wh_per_km (derived)
    // range_km (derived)

All of them are here. They are also the fields you actually want after a ride
that went wrong: what got hot, what the pack sagged to, how hard you pulled.

Pure arithmetic over frames, so a whole ride is replayed in a test.
"""

STATIONARY_KPH = 1.0          # below this we are stopped, not riding
MIN_EVIDENCE_KM = 0.5         # before range will give an estimate


class Session:
    """One ride. `lifetime=True` for the counters that never reset."""

    def __init__(self, board, lifetime=False):
        self.board = board
        self.lifetime = lifetime
        self.reset()

    def reset(self):
        self.elapsed_ms = 0
        self.riding_ms = 0
        self.trip_km = 0.0
        self.max_kph = 0.0
        self.min_voltage = 0.0        # 0 means "not seen under load yet"
        # their TODO list
        self.max_fet = 0.0
        self.max_motor_temp = 0.0
        self.max_current = 0.0
        self.min_current = 0.0
        self.max_batt_current = 0.0
        self.min_batt_current = 0.0
        self.wh_spent = 0.0
        self._tacho0 = None
        self._wh0 = None

    # -- accumulate --------------------------------------------------------

    def update(self, f, dt_ms):
        """Fold one frame in. `dt_ms` is time since the previous frame."""
        if not f.get("link_ok", True):
            return                     # do not accumulate from a dead link

        self.elapsed_ms += dt_ms
        kph = abs(self.board.kph_for_erpm(f["rpm"]))
        if kph >= STATIONARY_KPH:
            self.riding_ms += dt_ms
        if kph > self.max_kph:
            self.max_kph = kph

        # Distance and energy are counters on the ESC, so track the delta from
        # where they were when this session started. That survives the ESC
        # resetting them mid-ride, which a running total would not.
        tacho = f["tachometer_abs_value"]
        if self._tacho0 is None or tacho < self._tacho0:
            self._tacho0 = tacho
        self.trip_km = self.board.km_for_tacho(tacho - self._tacho0)

        wh = f.get("watt_hours", 0.0)
        if self._wh0 is None or wh < self._wh0:
            self._wh0 = wh
        self.wh_spent = wh - self._wh0

        fet, mot = f["temp_fet_filtered"], f["temp_motor_filtered"]
        if fet > self.max_fet:
            self.max_fet = fet
        if mot > self.max_motor_temp:
            self.max_motor_temp = mot

        im, ib = f["avg_motor_current"], f["avg_input_current"]
        if im > self.max_current:
            self.max_current = im
        if im < self.min_current:
            self.min_current = im
        if ib > self.max_batt_current:
            self.max_batt_current = ib
        if ib < self.min_batt_current:
            self.min_batt_current = ib

        # Voltage under load only: a resting pack reads high and would hide
        # the sag that actually matters.
        v = f["input_voltage"]
        if ib > 1.0 and (self.min_voltage == 0.0 or v < self.min_voltage):
            self.min_voltage = v

    # -- derived (their TODO) ---------------------------------------------

    @property
    def avg_kph(self):
        if self.riding_ms <= 0:
            return 0.0
        return self.trip_km / (self.riding_ms / 3600000.0)

    @property
    def wh_per_km(self):
        if self.trip_km < 0.05:
            return 0.0
        return self.wh_spent / self.trip_km

    def range_km(self, f):
        """Remaining range at this ride's efficiency.

        Returns 0.0 when there is not enough evidence yet, rather than a
        confident number derived from thirty metres of riding.
        """
        rate = self.wh_per_km
        # Half a kilometre before it will answer. Two hundred metres of
        # riding produces a confident-looking number built on almost nothing,
        # and a range estimate people trust is worse than one they wait for.
        if rate <= 0.0 or self.trip_km < MIN_EVIDENCE_KM:
            return 0.0
        # Not remaining-energy-over-rate: the kilometres left cost more than
        # the ones behind you, because power falls with voltage and sag
        # deepens as the pack empties.
        return self.board.range_km(rate, f["input_voltage"])

    # -- persistence -------------------------------------------------------

    KEYS = ("elapsed_ms", "riding_ms", "trip_km", "max_kph", "min_voltage",
            "max_fet", "max_motor_temp", "max_current", "min_current",
            "max_batt_current", "min_batt_current", "wh_spent")

    def to_dict(self):
        return dict((k, getattr(self, k)) for k in self.KEYS)

    def load(self, d):
        for k in self.KEYS:
            if k in d:
                setattr(self, k, d[k])
        return self

    def merge(self, other):
        """Fold a finished session into a lifetime total."""
        self.elapsed_ms += other.elapsed_ms
        self.riding_ms += other.riding_ms
        self.trip_km += other.trip_km
        self.wh_spent += other.wh_spent
        for k in ("max_kph", "max_fet", "max_motor_temp", "max_current",
                  "max_batt_current"):
            if getattr(other, k) > getattr(self, k):
                setattr(self, k, getattr(other, k))
        for k in ("min_current", "min_batt_current"):
            if getattr(other, k) < getattr(self, k):
                setattr(self, k, getattr(other, k))
        if other.min_voltage > 0 and (self.min_voltage == 0
                                      or other.min_voltage < self.min_voltage):
            self.min_voltage = other.min_voltage
        return self


class Resistance:
    """Online estimate of pack internal resistance, R0 in the Rint model.

    From pairs of (voltage, current) samples: the slope of V against I is
    -R0. Rather than a full regression - which is more arithmetic than an
    ESP32 wants at 5 Hz - it tracks the lightest and heaviest loaded samples
    seen recently and takes the slope between them, which is where the
    signal is anyway.

    Reports nothing until it has seen a real spread of current, because a
    slope fitted to noise is worse than no slope at all.
    """

    MIN_SPREAD_A = 8.0        # amps between the two samples before we believe it
    BLEND = 0.2               # how fast the estimate follows new evidence

    def __init__(self, cells=12):
        self.cells = cells
        self.value = 0.0
        self._lo = None       # (current, voltage) least loaded
        self._hi = None       # most loaded
        self.samples = 0

    def update(self, volts, current):
        if volts <= 0:
            return self.value
        if self._lo is None or current < self._lo[0]:
            self._lo = (current, volts)
        if self._hi is None or current > self._hi[0]:
            self._hi = (current, volts)
        if self._lo and self._hi:
            di = self._hi[0] - self._lo[0]
            if di >= self.MIN_SPREAD_A:
                dv = self._lo[1] - self._hi[1]
                r = dv / di
                # A pack with negative or absurd resistance is a measurement
                # artefact, not a discovery.
                if 0.0 < r < 1.0:
                    self.value = (r if self.value == 0.0
                                  else self.value * (1 - self.BLEND) + r * self.BLEND)
                    self.samples += 1
        return self.value

    @property
    def milliohms_per_cell(self):
        if not self.value:
            return 0.0
        return self.value * 1000.0 / self.cells

    def reset(self):
        self.value = 0.0
        self._lo = self._hi = None
        self.samples = 0
