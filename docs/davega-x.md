# The DAVEGA X itself

The shim in this repo works *around* the display, by lying to it about the ESC's
firmware version. This page is about the other direction: what the display is,
and what you can do to it directly.

> The X's firmware is **not** open source, and the shop closed in May 2024. This
> is about your own hardware. Nothing here is redistributable and none of it is
> supported by anybody.

> [!WARNING]
> **Everything on this page was derived from the published firmware images and
> the vendor's own installer — not from a running device.** The two scripts in
> `davega/tools/` have never been executed on a DAVEGA. They are written
> against what the firmware images say, and your device is the authority. Run
> `recon()` first, `backup()` before any write, and expect to correct this page.

## Hardware

From the (now closed) shop listing and the firmware image itself:

| | |
|---|---|
| MCU | **ESP32** — 512 kB RAM, 4 MB flash |
| Display | 2.8″ 240×320 TFT, **ILI9341** (`frozen/ili934xnew.py`) |
| USB | micro USB behind the case, via a **CP2102** USB-UART bridge |
| Radio | 2.4 GHz WiFi 802.11 b/g/n, plus BLE — see below |
| To the ESC | 7-pin or 8-pin JST-PH, UART |
| Build | MicroPython on **ESP-IDF v4.0.1** |

So: rather more than a display. It is a WiFi/BLE computer that happens to have a
screen, and the micro USB port means serial access needs no soldering.

### Bluetooth is not a way in

The X advertises Bluetooth and has a `bt_enabled` setting, so it is a reasonable
guess that you could reach the REPL over BLE. You cannot.

Everything BLE in the firmware lives in `frozen/llt_bms.py`, and every string in
it is **central-role**: "Looking for BLE BMS...", "discovering services",
"discovering characteristics", "notify characteristic found", "write
characteristic found", "subscribing to notifications", "connected to BMS", "No
BLE BMS found". `DATA_SERVICE`, `NOTIFY_CHARACTERISTIC` and `WRITE_CHARACTERISTIC`
are the *BMS's* UUIDs, which the display connects out to.

There is no DAVEGA-side service, no advertised device name, and nothing that
would accept an inbound connection. `bt_enabled` turns on BMS polling, not a
transport. (MicroPython's `gap_advertise` and `gatts_*` names do appear in the
image, but every built-in name does — the symbol table is not evidence of use.)

So **WiFi and WebREPL is the only remote way onto the device**, with USB serial
over the CP2102 as the wired alternative.

## Firmware, and what is still downloadable

The vendor's own installer is a PyInstaller bundle wrapping `esptool`, and its
endpoints still resolve:

| | |
|---|---|
| Version index | `https://davega.eu/fw/index_v5.json` |
| App images | `https://davega.eu/fw/davegax-app-<version>.bin` |
| Full v5.01 image | `https://davega.eu/fw/davegax-firmware-v5.01.bin` |
| Cloud backups | `https://davega.eu/rest/backup/<device_id>/list` |
| Legacy v2/v3 | `https://davega.eu/fw/davegax-*.dfs` |

**There is a v5.07rc3, dated 2025-03-11** — newer than the v5.06 the changelog
stops at, released after the shop closed and never announced. Diffing it against
v5.06 shows no new user-visible strings, so treat it as a maintenance build.

**It does not lift the version gate.** Both images contain the same constant:

```
Supported VESC FW versions: 3.48 - 6.x
Unsupported VESC FW: %s.%s
INCOMPATIBLE FW VERSION! IGNORING.
```

That is the answer to "is there a newer firmware that fixes this?" — no. Nothing
the vendor ever shipped accepts VESC 7, so the shim stays necessary.

Note that installing v5 firmware over USB is **license-gated**: the installer
fetches a per-device key from `davega.eu/lk?device_id=...` and verifies it
against the device MAC. Your own device is already licensed; this is here so you
know the mechanism exists, not to work around it.

## Settings live in /config.json

The firmware stores its configuration as a **plain JSON file on the device
filesystem**, alongside its odometers:

```
/config.json        settings
/odometer1.json     trip / lifetime counters
/odometer2.json
```

Which means settings can be scripted. `davega/tools/settings.py` does
this over WebREPL: `show()` prints the config, `backup()` copies it aside,
`update(wheel_diameter_mm=200)` writes named keys back, and it refuses keys the
firmware does not already have so a typo cannot create a dead setting.

Keys visible in the firmware images, grouped the way the on-device menu groups
them:

| Menu | Keys |
|---|---|
| Drive | `wheel_diameter_mm`, `wheel_pulley_teeth`, `motor_pulley_teeth`, `motor_pole_pairs`, `motor_count`, `motor_temp_sensor` |
| Battery | `cells_in_series`, `battery_mah`, `battery_usable_capacity`, `cell_type`, `voltage_source` |
| Units | `imperial_units`, `distance_units`, `consumption_units`, `speed_units`, `temp_units` |
| Misc | `orientation`, `screen_values`, `riding_screen_main`, `update_interval_ms`, `show_total_voltage`, `show_unexpected_restarts`, `delay_switch_screen_on_stop_secs`, `delay_switch_to_bms_screen_secs` |
| Experimental | `rpm_from_esc2`, `detect_charger`, `vesc_alarm`, `voltage_multiplier`, `interpolate_energy` |
| Other | `reset_session_on_charge_up`, `initial_distance_km`, `backup_each_km`, `range_ramp_up_km`, `get_voltage_from_bms`, `max_cell_voltage_diff`, `bt_enabled` |
| WiFi | `wifi_ssid`, `wifi_password`, `wifi_connect_timeout_secs` |

