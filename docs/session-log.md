> Working notes from the session this project came out of. Kept because the
> dead ends are as informative as the fixes. Hardware identifiers redacted.

# LaCroix eskate — firmware upgrade + setup

## Session log

### 2026-09-05 — recon started
- VESC Tool (Android, `vedder.vesctool`) running on Pixel 9 Pro (`<PHONE-SERIAL>`), driven over adb from the Mac.
- Connected **BLE** to `AA:BB:CC:DD:EE:FF`.
- Status bar reads **"limited mode"** → VESC Tool's firmware version doesn't match what the ESC is running.
- **HW: `UNITY`** (FOCBOX Unity — dual-motor, two ESC sides in one enclosure), confirmed by Isaac.
- **FW: `v6.05`**
- UUID: `<ESC-UUID>`
- **VESC Tool app version: 7.00** (versionCode 219, updated 2026-06-10)
- → Limited mode cause: **app 7.00 vs firmware 6.05**. Fix = flash ESC to a 7.00-series build (or downgrade the app to 6.05).
- Included-firmware Hardware/Firmware dropdowns were empty; hit "Download Latest" to fetch the archive and find out whether a UNITY target exists in 7.00.
- Backup taken: not yet

## Rules for this job
1. Back up configs (motor + app) BEFORE writing anything.
2. Identify hardware exactly before flashing. A FOCBOX Unity / LaCroix-branded ESC needs its own firmware build — stock VESC firmware can brick it.
3. Prefer USB for firmware flashing. BLE flashing is slow and a dropout mid-write is how you brick an ESC.
4. Wheels off the ground / motors clear for any motor detection.

## Files
- `screenshots/` — app state as we go
- `backups/` — exported config backups pulled off the phone
- `firmware/` — .bin files used

### 2026-09-05 — firmware archive + backup
- "Download Latest" fetched the 7.00 firmware archive. VESC Tool then auto-selected:
  - **Hardware: `UNITY`**, **Firmware: `VESC_default.bin`**
  - → a stock UNITY build **does** ship in the 7.00 series. No build-from-source needed.
- **Backup Configs: SUCCESS** for both UUIDs:
  - `<ESC-UUID>` (side A, the one BLE connects to)
  - `<ESC-UUID>` (side B, over internal CAN)
  - Confirms the Unity's two ESC sides are both reachable, and that limited mode does not block backup.
- ⚠️ Backups live in app-private internal storage (`/data/data/vedder.vesctool/`). NOT pullable over adb
  (`run-as` → "package not debuggable"; `/sdcard/Android/data/vedder.vesctool/files/` is empty).
  **The only copy is inside the phone app.** Don't clear app data. Get desktop VESC Tool to hold a real file copy.

## Open decisions
- [ ] Flash 7.00 over **USB** (safer, needs enclosure open) or **BLE** (convenient, dropout = brick risk)?
- [ ] Which remote? Determines the Setup Input path.
- [ ] Get a config copy onto the Mac before flashing (desktop VESC Tool, or export XML to Downloads).

### 2026-09-05 — desktop VESC Tool on the Mac
- Installed at `/Applications/VESC Tool.app`, version **`7.00-0+0e283530`** — exact match to the Android app (7.00).
  Confirms the flash target: get the ESC to 7.00 and both tools go full-featured.
- **It has a full CLI.** Key flags: `--queryDeviceFwParams`, `--getMcConf/--setMcConf`,
  `--getAppConf/--setAppConf`, `--uploadFirmware`, `--canFwd <id>`, `--vescPort <port>`, `--offscreen`,
  `--tcpServer <port>`, `--useMobileUi`.
  CLI connects over **serial only** (`--vescPort`, or autoconnect) — no BLE flag. So CLI ⇒ USB.
- macOS build declares `NSBluetoothAlwaysUsageDescription`, so the **GUI** likely can do BLE directly.
  (Corrects an earlier assumption that macOS desktop had no BLE.) Untested.

