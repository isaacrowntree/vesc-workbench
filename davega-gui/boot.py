"""The dashboard, from boot to the first frame.

Lives here rather than in `start.py` so it can ship as bytecode. MicroPython
compiles a `.py` every time it imports it, and on this ESP32 that compile is
most of the wait between switching the board on and seeing a number - 154 kB
of source against 62 kB of `.mpy` that needs no compiling at all.

`start.py` stays plain source: it is the escape hatch, and an escape hatch
that depends on the toolchain having run is not one.
"""
LIFETIME_PATH = "/data/gui-lifetime.json"
ERROR_PATH = "/data/gui-error.txt"
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


def main():
    """Take the screen and run the dashboard.

    `start.py` has already cleared the error file and checked the escape
    hatch; by the time this runs the decision to take the screen is made, and
    anything raised here is its problem to report.
    """
    import gc

    # Shipped as bytecode, so importing no longer means compiling - but the
    # heap is small and still fragments, and a collect between imports costs
    # nothing. It was the difference between booting and handing the screen
    # back when these were source.
    import gui.device as device
    gc.collect()
    import gui.input as user_input
    import gui.vesc as vesc
    gc.collect()
    from gui.board import Board
    from gui.themes import THEMES, DEFAULT
    from gui.app import App, Menu, MenuItem
    gc.collect()
    from gui.riding import Riding
    gc.collect()
    from gui.panels import (RangeScreen, OverviewScreen, SessionScreen,
                            LifetimeScreen)
    gc.collect()
    from gui.runner import Runner
    from gui.session import Session, Resistance
    from machine import UART
    import utime
    gc.collect()

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
        wh_per_km=cfg.get("wh_per_km", 18.0),
    )
    esc_count = cfg.get("motor_count", 2)

    screens = (("riding", Riding), ("range", RangeScreen),
               ("overview", OverviewScreen), ("session", SessionScreen),
               ("lifetime", LifetimeScreen))
    menu = Menu([
        # From the registry, not a second hand-kept list: a theme added to
        # themes.py is selectable on the board without touching this file.
        # The default leads, so the first press off it is a real alternative.
        MenuItem("Theme", [DEFAULT] + sorted(k for k in THEMES
                                             if k != DEFAULT),
                 on_select=_save_theme),
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
    # The other controllers on the CAN bus. A Unity is two of them in one
    # case - 123 answers over the wire, 124 through it - and the reply carries
    # only the one that answered, so without this the board reports half its
    # pack draw and one motor's temperature.
    can_ids = cfg.get("can_ids", [124] if esc_count > 1 else [])
    runner = Runner(app, d, uart, board, buttons, utime.ticks_ms,
                    utime.ticks_diff, utime.sleep_ms, vesc, esc_count,
                    session=session, lifetime=lifetime, resistance=resistance,
                    can_ids=can_ids)

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
