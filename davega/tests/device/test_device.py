"""The dashboard, end to end, in the interpreter that will run it.

Everything else in `davega/tests/` runs under CPython, which is fast and
convenient and does not tell you whether the code will start on the board.
This does. It runs the real modules in MicroPython 1.14 - the version the
DAVEGA reports - with the panel, the buttons, the UART and the flash faked,
and drives a whole ride through it: boot, sweep, telemetry, every screen,
every button, the menu, a fault and a recovery.

What it is for, in order of how often each has actually bitten:

  1. Importing. CPython accepts syntax and library calls MicroPython does not,
     and the failure lands as a dead screen on a deck rather than a red test.
  2. Memory. 98 kB of heap, and a dashboard that allocates too eagerly boots
     nine times and fails the tenth.
  3. framebuf. `bands` composes curves into a real framebuffer on the device
     and into a Python stand-in everywhere else. This is where the two are
     checked against each other.
  4. The loop. Buttons, staleness, a controller that stops answering.

Run: davega/tests/device/run.sh
"""
import sys
import gc

sys.path.insert(0, "/work/davega")
sys.path.insert(0, "/work/davega/tests/device")
sys.path.insert(0, "/work/davega/tests/device/stubs")

import fakes                                             # noqa: E402
import frames                                            # noqa: E402

FAILS = []
BASE = gc.mem_free()


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        FAILS.append(name)
        print("  FAIL  %s %s" % (name, detail))


def mem(label):
    gc.collect()
    used = BASE - gc.mem_free()
    print("        %-34s %7d bytes in use" % (label, used))
    return used


# ---------------------------------------------------------------- imports

print("== every module imports under MicroPython")
# One at a time, so a failure names the module rather than the package. This
# is the check that would have caught a CPython-only construct before it
# reached the deck.
MODULES = ("palette", "themes", "anim", "bigfont", "widgets", "bands", "base",
           "board", "vesc", "session", "device", "input", "app", "riding",
           "panels", "runner", "boot")
for name in MODULES:
    try:
        __import__("gui." + name)
        gc.collect()
    except Exception as e:                               # noqa: BLE001
        check("import gui.%s" % name, False, repr(e))
        break
else:
    check("all %d modules import" % len(MODULES), True)

after_imports = mem("everything imported")


# ---------------------------------------------------------------- framebuf

print()
print("== bands composes curves through the real framebuf")
# The harness has a pure-Python stand-in for framebuf. On the device the C one
# is used. If they rasterise differently, every golden image is a promise the
# panel does not keep - so the same drawing is done both ways and compared.
from gui import bands                                    # noqa: E402

W, H = 120, 40


def _draw(c):
    c.fill(0x0000)
    c.disc(60, 20, 16, 0xF800)
    c.ring(60, 20, 18, 0x07FF, 2)
    sin, cos = bands.sincos(-35.0)
    c.spoke(60, 20, 4, 17, sin, cos, 0xFFE0, 2)
    c.wedge([4, 30, 24, 2], [6, 10, 30, 26], 0x07E0)


def _render(frame_factory):
    buf = bytearray(W * H * 2)
    fb = frame_factory(buf, W, H)
    _draw(bands.Canvas(fb, 0, 0, W, H))
    return bytes(buf)


import framebuf                                          # noqa: E402

# Through `bands._frame`, not through framebuf directly - the wrapper it
# returns is part of what is being checked. The C rasteriser stores RGB565
# with a native 16-bit write, so on this little-endian machine the low byte
# lands first, while the panel wants the high byte first and `writeblock`
# streams the buffer untouched. Both paths must end up in panel order.
native = _render(bands._frame)
python = _render(bands._PyFrame)
if native == python:
    check("the Python stand-in matches the C framebuf", True)
else:
    diff = sum(1 for i in range(0, len(native), 2)
               if native[i:i + 2] != python[i:i + 2])
    check("the Python stand-in matches the C framebuf", False,
          "%d of %d pixels differ" % (diff, W * H))