#### Helpers installed
- `vesc` (`~/.local/bin/vesc`) — no args launches the GUI, any args pass through to the CLI.
- `vesc-port` — lists `/dev/cu.usbmodem*` so you can see if the Unity is plugged in.
- `./backup-configs.sh [canId...]` — dumps mcconf+appconf XML for the local side and each CAN id
  into `backups/<timestamp>/`. Run this once USB is connected; it gives us file-based backups
  (unlike the phone's app-internal ones).

#### Connection options for desktop
| Path | CLI? | Notes |
|---|---|---|
| USB into the Unity | yes | Best: file backups + safest flash. Needs enclosure open. |
| Desktop BLE | no (GUI only) | Untested; Info.plist suggests supported. |
| TCP bridge via phone | no (GUI only) | Enable bridge in Android app; `adb forward tcp:65102 tcp:65102` makes it localhost. |

### 2026-09-05 — config captured + hardware research

Configs pulled to the Mac via desktop VESC Tool over the phone's TCP bridge
(Start page → "Wireless Bridge to Computer (TCP)", port 65102, phone IP 192.168.1.100).
Files: `backups/2026-09-05-pre-7.00-flash/board{1,2}-{mc,app}conf.xml` (+ C headers, + raw ConfBackup blobs).

- board1 = `controller_id 123` (local), board2 = `controller_id 124` (over CAN).
- The two sides are identical except for per-motor detection results (R/L/flux, hall tables,
  current offsets) — expected — **and the setup-info fields, which disagree (see below).**

#### As-found values (both sides unless noted)
| Param | Value |
|---|---|
| motor_type | 2 (FOC) |
| foc_sensor_mode | 2 (hall sensors) |
| l_current_max / min | ±66.81 A (123) / ±65.86 A (124) |
| l_in_current_max | **99 A per side** |
| l_in_current_min | **−60 A per side** |
| l_abs_current_max | 400 A |
| l_battery_cut_start / end | 40.8 V / 36 V (3.4 / 3.0 V per cell) |
| l_min_vin / l_max_vin | 8 V / 57 V |
| l_watt_max / min | ±1.5e6 (i.e. unlimited) |
| l_temp_fet / motor start-end | 85 → 100 °C |
| si_motor_poles | 14 (7 pole pairs) |
| si_battery_cells | 12 |
| app_to_use | 4 = PPM + UART |
| ppm ctrl_type | 3 = current, no reverse, with brake |
| ppm pulse start/center/end | 1.185 / 1.501 / 1.962 ms |
| ppm throttle_exp | 2.5 |
| ppm ramp pos/neg | 0.1 / 0.1 s |
| ppm multi_esc / tc | 1 / 1 (tc_max_diff 3000) |

#### Hardware (researched)
- Nazaré shipped: dual **6389 190 kv**, 8″ Kenda pneumatics (**200 mm**) on MBS Rockstar2 hubs,
  Focbox Unity, **Flipsky VX1** remote (matches PPM+UART).
- Stock drive was **HyperDrive = belt** (72 T pulley, 435-5M-15). **Falcon = gear drive, 4.2:1.**
- Isaac's board: **Falcon gear drive + Hyper rims (200 mm)**.
- Factory packs: Nazaré **12s6p** NCR20700B 1089 Wh (early) → **12s5p** P42A (later).
  **12s4p / 726 Wh was the Jaws, never the Nazaré.**

#### Wrong in the current config
| Param | Configured | Should be | Effect |
|---|---|---|---|
| si_gear_ratio | 3.231 (123) / 3.0 (124) | **4.2** (Falcon) | display speed overstated ~30% |
| si_wheel_diameter | 0.2 (123) / **0.083** (124) | **0.2** | 124 is a leftover default |
| si_battery_ah | 17 (123) / 6 (124) | **25.5** if 12s6p | range estimate |
| l_in_current_max | 99 A/side (198 A total) | **~40 A/side** | 198 A = 33 A/cell on 6P vs ~15 A max |
| l_in_current_min | −60 A/side (−120 A total) | **~−12 A/side** | regen ~30 A/cell charge on 6P |

3.231 = 42/13 — almost certainly left over from the pre-Falcon belt setup.
si_* fields are display-only; the l_in_current_* ones are not.

⚠️ Pack size still unconfirmed — config says 17 Ah (4P-shaped), Isaac believes 12s6p.
Confirm from the pack label (1089 Wh = 6P, 726 Wh = 4P) before setting current limits.

### 2026-09-05 — CORRECTIONS after checking firmware source + forums

Two earlier claims in this file were WRONG. Superseding them:

1. **`l_battery_regen_cut_start/end = 1000/1100` is the VESC firmware default**, not a misconfiguration.
   From `bldc/motor/mcconf_default.h`:
   `#define MCCONF_L_BATTERY_REGEN_CUT_START 1000.0` / `..._END 1100.0`.
   VESC ships with regen voltage limiting effectively disabled, relying on `l_max_vin`.
   Setting 50.4/51.5 for 12S is an optional improvement, NOT a fix.

2. **`l_abs_current_max = 400` is the Unity's hardware default and deliberate.**
   From `bldc/hwconf/other/hw_unity.h`:
   `// dangerous. Therefore it is disabled, and we rely on the DRV to limit the current`
   `#define MCCONF_L_MAX_ABS_CURRENT 400.0`
   **LEAVE IT AT 400.** The generic "abs ≈ 1.5× motor current" rule does not apply to Unity.
   Unity hw limits: `HW_LIM_CURRENT_IN -100..100`, `HW_LIM_CURRENT -150..150`, `HW_LIM_VIN 6..59`.

3. `l_in_current_max 99` / `min -60` are ALSO firmware defaults (same header) — i.e. never tuned
   to this pack. 99 is at the Unity's per-side hw ceiling of 100.

NOTE: `mcconf_default.h` / `appconf_default.h` in the backups dir are NOT firmware defaults —
VESC Tool's "Save C Header" exports the *currently loaded* config. Don't use them as a defaults
reference; use the bldc repo.

#### Community tuning formula (MBoards cheat sheet, dual motor, per ESC)
    Battery Current Max   = (parallel groups × 15) / 2
    Battery Current Regen = (parallel groups × −4) / 2
- 12s6p → **45 A / −12 A per side** (90 A / −24 A total)
- 12s4p → 30 A / −8 A per side
Motor current for 63xx: community range 60–80 A, sweet spot 60–70. **Existing 66 A is correct, leave it.**

#### Remote: Hoyt Puck (NOT the stock Flipsky VX1)
The stored PPM calibration (1.185 / 1.501 / 1.962 ms) was almost certainly done with the VX1.
**Re-run Setup Input with the Puck** — highest-value action in the whole list.

#### Revised change list
| Setting | Now | To |
|---|---|---|
| l_in_current_max | 99 | **45** |
| l_in_current_min | −60 | **−12** |
| si_gear_ratio | 3.231 / 3.0 | **4.2** |
| si_wheel_diameter | 0.2 / 0.083 | **0.2** both |
| si_battery_ah | 17 / 6 | **25.5** (if 12s6p — still unconfirmed) |
| PPM calibration | VX1-era | **re-run with Puck** |
| l_abs_current_max | 400 | leave |
| regen cut | 1000/1100 | leave (optional 50.4/51.5) |