Run `show()` on your own device before trusting that list — your firmware is the
authority, not this table.

What this does **not** cover is anything the display reads from the ESC. Speed,
current, voltage and distance come over the wire; change those with `make apply`,
not here.

## The app's structure

The firmware freezes 58 modules under `frozen/`. The ones worth knowing:

| Module | What it is |
|---|---|
| `frozen/config.py` | `load_config` / `save_config` against `/config.json` |
| `frozen/settings_menu.py`, `frozen/menu_*.py` | the on-device menu tree |
| `frozen/vesc_comm.py`, `vesc_data.py`, `vesc_util.py` | the VESC protocol — where the version gate lives |
| `frozen/update_fw.py`, `update_fw_checker.py` | OTA |
| `frozen/backup_data.py`, `serialize.py`, `autobackup.py` | cloud backup |
| `frozen/llt_bms.py` | BLE BMS support |
| `frozen/display.py`, `ili934xnew.py`, `gauge.py`, `screen*.py` | rendering |
| `frozen/license_key.py`, `autodownload_key.py` | licensing |

One string in there is worth flagging: `sending COMM_SET_MCCONF_PACKET`. The
DAVEGA does not only read from the ESC — it can write motor configuration to it.

## What we do not know, and how to find out

Rather than guess at the MCU, the flash size or where the version gate lives,
ask the device. `davega/tools/recon.py` is a read-only recon script:
paste it into the WebREPL prompt and call `recon()`.

It reports:

| | |
|---|---|
| `sys.implementation`, `sys.platform` | which MicroPython port — this identifies the MCU |
| `machine.freq()`, `machine.unique_id()` | clock and chip id |
| `esp.flash_size()`, `gc.mem_free()`, `os.statvfs("/")` | flash, RAM, free filesystem |
| a recursive listing of `/` | every file you can actually change |
| **`help("modules")`** | every module including the **frozen** ones — this is the stock app's structure |
| `boot.py`, `main.py`, `start.py`, `webrepl_cfg.py` | the code that runs at startup, printed |

Then `probe('frozen.something')` imports a module and prints what it exposes,
and `find_version_gate(mod)` looks for the constants behind
*"supported vesc firmware versions 5.x to 6.x"*.

Run `recon()` **before** changing anything and keep the output. It is the only
record of the stock device you are going to get.

## Can you patch the version gate itself?

Maybe — and if it works, the shim becomes unnecessary.

The v5.06 image names the gate outright. Two functions sit in
**`frozen/run_standard.py`**:

```
is_compatible_vesc_version
assert_compatible_vesc_version
```

alongside `is_vesc`, `has_vesc_restarted`, `scan_vescs` and `vesc_fault_alarm`.
The refusal is not buried in an expression somewhere; it has a name.

Frozen modules are compiled into the firmware image, so their source cannot be
edited on the device. But it does not need to be. MicroPython resolves a
module-level call through the module's globals **at call time**, so rebinding
the attribute before the app calls it should take effect:

```python
import frozen.run_standard as rs
rs.is_compatible_vesc_version = lambda *a, **k: True
rs.assert_compatible_vesc_version = lambda *a, **k: None
```

`davega/tools/start.py` is that, with the failure handling. The firmware
has executed a user `start.py` at boot since v5.03 — that is how
[sn8ke](https://github.com/janpom/sn8ke) hooks in, and sn8ke falls through to
the normal app when its button is not held, which is the behaviour this depends
on.

**The ordering works.** `frozen/main.py` names its boot steps in sequence:

```
load_license_key  is_button_press_and_hold  should_factory_reset
maybe_factory_reset  maybe_webrepl  exec_custom_start  boot_fw
```

`exec_custom_start` runs **before** `boot_fw`, so user code executes before the
application starts — which is what a patch needs. And `maybe_webrepl` runs
before `exec_custom_start`, so **a broken `start.py` cannot lock you out**: hold
UP+DOWN at boot and you reach a REPL regardless of what is on the filesystem.
That is the escape hatch, confirmed from the firmware rather than assumed.

**It is still untested**, and can fail two ways, both harmless:

- the caller may hold its own reference (`from ... import ...`), so patching the
  module changes nothing;
- the names may differ on your firmware version.

Both are a no-op rather than a brick, and the file catches its own exceptions.
Check the ground truth first with `probe('frozen.run_standard')` from
`recon.py`.

## Can you build and flash your own firmware?

Physically yes — it is an ESP32 with a CP2102 on a micro USB port, so `esptool`
reaches it without opening anything.

Practically, weigh it:

- **Back up first, without exception.** `esptool.py read_flash 0 ALL davega-stock.bin`
  over a serial connection. The vendor is gone; if you overwrite the stock image
  without a copy, nobody can give you another one.
- Stock firmware is frozen bytecode inside that image. You would be replacing
  the entire application, not patching it — a generic MicroPython build gives you
  a blank device, not a DAVEGA.
- The v5 installer is license-gated per device.

Since v5.07rc3 does not lift the version gate either, flashing buys you nothing
for the problem this repo exists to solve. The honest ordering is **REPL first,
`start.py` second, flashing a distant third** — the first two are reversible and
need no tools.

## If you learn something

The device is discontinued and the community has no documentation for it. If
recon output tells you something concrete — the port, where settings live, how
the version check is written — that is worth contributing back here.
