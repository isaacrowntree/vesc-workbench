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
                 sleep_ms, vesc, esc_count=1, session=None, lifetime=None):
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
        self.frame = board.frame()
        self.last_good = None
        self.stale = False
        self.reads = 0
        self.bad = 0
        self.last_read_ok = False
        self.session = session
        self.lifetime = lifetime
        self._last_tick = None

    def poll_telemetry(self):
        """One request/reply. Returns True if the frame was updated."""
        try:
            self.vesc.request(self.uart)
            packet = self.vesc.read(self.uart, UPDATE_MS, self._now, self._diff)
            values = self.vesc.parse(packet, self.esc_count)
        except Exception:                       # noqa: BLE001
            values = None
        self.reads += 1
        if values is None:
            self.bad += 1
            return False
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

        now = self._now()
        dt = 0 if self._last_tick is None else self._diff(now, self._last_tick)
        self._last_tick = now
        if self.session is not None and dt > 0:
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
    frame[prefix + "range_km"] = session.range_km(frame)
