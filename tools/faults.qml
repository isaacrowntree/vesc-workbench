import QtQuick 2.7

// Read the ESC's stored fault history and live values, both motor sides.
// The terminal command `faults` returns what actually tripped on a ride -
// the GUI shows only the current fault, which is almost always None by the
// time you plug in.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property int    canId: @@CANID@@
    property var cmds: null
    property int step: 0
    property int ticks: 0
    property int waitTicks: 0

    function log(m) { console.log("FLT: " + m) }

    Connections {
        target: root.cmds
        function onPrintReceived(str) { console.log("    " + str) }
        function onValuesReceived(v, mask) {
            console.log("    v_in=" + v.v_in.toFixed(1) + "V  fet=" + v.temp_mos.toFixed(1)
                        + "C  motor=" + v.temp_motor.toFixed(1) + "C"
                        + "  duty=" + v.duty_now.toFixed(2)
                        + "  amp_motor=" + v.current_motor.toFixed(1)
                        + "  amp_batt=" + v.current_in.toFixed(1)
                        + "  Ah=" + v.amp_hours.toFixed(2) + " / regen " + v.amp_hours_charged.toFixed(2)
                        + "  fault=" + v.fault_str)
        }
    }

    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }

    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 200) { root.log("TIMEOUT at step " + root.step); Qt.quit() }
            if (root.waitTicks > 0) { root.waitTicks--; return }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    var fw = VescIf.getFirmwareNow()
                    if (fw.indexOf("x.x") >= 0) break
                    root.cmds = VescIf.commands()
                    root.log("connected: " + fw)
                    root.step = 1; root.waitTicks = 4
                }
                break
            case 1:
                root.log("--- LOCAL live values")
                root.cmds.setSendCan(false)
                root.cmds.getValues()
                root.step = 2; root.waitTicks = 8
                break
            case 2:
                root.log("--- LOCAL fault history")
                root.cmds.sendTerminalCmd("faults")
                root.step = 3; root.waitTicks = 14
                break
            case 3:
                root.log("--- CAN " + root.canId + " live values")
                root.cmds.setSendCan(true, root.canId)
                root.cmds.getValues()
                root.step = 4; root.waitTicks = 8
                break
            case 4:
                root.log("--- CAN " + root.canId + " fault history")
                root.cmds.sendTerminalCmd("faults")
                root.step = 5; root.waitTicks = 14
                break
            case 5:
                root.cmds.setSendCan(false)
                root.log("done")
                root.cmds = null
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