check("bands used the C rasteriser, not the stand-in",
      type(bands._frame(bytearray(32), 4, 4)) is not bands._PyFrame)
check("and knows this machine stores RGB565 low byte first", bands._SWAP)

# The bytes that leave for the panel, high byte first.
probe = bytearray(2)
bands._frame(probe, 1, 1).pixel(0, 0, 0xF800)
check("a red pixel reaches the panel as F8,00",
      probe[0] == 0xF8 and probe[1] == 0x00,
      "got %02X,%02X" % (probe[0], probe[1]))


# ---------------------------------------------------------------- the ride

print()
print("== a whole ride, through the real loop")
env = fakes.wire()
d, buttons, uart = env["display"], env["buttons"], env["uart"]

import utime                                             # noqa: E402
from gui.board import Board                              # noqa: E402
from gui.runner import Runner                            # noqa: E402
from gui.app import App, Menu, MenuItem                  # noqa: E402
from gui.riding import Riding                            # noqa: E402
from gui.panels import (RangeScreen, OverviewScreen,     # noqa: E402
                        SessionScreen, LifetimeScreen)
from gui.session import Session, Resistance              # noqa: E402
from gui.themes import THEMES, DEFAULT                   # noqa: E402
import gui.device as device                              # noqa: E402
import gui.input as user_input                           # noqa: E402
import gui.vesc as vesc                                  # noqa: E402

board = Board(cells=12, parallel=4, pole_pairs=7, gear_ratio=84 / 20.0,
              wheel_m=0.2)
screens = (("riding", Riding), ("range", RangeScreen),
           ("overview", OverviewScreen), ("session", SessionScreen),
           ("lifetime", LifetimeScreen))
chosen = []
saved = {}
writes = [0]


def _remember(a):
    """Stands in for boot.py's config write, counting how often it happens."""
    writes[0] += 1
    saved["theme"] = a.theme
    saved["theme_light"] = a.light


menu = Menu([
    MenuItem("Theme", [DEFAULT] + sorted(k for k in THEMES if k != DEFAULT),
             on_select=lambda app, v: (chosen.append(v), app.set_theme(v))),
    MenuItem("Display", ["night", "day"],
             on_select=lambda app, v: app.set_light(v == "day")),
], on_close=_remember)
app = App(screens, board, DEFAULT, menu, sweep=True)
runner = Runner(app, device.attach(), uart, board,
                user_input.attach(), utime.ticks_ms, utime.ticks_diff,
                utime.sleep_ms, vesc, esc_count=2,
                session=Session(board), lifetime=Session(board, lifetime=True),
                resistance=Resistance(), can_ids=[124])


def serve(primary, second):
    """Answer the next request pair with these two replies."""
    uart.script = [
        (lambda r: r == vesc.GET_VALUES, primary),
        (lambda r: len(r) > 3 and r[2] == vesc.COMM_FORWARD_CAN, second),
    ]


def spin(n=6):
    for _ in range(n):
        runner.step()


# The recorded frames first: if the parser has drifted from the hardware,
# everything after this is measuring the wrong thing.
serve(frames.REAL_123, frames.REAL_124)
spin(4)
f = runner.frame
check("recorded frames parse (%.1f V, fet %.1f C)"
      % (f["input_voltage"], f["temp_fet_filtered"]),
      44.0 < f["input_voltage"] < 47.0 and 20.0 < f["temp_fet_filtered"] < 40.0,
      repr((f["input_voltage"], f["temp_fet_filtered"])))
check("the hotter of the two controllers is the one reported",
      abs(f["temp_fet_filtered"] - 28.1) < 0.3, repr(f["temp_fet_filtered"]))
check("both controllers were asked", runner.can_ok > 0 and runner.bad == 0,
      "can_ok=%d bad=%d" % (runner.can_ok, runner.bad))

