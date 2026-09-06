import QtQuick 2.7
// Does each motor side report its own pack current, or the same one twice?
// On a Unity there is one pack and one input shunt, so summing them would
// double-count energy - and halve any range estimate built on it.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property int    canId: @@CANID@@
    property var cmds: null
    property int step: 0
    property int ticks: 0
    property int waitTicks: 0
    function log(m) { console.log("DUAL: " + m) }
    Connections {
        target: root.cmds
        function onValuesReceived(v, mask) {
            console.log("    v_in=" + v.v_in.toFixed(2)
                        + "  current_in=" + v.current_in.toFixed(2)
                        + "  current_motor=" + v.current_motor.toFixed(2)
                        + "  amp_hours=" + v.amp_hours.toFixed(4)
                        + "  amp_hours_chg=" + v.amp_hours_charged.toFixed(4)
                        + "  watt_hours=" + v.watt_hours.toFixed(3)
                        + "  tacho=" + v.tachometer_abs)
        }
    }
    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 90) { root.log("TIMEOUT"); Qt.quit() }
            if (root.waitTicks > 0) { root.waitTicks--; return }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    if (VescIf.getFirmwareNow().indexOf("x.x") >= 0) break
                    root.cmds = VescIf.commands()
                    root.step = 1; root.waitTicks = 4
                }
                break
            case 1:
                root.log("--- LOCAL (id 123)")
                root.cmds.setSendCan(false); root.cmds.getValues()
                root.step = 2; root.waitTicks = 8
                break
            case 2:
                root.log("--- CAN " + root.canId)
                root.cmds.setSendCan(true, root.canId); root.cmds.getValues()
                root.step = 3; root.waitTicks = 8
                break
            case 3:
                root.cmds.setSendCan(false)
                root.log("done"); VescIf.disconnectPort(); Qt.quit()
                break
            }
        }
    }
}
