# DAVEGA X settings, over WebREPL.
#
# The X keeps its configuration in /config.json - a plain JSON file on the
# device filesystem - so settings can be read, diffed and written from the
# REPL instead of clicked through the on-device menu.
#
# Get a REPL: hold UP + DOWN while the DAVEGA boots, connect to its access
# point, open the MicroPython WebREPL client over HTTP. Then paste this in.
#
# Always run `backup()` before `update()`. There is no undo and no vendor.

CONFIG = "/data/config.json"


def _load():
    import ujson
    with open(CONFIG) as f:
        return ujson.load(f)


def show():
    """Print the whole config, sorted."""
    cfg = _load()
    for k in sorted(cfg):
        print("%-32s %r" % (k, cfg[k]))
    return cfg


def backup(path="/data/config.backup.json"):
    """Copy /config.json aside on the device. Do this first, every time."""
    import ujson
    cfg = _load()
    with open(path, "w") as f:
        ujson.dump(cfg, f)
    print("backed up %d keys to %s" % (len(cfg), path))
    return path


def restore(path="/data/config.backup.json"):
    import ujson
    with open(path) as f:
        cfg = ujson.load(f)
    with open(CONFIG, "w") as f:
        ujson.dump(cfg, f)
    print("restored %d keys from %s - reboot to apply" % (len(cfg), path))


def update(**kw):
    """Set keys and write them back. Refuses keys the config does not have,
    since a typo would otherwise create a dead key that nothing reads.

        update(wheel_diameter_mm=200, motor_pole_pairs=7)

    Reboot for the change to take effect.
    """
    import ujson
    cfg = _load()
    unknown = [k for k in kw if k not in cfg]
    if unknown:
        print("unknown keys, refusing: %s" % unknown)
        print("run show() to see what this firmware actually has")
        return None
    for k, v in kw.items():
        print("%-32s %r -> %r" % (k, cfg[k], v))
        cfg[k] = v
    with open(CONFIG, "w") as f:
        ujson.dump(cfg, f)
    print("written - reboot to apply")
    return cfg


def set_theme(name):
    """Select a davega-gui theme.

    `theme` is our key, not the stock firmware's, so unlike update() this is
    allowed to create it. The stock app ignores keys it does not know.
    """
    import ujson
    cfg = _load()
    before = cfg.get("theme", "<unset>")
    cfg["theme"] = name
    with open(CONFIG, "w") as f:
        ujson.dump(cfg, f)
    print("theme %s -> %s (reboot to apply)" % (before, name))
    return name


def get_theme():
    return _load().get("theme", "<unset>")


def set_display(mode):
    """'day' or 'night'. Ours, not the stock app's, so it may be created."""
    import ujson
    cfg = _load()
    before = "day" if cfg.get("theme_light") else "night"
    cfg["theme_light"] = (mode == "day")
    with open(CONFIG, "w") as f:
        ujson.dump(cfg, f)
    print("display %s -> %s (reboot to apply)" % (before, mode))
    return mode


# Keys seen in the v5.01-v5.07rc3 firmware images. Present for orientation
# only: run show() to see what your firmware really has, and treat any
# difference as the firmware being right.
KNOWN_KEYS = (
    # drive
    "wheel_diameter_mm", "wheel_pulley_teeth", "motor_pulley_teeth",
    "motor_pole_pairs", "motor_count", "motor_temp_sensor",
    # battery
    "cells_in_series", "battery_mah", "battery_usable_capacity", "cell_type",
    "voltage_source",
    # units and display
    "imperial_units", "distance_units", "consumption_units", "speed_units",
    "temp_units", "orientation", "screen_values", "riding_screen_main",
    "update_interval_ms", "show_total_voltage", "show_unexpected_restarts",
    "delay_switch_screen_on_stop_secs", "delay_switch_to_bms_screen_secs",
    # behaviour
    "rpm_from_esc2", "detect_charger", "vesc_alarm", "voltage_multiplier",
    "reset_session_on_charge_up", "interpolate_energy", "initial_distance_km",
    "backup_each_km", "range_ramp_up_km", "get_voltage_from_bms",
    "max_cell_voltage_diff", "bt_enabled",
    # wifi
    "wifi_ssid", "wifi_password", "wifi_connect_timeout_secs",
)


def use_second_esc(on=True):
    """Take the speed reading from the second ESC instead of the first.

    Added in firmware v5.06 as "RPM from ESC 2" under Experimental Settings.
    The display polls both motors either way; this only picks which one the
    speed calculation uses.
    """
    return update(rpm_from_esc2=bool(on))
