"""Run start.py's wiring with fakes for everything the device provides.

Catches the class of bug that only shows up at boot: a name that does not
exist, an argument in the wrong place, a module that is not where start.py
thinks it is. The stock app would survive it - our try/except sees to that -
but the rider would get no dashboard and no explanation.
"""
import sys, os, types, tempfile

LIFE = os.path.join(tempfile.gettempdir(), "gui-lifetime-smoke.json")
if os.path.exists(LIFE):
    os.remove(LIFE)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                     # davega/
sys.path.insert(0, ROOT)

# --- fake the device modules -------------------------------------------
frozen = types.ModuleType("frozen"); frozen.__path__ = []
sys.modules["frozen"] = frozen

class Pin:
    def __init__(self, v=1): self._v = v
    def value(self): return self._v

buttons = types.ModuleType("frozen.buttons")
buttons.BUTTON_UP = Pin(1)      # not held -> our dash runs
buttons.BUTTON_DOWN = Pin(1)
buttons.BUTTON_ENTER = Pin(1)
sys.modules["frozen.buttons"] = buttons

sys.path.insert(0, ROOT)
from harness.display import Display
disp = types.ModuleType("frozen.display"); disp.DISPLAY = Display(strict=False)
sys.modules["frozen.display"] = disp
du = types.ModuleType("frozen.display_util")
du.draw_number = None; du.number_dimensions = None; du.FONT_3X5 = b""
sys.modules["frozen.display_util"] = du

class FakeUART:
    def __init__(self, *a, **k): self.buf = b""
    def write(self, d): self.buf = b""
    def read(self, n): return None
machine = types.ModuleType("machine"); machine.UART = FakeUART
sys.modules["machine"] = machine

utime = types.ModuleType("utime")
_t = [0]
def ticks_ms():
    _t[0] += 1; return _t[0]
utime.ticks_ms = ticks_ms
utime.ticks_diff = lambda a, b: a - b
utime.sleep_ms = lambda ms: None
sys.modules["utime"] = utime
sys.modules["ujson"] = __import__("json")

# `gui` is a real package now - the same one that ships to /gui on the device -
# so it imports directly rather than being assembled from a stub.
import gui

# --- run the boot path, bounded ----------------------------------------
# start.py is the escape hatch and gui/boot.py is the dashboard. Both are
# exercised: boot.py for the wiring, start.py for the hatch and the failure
# report, because between them they are what happens when the board is
# switched on.
ERR = os.path.join(tempfile.gettempdir(), "gui-error-smoke.txt")
if os.path.exists(ERR):
    os.remove(ERR)


def _load(path, **subs):
    src = open(os.path.join(ROOT, path)).read()
    for a, b in subs.items():
        src = src.replace(a, b)
    return src


boot_src = _load(
    "gui/boot.py",
    **{"while True:": "for _loop in range(40):",
       'LIFETIME_PATH = "/data/gui-lifetime.json"': 'LIFETIME_PATH = %r' % LIFE,
       # Force the periodic save to fire inside a short run, so the path that
       # keeps lifetime totals across a power cycle is actually exercised.
       "SAVE_EVERY_MS = 5 * 60 * 1000": "SAVE_EVERY_MS = 5",
       'ERROR_PATH = "/data/gui-error.txt"': 'ERROR_PATH = %r' % ERR})
ns = {"__name__": "gui.boot"}
exec(compile(boot_src, "boot.py", "exec"), ns)
ns["main"]()

d = disp.DISPLAY
fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


print("== the boot path wires up and draws")
check("boot.py drew a dashboard (%d calls)" % len(d.calls), len(d.calls) > 50)
check("lifetime totals were persisted", os.path.exists(LIFE))
if os.path.exists(LIFE):
    import json
    saved = json.load(open(LIFE))
    check("and the file holds the session keys",
          "trip_km" in saved and "max_fet" in saved,
          "got %s" % sorted(saved)[:4])

# --- start.py: the escape hatch and the failure report ------------------
# It is deliberately the one file that is not bytecode, because it has to work
# when /gui does not. So it is tested against a *stubbed* gui.boot: what
# matters here is whether it calls the dashboard, not what the dashboard does.
called = []
fake_boot = types.ModuleType("gui.boot")
fake_boot.main = lambda: called.append(True)
sys.modules["gui.boot"] = fake_boot
gui.boot = fake_boot

start_src = _load("start.py",
                  **{'ERROR_PATH = "/data/gui-error.txt"': 'ERROR_PATH = %r' % ERR})

buttons.BUTTON_UP = Pin(0)      # held
d.reset_state()
exec(compile(start_src, "start.py", "exec"), {"__name__": "start"})
check("holding UP stands the dash down for the stock app",
      not called and len(d.calls) == 0,
      "called=%s drew %d calls" % (called, len(d.calls)))

buttons.BUTTON_UP = Pin(1)      # not held
exec(compile(start_src, "start.py", "exec"), {"__name__": "start"})
check("otherwise it runs the dashboard", bool(called))

# A boot that fails must leave an explanation behind, or diagnosing it costs a
# WebREPL session and a round trip.
def _boom():
    raise ImportError("no module named 'gui.nonexistent'")


fake_boot.main = _boom
exec(compile(start_src, "start.py", "exec"), {"__name__": "start"})
check("a failed boot writes the traceback where it survives",
      os.path.exists(ERR))
if os.path.exists(ERR):
    body = open(ERR).read()
    check("and names the failure", "ImportError" in body or "Error" in body,
          body[:60])

print()
if fails:
    print("%d BOOT TESTS FAILED" % len(fails))
    raise SystemExit(1)
print("all boot tests passed")
