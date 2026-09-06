# QML tooling — drive the ESC over the phone's TCP bridge

The VESC Tool **CLI is serial-only** (`--vescPort` calls `connectSerial()`; a TCP
host:port or a socat PTY are both rejected as "Invalid serial port"). But
`--loadQml` runs arbitrary QML with `VescIf` in scope, and `VescIf.connectTcp()`
is `Q_INVOKABLE` — so QML *can* reach the ESC over the bridge. That's the workaround.

    vesc --offscreen --loadQml tools/pull-configs.qml     # read  -> backups/qml-pull/
    vesc --offscreen --loadQml tools/apply-configs.qml    # write <- configs-to-load/

Requires: phone VESC Tool connected to the ESC over BLE, Start page ->
"Wireless Bridge to Computer (TCP)" -> Activate Bridge. Desktop VESC Tool must be
CLOSED — the bridge takes one client at a time.

Set `host` / `port` / `canId` at the top of each script if the phone's IP changes.

## Why this works (source refs, vedderb/vesc_tool)
- `mobile/qmlui.cpp:96`  `setContextProperty("VescIf", vesc)`
- `vescinterface.h:199`  `Q_INVOKABLE void connectTcp(QString server, int port)`
- `vescinterface.h:73-74` `Q_INVOKABLE ConfigParams *mcConfig() / appConfig()`
- `configparams.h:96-97` `Q_INVOKABLE bool saveXml(...) / loadXml(...)`
- `commands.h:197,200`   `getMcconf()` / `getAppConf()` (public slots)
- `commands.h:199,202`   `setMcconf(bool)` / `setAppConf()` (public slots)
- `commands.h:39`        `Q_INVOKABLE bool setSendCan(bool, int id)`

Confirmed working in "limited mode" (VESC Tool 7.00 against 6.05 firmware).
