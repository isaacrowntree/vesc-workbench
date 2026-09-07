# Upload as /start.py. The firmware runs it before the stock app, so this
# replaces the DAVEGA's dashboard with the one in davega-gui.
#
# ESCAPE HATCH, and read this before uploading:
#   Hold UP while the DAVEGA boots and this file steps aside, leaving the
#   stock app to run as normal. WebREPL (hold UP+DOWN) is entered before any
#   of this executes, so a broken start.py can never lock you out.
#
# Deliberately tiny, and deliberately plain source. Everything else ships as
# precompiled bytecode in /gui, but this file is the one that has to work when
# /gui does not - so it depends on nothing in it, and the escape hatch is
# checked before the first import.

ERROR_PATH = "/data/gui-error.txt"

try:
    from frozen.buttons import BUTTON_UP
    if BUTTON_UP.value():                        # active low: not held
        import os
        try:
            os.remove(ERROR_PATH)                # last boot's failure, if any
        except Exception:                        # noqa: BLE001
            pass
        import gui.boot
        gui.boot.main()
    else:
        print("start.py: UP held, standing aside for the stock app")
except Exception as e:                           # noqa: BLE001
    # A dash that fails hands the screen back rather than keeping it - but
    # silently handing it back tells the rider nothing and costs a WebREPL
    # session to diagnose. Write the traceback somewhere it survives.
    print("start.py: falling through to the stock app: %r" % (e,))
    try:
        import sys
        with open(ERROR_PATH, "w") as fh:
            fh.write("%r\n" % (e,))
            # A full traceback where the runtime offers one; the repr above is
            # written first so the file is never empty if it does not.
            printer = getattr(sys, "print_exception", None)
            if printer is not None:
                printer(e, fh)
    except Exception:                            # noqa: BLE001
        pass