worst_settle = 0
worst_idle = 0
for label, (primary, second) in frames.ride():
    serve(primary, second)
    d.reset()
    spin(10)                            # move to this state and let it land
    settle_calls = len(d.calls)
    worst_settle = max(worst_settle, settle_calls)
    d.reset()
    runner.step()                       # one more, with nothing changing
    idle = len(d.calls)
    worst_idle = max(worst_idle, idle)
    check("%-15s %3d calls to settle, %2d idle" % (label, settle_calls, idle),
          settle_calls > 0 or label == "standstill")

check("a settled screen costs almost nothing (worst %d calls)" % worst_idle,
      worst_idle <= 12, "%d calls with nothing changing" % worst_idle)
after_ride = mem("after the ride")


# ---------------------------------------------------------------- buttons

print()
print("== the buttons do what the panel says they do")


def tap(pin, passes=3):
    """A press, long enough to be a press.

    The debounce is 50 ms and the hold threshold is three seconds, both taken
    from the reference firmware. A test loop runs far faster than a thumb, so
    without real time passing every press after the first is discarded as
    contact bounce - which is the correct behaviour, and makes the button
    tests meaningless unless the clock is allowed to move.
    """
    utime.sleep_ms(60)
    pin.press()
    for _ in range(passes):
        runner.step()
    utime.sleep_ms(60)
    pin.release()
    for _ in range(passes):
        runner.step()


# The vendor's pin names run the other way round from the panel: the pin
# `frozen.buttons` calls BUTTON_UP is the button on the right. `gui.input`
# swaps them at the boundary, and pressing them by their physical position
# here is what proves it.
RIGHT, LEFT = buttons.BUTTON_UP, buttons.BUTTON_DOWN


start = app.key
tap(RIGHT)
second = app.key
check("the right button pages forward (%s -> %s)" % (start, second),
      second != start)
tap(LEFT)
check("the left button pages back to %s" % start, app.key == start,
      "landed on %s" % app.key)

# Every screen, drawn for real, in sequence, and back to where we started.
seen = [app.key]
drew = True
for _ in range(len(screens)):
    d.reset()
    tap(RIGHT)
    spin(4)
    if not d.calls:
        drew = False
    if app.key not in seen:
        seen.append(app.key)
check("all %d screens render (%s)" % (len(screens), ",".join(seen)),
      len(seen) == len(screens) and drew,
      "saw %d, every one drew: %s" % (len(seen), drew))

tap(buttons.BUTTON_ENTER)
check("enter opens the menu", app.in_menu, "not in the menu")

# The cursor starts on Theme, and enter advances that item's value. Moving
# first would land on Display, which is a different setting entirely.
tap(buttons.BUTTON_ENTER)
check("a theme can be chosen from the board", bool(chosen),
      "nothing selected")
if chosen:
    check("and it is not the one we started on", chosen[-1] != DEFAULT,
          "chose %s" % chosen[-1])
    # The theme change repaints the menu, because every colour on it just
    # changed. It does not keep repainting: a settled menu draws nothing, and
    # the screens behind it are rebuilt when the rider leaves.
    d.reset()
    spin(6)
    check("and then the menu settles again", len(d.calls) == 0,
          "%d calls after the change had landed" % len(d.calls))
    d.reset()
    app.press("hold")
    spin(4)
    check("leaving the menu repaints the screen in the new theme",
          len(d.calls) > 20, "%d calls" % len(d.calls))
    tap(buttons.BUTTON_ENTER)              # back in, for the checks below


# ---------------------------------------------------------------- the link

print()
print("== the config screen")
# It used to erase the whole panel on every telemetry pass, which at 5 Hz is a
# flicker you cannot hold still enough to use.
tap(buttons.BUTTON_ENTER)                 # back in
check("the menu is open", app.in_menu, "not in the menu")
d.reset()
for _ in range(10):
    runner.step()
check("an untouched menu draws nothing (%d calls)" % len(d.calls),
      len(d.calls) == 0, "%d calls over 10 passes" % len(d.calls))

d.reset()
tap(RIGHT)
moved = len(d.calls)
erases = sum(1 for c in d.calls if c[0] == "erase")
check("moving the cursor repaints two rows, not the panel (%d calls)" % moved,
      0 < moved < 20 and erases == 0, "%d calls, %d erases" % (moved, erases))

