# Run on the DAVEGA. Records what the STOCK screens draw.
#
# The firmware's modules are frozen bytecode, so their source cannot be read.
# It does not need to be: swap the display for a recorder, ask a stock screen
# to render, and what comes back is the exact layout - every coordinate, every
# colour, every string - which is a far better baseline to reskin from than a
# hand-copied approximation.
#
# Prints one call per line as CSV, for the host harness to replay.

def _first_that_works(fn, arg_sets, label):
    """Frozen code has no introspectable signatures, so try the plausible
    shapes and report which one the firmware actually wanted."""
    last = None
    for args in arg_sets:
        try:
            out = fn(*args)
            print("# %s%s ok" % (label, "(%d args)" % len(args)))
            return out if out is not None else True
        except TypeError as e:
            last = e
        except Exception as e:
            print("# %s%s raised %r" % (label, "(%d args)" % len(args), e))
            return None
    print("# %s: no signature matched (%r)" % (label, last))
    return None


def record(screen_cls_name="RealtimeScreen", payload_hex=None):
    import frozen.screen as sc
    import frozen.display as fd
    import frozen.screen_values as sv

    log = []

    class Recorder:
        # Mirror the real ILI9341's surface exactly. is_initialized and
        # is_horizontal are METHODS on the device; making them plain booleans
        # gets you "'bool' object isn't callable" from inside frozen code you
        # cannot read.
        width, height = 240, 320
        orientation = 0
        font = None

        def is_initialized(self):
            return True

        def is_horizontal(self):
            return False

        def init(self, *a, **k):
            self._log("init")

        def reset(self, *a, **k):
            self._log("reset")

        def _log(self, name, *a):
            log.append((name,) + a)

        def erase(self):
            self._log("erase")

        def set_color(self, fg, bg=None):
            self._log("set_color", fg, bg)

        def set_font(self, f):
            self._log("set_font", getattr(f, "__name__", "?"))

        def set_pos(self, x, y):
            self._log("set_pos", x, y)

        def fill_rectangle(self, x, y, w, h, c=None):
            self._log("fill_rectangle", x, y, w, h, c)

        def pixel(self, x, y, c=None):
            self._log("pixel", x, y, c)

        def print(self, t, scale=1):
            self._log("print", str(t), scale)

        def chars(self, t, scale=1):
            self._log("print", str(t), scale)

        def next_line(self, *a):
            self._log("next_line")

        def reset_scroll(self):
            self._log("reset_scroll")

        def scrdef(self, *a):
            self._log("scrdef")

        def scrset(self, *a):
            self._log("scrset")

        def blit(self, *a, **k):
            self._log("blit", *[x for x in a if isinstance(x, int)])

        def write(self, *a, **k):
            self._log("write")

        def writeblock(self, *a, **k):
            self._log("writeblock")

    rec = Recorder()
    # Every module that grabbed its own reference to the display has to be
    # redirected, or half the drawing lands on the real screen.
    patched = []
    for mod in (sc, fd, sv):
        if hasattr(mod, "DISPLAY"):
            patched.append((mod, mod.DISPLAY))
            mod.DISPLAY = rec
    for name in ("gauge", "number_cell", "display_util", "message_box"):
        try:
            m = __import__("frozen." + name, None, None, [name])
            if hasattr(m, "DISPLAY"):
                patched.append((m, m.DISPLAY))
                m.DISPLAY = rec
        except Exception:
            pass

    try:
        import frozen.config as cfgmod
        # Use the device's real settings, so the capture is the layout this
        # board actually shows rather than a default one.
        try:
            cfg = cfgmod.load_config()
        except Exception:
            cfg = cfgmod.Config
        import frozen.vesc_data as vd

        # A screen needs VESCs to read from. Build them rather than waiting
        # for a discovery scan, which cannot run while we are in WebREPL mode.
        payload = None
        if payload_hex:
            payload = bytes(int(payload_hex[i:i + 2], 16)
                            for i in range(0, len(payload_hex), 2))

        vescs = []
        for can_id in (123, 124):
            v = vd.Vesc()
            try:
                v.can_id = can_id
            except Exception:
                pass
            if payload is not None:
                # Feed the device's own parser a frame built on the host, so
                # the stock screens render a known state and we capture the
                # layout for it.
                try:
                    v.set_values(payload)
                except Exception as e:
                    print("# set_values raised %r" % (e,))
            vescs.append(v)

        cls = getattr(sc, screen_cls_name)
        screen = cls(cfg, lambda *a: None)
        values = _first_that_works(
            sv.ScreenValues,
            ((cfg, vescs, None), (cfg, vescs, vescs), (cfg, vescs)),
            "ScreenValues")
        if values is None:
            return log
        for meth in ("reset", "update"):
            fn = getattr(screen, meth, None)
            if fn is None:
                continue
            _first_that_works(
                fn, ((values,), (), (values, values), (values, 0)), meth)
    finally:
        for mod, old in patched:
            mod.DISPLAY = old

    print("### %s: %d calls" % (screen_cls_name, len(log)))
    for row in log:
        print("|".join(str(x) for x in row))
    return log
