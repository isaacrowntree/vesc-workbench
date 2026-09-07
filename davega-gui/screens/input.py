"""Buttons: debounce, repeat and hold.

The three buttons are active low - `sn8ke` checks `not BUTTON_DOWN.value()` -
and a bare pin read gives you contact bounce, no hold detection and no repeat.
This turns pin state into the events the state machine understands.

It takes a `read()` returning (up, down, enter) and a millisecond clock, so a
test drives a whole session deterministically and nothing here needs a board.
"""

UP, DOWN, ENTER, HOLD = "up", "down", "enter", "hold"

# Constants taken from the DAVEga firmware rather than invented:
#   UPDATE_DELAY       50 ms   the main loop period, and its de-facto debounce
#   COUNTER_RESET_TIME 3000 ms how long a hold has to be to count as one
# Three seconds is long for a menu exit, but it is the gesture riders already
# have for "reset the session", and inventing a shorter one guarantees they
# eventually trigger the wrong thing.
DEBOUNCE_MS = 50
HOLD_MS = 3000
REPEAT_MS = 500          # up/down auto-repeat after this
REPEAT_EVERY_MS = 150


class Buttons:
    def __init__(self, read, ticks_ms, hold_ms=HOLD_MS, repeat=True):
        self._read = read
        self._now = ticks_ms
        self.hold_ms = hold_ms
        self.repeat = repeat
        self._state = (False, False, False)
        self._since = [0, 0, 0]
        self._fired = [False, False, False]
        self._last_repeat = [0, 0, 0]

    def poll(self):
        """Return a list of events since the last call. Usually empty."""
        now = self._now()
        raw = self._read()
        events = []
        for i, name in enumerate((UP, DOWN, ENTER)):
            down = bool(raw[i])
            was = self._state[i]

            if down != was:
                # Ignore anything faster than the contacts can settle.
                if now - self._since[i] < DEBOUNCE_MS:
                    continue
                self._since[i] = now
                if down:
                    self._fired[i] = False
                    self._last_repeat[i] = now
                    # up/down act on press: a dash should respond immediately
                    if name in (UP, DOWN):
                        events.append(name)
                        self._fired[i] = True
                else:
                    # enter acts on release, so a hold can be told apart
                    if name == ENTER and not self._fired[i]:
                        events.append(ENTER)
                self._state = _replace(self._state, i, down)
                continue

            if not down:
                continue

            held = now - self._since[i]
            if name == ENTER and not self._fired[i] and held >= self.hold_ms:
                events.append(HOLD)
                self._fired[i] = True
            elif (self.repeat and name in (UP, DOWN) and held >= REPEAT_MS
                    and now - self._last_repeat[i] >= REPEAT_EVERY_MS):
                events.append(name)
                self._last_repeat[i] = now
        return events


def _replace(tup, i, v):
    return tuple(v if j == i else x for j, x in enumerate(tup))


def attach():
    """Wrap the real buttons. Active low, so a press reads 0.

    The vendor's names run the other way round from the panel: the button
    `frozen.buttons` calls BUTTON_UP is the one on the right, so taking the
    names at face value made the right-hand button page backwards. Swapped
    here, at the boundary, so that everything above deals in what the rider
    pressed rather than in what the pin was called.
    """
    from frozen.buttons import BUTTON_UP, BUTTON_DOWN, BUTTON_ENTER
    import utime

    def read():
        return (not BUTTON_DOWN.value(),
                not BUTTON_UP.value(),
                not BUTTON_ENTER.value())

    return Buttons(read, utime.ticks_ms)
