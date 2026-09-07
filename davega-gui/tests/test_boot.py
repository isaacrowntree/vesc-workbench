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

ROOT = os.path.abspath("davega-gui")
sys.path.insert(0, os.path.dirname(ROOT))

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

# gui.* is how start.py addresses the package on the device
gui = types.ModuleType("gui"); gui.__path__ = [ROOT, os.path.join(ROOT, "screens")]
sys.modules["gui"] = gui
for name in ("palette", "themes", "widgets", "base", "board", "anim", "startup",
             "riding", "panels", "app", "device", "input", "vesc", "session"):
    mod = __import__("screens." + name, fromlist=[name])
    sys.modules["gui." + name] = mod
sys.modules["gui.runner"] = __import__("runner")

# --- run start.py's wiring, bounded ------------------------------------
src = open(os.path.join(ROOT, "start.py")).read()
src = src.replace("while True:", "for _loop in range(40):")
src = src.replace('LIFETIME_PATH = "/data/gui-lifetime.json"',
                  'LIFETIME_PATH = %r' % LIFE)
# Force the periodic save to fire inside a short run, so the path that keeps
# lifetime totals across a power cycle is actually exercised.
src = src.replace("SAVE_EVERY_MS = 5 * 60 * 1000", "SAVE_EVERY_MS = 5")
ns = {"__name__": "start"}
exec(compile(src, "start.py", "exec"), ns)

d = disp.DISPLAY
fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


print("== the boot path wires up and draws")
check("start.py drew a dashboard (%d calls)" % len(d.calls), len(d.calls) > 50)
check("lifetime totals were persisted", os.path.exists(LIFE))
if os.path.exists(LIFE):
    import json
    saved = json.load(open(LIFE))
    check("and the file holds the session keys",
          "trip_km" in saved and "max_fet" in saved,
          "got %s" % sorted(saved)[:4])

# and confirm the escape hatch stands the dash down
buttons.BUTTON_UP = Pin(0)      # held
d.reset_state()
ns2 = {"__name__": "start"}
exec(compile(src, "start.py", "exec"), ns2)
check("holding UP stands the dash down for the stock app", len(d.calls) == 0,
      "drew %d calls" % len(d.calls))

print()
if fails:
    print("%d BOOT TESTS FAILED" % len(fails))
    raise SystemExit(1)
print("all boot tests passed")
