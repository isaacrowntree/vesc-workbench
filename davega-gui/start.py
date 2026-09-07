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


LIFETIME_PATH = "/data/gui-lifetime.json"
SAVE_EVERY_MS = 5 * 60 * 1000        # five minutes


def _read_json(path):
    try:
        import ujson
        with open(path) as fh:
            return ujson.load(fh)
    except Exception:                            # noqa: BLE001
        return {}


def _write_json(path, obj):
    try:
        import ujson
        with open(path, "w") as fh:
            ujson.dump(obj, fh)
    except Exception:                            # noqa: BLE001
        pass


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
    from gui.session import Session, Resistance
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
    light = bool(cfg.get("theme_light", False))
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
    menu = Menu([
        MenuItem("Theme", ["nazare", "rosso", "papaya", "ghost", "nevera",
                           "hybrid", "minimal", "motorsport", "silver",
                           "toro"], on_select=_save_theme),
        MenuItem("Display", ["night", "day"], on_select=_save_light),
    ])
    if light:
        menu.items[1].pos = 1

    d = device.attach()
    app = App(screens, board, theme, menu, light=light)
    # tx 17 / rx 16 - the reverse of what VescComm's own attributes suggest,
    # and the difference between reading the board and reading nothing. A
    # firmware-7 reply is 79 bytes, so the buffer has to be bigger than the
    # reference firmware's 70.
    # A short port timeout matters: uart.read() blocks for it when nothing has
    # arrived, and at 100 ms that cost 211 ms a telemetry read. At 5 ms, with
    # the reader asking any() first, the same read takes 17.
    uart = UART(2, 115200, tx=17, rx=16, rxbuf=256, timeout=5)
    buttons = user_input.attach()

    session = Session(board)
    lifetime = Session(board, lifetime=True).load(_read_json(LIFETIME_PATH))
    resistance = Resistance(board.cells)

    gc.collect()
    runner = Runner(app, d, uart, board, buttons, utime.ticks_ms,
                    utime.ticks_diff, utime.sleep_ms, vesc, esc_count,
                    session=session, lifetime=lifetime, resistance=resistance)

    # Lifetime totals are worth keeping across a power cycle; a ride is not,
    # and writing every frame would wear the flash for nothing.
    last_save = utime.ticks_ms()
    while True:
        runner.step()
        if utime.ticks_diff(utime.ticks_ms(), last_save) > SAVE_EVERY_MS:
            lifetime.merge(session)
            session.reset()
            _write_json(LIFETIME_PATH, lifetime.to_dict())
            last_save = utime.ticks_ms()
        utime.sleep_ms(50)


def _save_light(app, value):
    """Day or night, remembered."""
    _write_config("theme_light", value == "day")
    app.set_light(value == "day")


def _save_theme(app, value):
    """Menu selections outlive the ride."""
    _write_config("theme", value)
    app.set_theme(value)


def _write_config(key, value):
    """One key, in place. Everything else in the file is the stock app's and
    must survive untouched."""
    try:
        import ujson
        with open("/data/config.json") as fh:
            cfg = ujson.load(fh)
        cfg[key] = value
        with open("/data/config.json", "w") as fh:
            ujson.dump(cfg, fh)
    except Exception:                            # noqa: BLE001
        pass


try:
    _dash()
except Exception as e:                           # noqa: BLE001
    # A dash that fails should hand the screen back, not keep it.
    print("start.py: falling through to the stock app: %r" % (e,))