before = len(chosen)
d.reset()
tap(buttons.BUTTON_ENTER)
check("a value changes on the row under the cursor",
      len(chosen) == before or app.in_menu)

# Leaving the menu is a three second hold, and that is when settings persist.
saved.clear()
writes[0] = 0
before_cycles = len(chosen)
tap(LEFT)                                 # back onto the Theme row
for _ in range(4):                        # cycle the theme a few times
    tap(buttons.BUTTON_ENTER)
check("cycling the theme applies live (%d changes)"
      % (len(chosen) - before_cycles), len(chosen) > before_cycles)
check("and writes nothing while you cycle", writes[0] == 0,
      "%d writes before leaving" % writes[0])
app.press("hold")
runner.step()
check("holding leaves the menu", not app.in_menu, "still in the menu")
check("and that is when the settings are written (%s)" % sorted(saved),
      "theme" in saved and "theme_light" in saved, repr(saved))
check("four theme changes cost one write, not four", writes[0] == 1,
      "%d writes" % writes[0])

print()
print("== what happens when the ESC stops answering")
uart.script = []                       # nothing replies from here on
before = runner.bad
for _ in range(40):
    runner.step()
    utime.sleep_ms(50)                 # STALE_MS is 1500: let it actually pass
check("bad reads are counted, not raised", runner.bad > before,
      "bad went %d -> %d" % (before, runner.bad))
check("the link is reported stale", runner.stale)
check("and the dashboard is still drawing", True)

serve(frames.REAL_123, frames.REAL_124)
spin(6)
check("it recovers when the ESC comes back", not runner.stale)


# ---------------------------------------------------------------- memory

print()
print("== memory")
# Absolute byte counts do not carry from here to the board: this is the unix
# port on a 64-bit host, where every reference is twice the width and the
# allocator's blocks are a different size. Reported, not asserted.
peak = mem("dashboard, one layout, mid-ride (64-bit host)")

# What does carry is whether a frame allocates. The board has 98 kB and runs
# for hours; a dashboard that leaks a little per frame boots fine, looks fine,
# and dies somewhere on the way home. So: settle, collect, then run a few
# hundred frames and see whether the floor moved.
serve(*frames.ride()[2][1])            # cruising, and nothing changing
spin(12)
d.reset()

# The first stretch is discounted: the fakes' own bounded logs are still
# filling, and that is the instrument warming up rather than the dashboard
# growing. The window that counts is the one after they are full.
def window(n):
    gc.collect()
    before = gc.mem_free()
    for _ in range(n):
        runner.step()
    gc.collect()
    return before - gc.mem_free()


# Two windows, because one cannot tell a leak from a warm-up. Caches fill,
# bounded logs reach their cap, a tween settles - all of that shows up as
# growth in the first window and none of it repeats. A real leak repeats.
first = window(400)
second = window(400)
print("        %-34s %+7d then %+7d bytes"
      % ("two 400-frame windows", -first, -second))
check("a settled frame allocates nothing lasting", second <= 0,
      "still losing %d bytes per 400 frames after warm-up - on 98 kB that is "
      "about %d frames to a MemoryError"
      % (second, (98 * 1024) // max(1, second) * 400))


# ------------------------------------------------------- every layout, last
# Deliberately after the memory check: this imports all ten at once, which the
# board never does and which would make the reading above meaningless.
print()
print("== every layout imports")
LAYOUTS = ("flagship", "dial", "shards", "hairline", "bare", "flow", "eco",
           "minimal", "rail", "rings")
bad = None
for name in LAYOUTS:
    try:
        __import__("gui.layouts." + name)
        gc.collect()
    except Exception as e:                               # noqa: BLE001
        bad = "%s: %r" % (name, e)
        break
check("all %d layouts import" % len(LAYOUTS), bad is None, bad or "")
mem("with all ten layouts resident")

print()
if FAILS:
    print("%d DEVICE TESTS FAILED" % len(FAILS))
    sys.exit(1)
print("all device tests passed")
