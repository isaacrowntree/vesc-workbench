"""The main loop, with nothing device-specific in it.

Kept separate from `start.py` so it can be tested with fakes: the loop is where
the awkward decisions live - what to draw when telemetry stops, when to stop
polling and finish an animation, when to give up.
"""

# The reference firmware's UPDATE_DELAY: "how often data is read from VESC".
UPDATE_MS = 50

# After this long with no valid reply, say so rather than showing stale
# numbers as though they were live.
STALE_MS = 1500


class Runner:
    def __init__(self, app, display, uart, board, buttons, ticks_ms, ticks_diff,
                 sleep_ms, vesc, esc_count=1, session=None, lifetime=None,
                 resistance=None, can_ids=()):
        self.app = app
        self.d = display
        self.uart = uart
        self.board = board
        self.buttons = buttons
        self._now = ticks_ms
        self._diff = ticks_diff
        self._sleep = sleep_ms
        self.vesc = vesc
        self.esc_count = esc_count
        #: other controllers on the CAN bus, asked through the local one. A
        #: Unity is two of them in one case and the reply carries only the
        #: controller that answered.
        self.can_ids = tuple(can_ids)
        self.can_ok = 0
        self.can_bad = 0
        self.frame = board.frame()
        self.last_good = None
        self.stale = False
        self.reads = 0
        self.bad = 0
        self.last_read_ok = False
        self.session = session
        self.lifetime = lifetime
        self.resistance = resistance
        self._last_tick = None

    def poll_telemetry(self):
        """One request/reply per controller. Returns True if the frame moved.

        The local ESC is asked over the wire and the rest through it, over
        CAN. If a CAN read fails the frame still updates from the controller
        that did answer, scaled by `esc_count` - half the board measured is
        better than none, and a dropped packet should not make the pack draw
        appear to halve.
        """
        try:
            self.vesc.request(self.uart)
            packet = self.vesc.read(self.uart, UPDATE_MS, self._now, self._diff)
            values = self.vesc.parse(packet)
        except Exception:                       # noqa: BLE001
            values = None
        self.reads += 1
        if values is None:
            self.bad += 1
            return False

        for can_id in self.can_ids:
            other = None
            try:
                self.uart.write(self.vesc.can_request(can_id))
                pkt = self.vesc.read(self.uart, UPDATE_MS, self._now,
                                     self._diff)
                other = self.vesc.parse(pkt)
            except Exception:                   # noqa: BLE001
                other = None
            if other is None:
                self.can_bad += 1
            else:
                self.can_ok += 1
                values = self.vesc.combine(values, other)
        if self.esc_count != 1 and values.get("esc_count", 1) == 1:
            # Nothing came back from the other controller, so fall back to the
            # reference firmware's assumption of two equal halves rather than
            # letting the board appear to draw half of what it does.
            values["avg_input_current"] *= self.esc_count
        self.frame.update(values)
        self.last_good = self._now()
        return True

    def is_stale(self):
        if self.last_good is None:
            return self.reads > 0
        return self._diff(self._now(), self.last_good) > STALE_MS

    def step(self):
        """One pass: buttons, telemetry, then draw until settled.

        Drawing is drained rather than done once, because an animation owes
        more frames than telemetry provides and the two run at different
        rates.
        """
        for event in self.buttons.poll():
            self.app.press(event)

        ok = self.poll_telemetry()
        self.stale = self.is_stale()
        # Their screens get told every pass whether the read worked. Ours now
        # do too, through the frame, so a screen can show it without the
        # runner knowing which screens care.
        self.frame["link_ok"] = not self.stale
        self.last_read_ok = ok

        if self.resistance is not None and ok:
            self.resistance.update(self.frame["input_voltage"],
                                   self.frame["avg_input_current"])
            r = self.resistance.value
            self.frame["r_internal"] = r
            # Charge shown from the open-circuit voltage, so the gauge stops
            # dropping every time the rider accelerates.
            self.frame["soc"] = (
                self.board.soc_loaded(self.frame["input_voltage"],
                                      self.frame["avg_input_current"], r)
                if r else
                self.board.soc_for_voltage(self.frame["input_voltage"]))

        now = self._now()
        dt = 0 if self._last_tick is None else self._diff(now, self._last_tick)
        self._last_tick = now
        if self.session is not None and dt > 0:
            # A ride with no history of its own borrows the board's.
            if self.lifetime is not None:
                self.session._lifetime_rate = self.lifetime.wh_per_km
            self.session.update(self.frame, dt)
            _publish(self.frame, self.session, "s_", self.board)
        if self.lifetime is not None:
            _publish(self.frame, self.lifetime, "l_", self.board)

        drawn = 0
        while self.app.tick(self.d, self.frame) and drawn < 20:
            drawn += 1
        return drawn + 1

    def run(self, forever=True, limit=0):
        n = 0
        while True:
            self.step()
            n += 1
            if not forever and n >= limit:
                return n
            self._sleep(UPDATE_MS)


def _publish(frame, session, prefix, board):
    """Fold a session's numbers into the frame under a prefix.

    Screens stay pure functions of one frame; they never hold a reference to
    an accumulator, so a test can render any session state directly.
    """
    frame[prefix + "trip_km"] = session.trip_km
    frame[prefix + "riding_ms"] = session.riding_ms
    frame[prefix + "elapsed_ms"] = session.elapsed_ms
    frame[prefix + "max_kph"] = session.max_kph
    frame[prefix + "avg_kph"] = session.avg_kph
    frame[prefix + "min_voltage"] = session.min_voltage
    frame[prefix + "max_fet"] = session.max_fet
    frame[prefix + "max_motor_temp"] = session.max_motor_temp
    frame[prefix + "max_current"] = session.max_current
    frame[prefix + "min_current"] = session.min_current
    frame[prefix + "max_batt_current"] = session.max_batt_current
    frame[prefix + "wh_spent"] = session.wh_spent
    frame[prefix + "wh_per_km"] = session.wh_per_km
    # The rate this ride has not earned yet: what the board has averaged over
    # its life, and failing that what it was told to assume.
    fallback = getattr(board, "wh_per_km", 0.0)
    lifetime_rate = getattr(session, "_lifetime_rate", 0.0)
    if lifetime_rate > 0.0:
        fallback = lifetime_rate
    frame[prefix + "range_km"] = session.range_km(frame, fallback)
    frame[prefix + "range_measured"] = session.measured()
