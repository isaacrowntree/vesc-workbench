# DAVEGA X recon. Paste into the WebREPL prompt (hold UP+DOWN while booting to
# get there, then connect a browser to the DAVEGA's access point).
#
# Read-only: it lists, imports and inspects. It writes nothing and reboots
# nothing. Run it before touching anything so you have a record of the stock
# device, and keep the output.

def recon():
    import sys, os, gc

    def head(t):
        print("\n=== %s ===" % t)

    head("interpreter")
    print("implementation :", sys.implementation)
    print("platform       :", sys.platform)
    print("version        :", sys.version)
    try:
        print("byteorder      :", sys.byteorder)
    except AttributeError:
        pass

    head("machine")
    try:
        import machine
        print("freq           :", machine.freq())
        print("unique_id      :", machine.unique_id())
        try:
            print("reset_cause    :", machine.reset_cause())
        except AttributeError:
            pass
    except ImportError as e:
        print("no machine:", e)

    head("flash / memory")
    try:
        import esp
        print("flash_size     :", esp.flash_size())
    except (ImportError, AttributeError) as e:
        print("no esp module  :", e)
    gc.collect()
    print("mem_free       :", gc.mem_free())
    print("mem_alloc      :", gc.mem_alloc())
    try:
        s = os.statvfs("/")
        print("fs total bytes :", s[0] * s[2])
        print("fs free bytes  :", s[0] * s[3])
    except OSError as e:
        print("statvfs failed :", e)

    head("filesystem")
    def walk(path, depth=0):
        try:
            entries = sorted(os.listdir(path))
        except OSError as e:
            print("  " * depth + "%s <unreadable: %s>" % (path, e))
            return
        for name in entries:
            full = path.rstrip("/") + "/" + name
            try:
                st = os.stat(full)
            except OSError:
                print("  " * depth + name + " <stat failed>")
                continue
            if st[0] & 0x4000:                      # directory
                print("  " * depth + name + "/")
                if depth < 3:
                    walk(full, depth + 1)
            else:
                print("  " * depth + "%-28s %8d" % (name, st[6]))
    walk("/")

    head("modules on the device")
    # This is the important one: it lists FROZEN modules too, which is the app
    # itself. Anything under frozen.* is compiled into the firmware image.
    help("modules")

    head("boot / main")
    for f in ("boot.py", "main.py", "start.py", "webrepl_cfg.py"):
        try:
            with open(f) as fh:
                body = fh.read()
            print("--- %s (%d bytes)" % (f, len(body)))
            print(body)
        except OSError:
            print("--- %s: absent" % f)


def probe(modname):
    """Import a frozen module and show what it exposes.

    Start with whatever help('modules') revealed, e.g.:
        probe('frozen.display'); probe('frozen.vesc'); probe('frozen.settings')
    """
    try:
        m = __import__(modname)
    except Exception as e:      # noqa: BLE001 - report anything, keep going
        print("%s: import failed: %s" % (modname, e))
        return None
    for part in modname.split(".")[1:]:
        m = getattr(m, part)
    print("=== %s ===" % modname)
    print("file:", getattr(m, "__file__", "<frozen>"))
    for name in sorted(dir(m)):
        if name.startswith("__"):
            continue
        try:
            val = getattr(m, name)
        except Exception as e:  # noqa: BLE001
            print("  %-28s <error: %s>" % (name, e))
            continue
        r = repr(val)
        if len(r) > 90:
            r = r[:87] + "..."
        print("  %-28s %s" % (name, r))
    return m


def find_version_gate(mod):
    """Look for the numbers behind 'supported vesc firmware versions 5.x to 6.x'.

    Pass a module returned by probe(). Reports any int or tuple attribute that
    looks like a firmware bound, which is where the refusal is configured.
    """
    for name in sorted(dir(mod)):
        if name.startswith("__"):
            continue
        try:
            val = getattr(mod, name)
        except Exception:       # noqa: BLE001
            continue
        if isinstance(val, int) and 3 <= val <= 9:
            print("  int   %-24s = %r" % (name, val))
        elif isinstance(val, (tuple, list)) and val and all(
                isinstance(x, int) for x in val):
            print("  seq   %-24s = %r" % (name, val))
        elif isinstance(val, str) and ("version" in val.lower()
                                       or "vesc" in val.lower()):
            print("  str   %-24s = %r" % (name, val))
