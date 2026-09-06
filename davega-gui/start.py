# Upload as /start.py. The firmware runs it before the stock app, so this
# replaces the DAVEGA's dashboard with the one in davega-gui.
#
# ESCAPE HATCH, and read this before uploading:
#   Hold UP while the DAVEGA boots and this file steps aside, leaving the
#   stock app to run as normal. WebREPL (hold UP+DOWN) is entered before any
#   of this executes, so a broken start.py can never lock you out.
#
# Anything unexpected falls through to the stock app rather than leaving you
# with a dead screen on the deck.


def _dash():
    import gc
    from frozen.buttons import BUTTON_UP

    # Held at boot: stand aside.
    if not BUTTON_UP.value():
        return False

    import gui.device as device
    import gui.input as user_input
    import gui.vesc as vesc
    from gui.board import Board
    from gui.app import App, Menu, MenuItem
    from gui.riding import Riding
    from gui.panels import (RangeScreen, OverviewScreen, SessionScreen,
                            LifetimeScreen)
    from gui.runner import Runner
    from machine import UART
    import utime

    cfg = {}
    try:
        import ujson
        with open("/data/config.json") as fh:
            cfg = ujson.load(fh)
    except Exception:                            # noqa: BLE001
        pass

    theme = cfg.get("theme", "nazare")
    board = Board(
        cells=cfg.get("cells_in_series", 12),
        parallel=cfg.get("parallel_groups", 4),
        pole_pairs=cfg.get("motor_pole_pairs", 7),
        gear_ratio=(cfg.get("wheel_pulley_teeth", 84)
                    / max(1, cfg.get("motor_pulley_teeth", 20))),
        wheel_m=cfg.get("wheel_diameter_mm", 200) / 1000.0,
        usable=cfg.get("battery_usable_capacity", 0.8),
    )
    esc_count = cfg.get("motor_count", 2)

    screens = (("riding", Riding), ("range", RangeScreen),
               ("overview", OverviewScreen), ("session", SessionScreen),
               ("lifetime", LifetimeScreen))
    menu = Menu([MenuItem("Theme", ["nazare", "rosso", "papaya", "ghost",
                                    "nevera", "hybrid", "minimal",
                                    "motorsport", "silver", "toro"],
                          on_select=_save_theme)])

    d = device.attach()
    app = App(screens, board, theme, menu)
    uart = UART(2, 115200, tx=16, rx=17)
    buttons = user_input.attach()

    gc.collect()
    Runner(app, d, uart, board, buttons, utime.ticks_ms, utime.ticks_diff,
           utime.sleep_ms, vesc, esc_count).run()
    return True


def _save_theme(app, value):
    """Menu selections outlive the ride."""
    try:
        import ujson
        with open("/data/config.json") as fh:
            cfg = ujson.load(fh)
        cfg["theme"] = value
        with open("/data/config.json", "w") as fh:
            ujson.dump(cfg, fh)
    except Exception:                            # noqa: BLE001
        pass
    app.set_theme(value)


try:
    _dash()
except Exception as e:                           # noqa: BLE001
    # A dash that fails should hand the screen back, not keep it.
    print("start.py: falling through to the stock app: %r" % (e,))
