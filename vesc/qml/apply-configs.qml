import QtQuick 2.7

// Write corrected motor configs to both Unity sides over the phone's TCP bridge.
//   vesc --offscreen --loadQml tools/apply-configs.qml
// Reads current config first (so the ESC's param set is populated), then loads
// the corrected XML over it and writes. App config is NOT touched - Setup Input
// still has to run for the Hoyt Puck.
Item {
    id: root

    property string host:  "@@HOST@@"
    property int    port:  @@PORT@@
    property int    canId: @@CANID@@
    property string dir:   "@@CONFDIR@@"

    property int step: 0
    property int ticks: 0
    property int waitTicks: 0

    function log(m) { console.log("VESCQ: " + m) }

    Component.onCompleted: {
        log("connecting to " + host + ":" + port)
        VescIf.connectTcp(host, port)
    }

    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 300) { root.log("TIMEOUT at step " + root.step); Qt.quit() }
            if (root.waitTicks > 0) { root.waitTicks--; return }

            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    root.log("connected")
                    root.step = 1; root.waitTicks = 4
                }
                break

            case 1:
                root.log("LOCAL: reading current mcconf")
                VescIf.commands().setSendCan(false)
                VescIf.commands().getMcconf()
                root.step = 2; root.waitTicks = 12
                break

            case 2:
                root.log("LOCAL: loadXml = " + VescIf.mcConfig().loadXml(root.dir + "/local-mcconf.xml", "MCConfiguration"))
                root.log("LOCAL: current_max now " + VescIf.mcConfig().getParamDouble("l_current_max")
                         + " gear " + VescIf.mcConfig().getParamDouble("si_gear_ratio"))
                VescIf.commands().setMcconf(true)
                root.step = 3; root.waitTicks = 16
                break

            case 3:
                root.log("CAN " + root.canId + ": reading current mcconf")
                VescIf.commands().setSendCan(true, root.canId)
                VescIf.commands().getMcconf()
                root.step = 4; root.waitTicks = 12
                break

            case 4:
                root.log("CAN: loadXml = " + VescIf.mcConfig().loadXml(root.dir + "/can124-mcconf.xml", "MCConfiguration"))
                root.log("CAN: current_max now " + VescIf.mcConfig().getParamDouble("l_current_max")
                         + " gear " + VescIf.mcConfig().getParamDouble("si_gear_ratio"))
                VescIf.commands().setMcconf(true)
                root.step = 5; root.waitTicks = 16
                break

            case 5:
                root.log("verifying: re-reading both sides")
                VescIf.commands().setSendCan(false)
                VescIf.commands().getMcconf()
                root.step = 6; root.waitTicks = 12
                break

            case 6:
                root.log("VERIFY local: current_max=" + VescIf.mcConfig().getParamDouble("l_current_max")
                         + " in_min=" + VescIf.mcConfig().getParamDouble("l_in_current_min")
                         + " gear=" + VescIf.mcConfig().getParamDouble("si_gear_ratio")
                         + " wheel=" + VescIf.mcConfig().getParamDouble("si_wheel_diameter")
                         + " ah=" + VescIf.mcConfig().getParamDouble("si_battery_ah"))
                VescIf.commands().setSendCan(true, root.canId)
                VescIf.commands().getMcconf()
                root.step = 7; root.waitTicks = 12
                break

            case 7:
                root.log("VERIFY can" + root.canId + ": current_max=" + VescIf.mcConfig().getParamDouble("l_current_max")
                         + " in_min=" + VescIf.mcConfig().getParamDouble("l_in_current_min")
                         + " gear=" + VescIf.mcConfig().getParamDouble("si_gear_ratio")
                         + " wheel=" + VescIf.mcConfig().getParamDouble("si_wheel_diameter")
                         + " ah=" + VescIf.mcConfig().getParamDouble("si_battery_ah"))
                VescIf.commands().setSendCan(false)
                root.step = 8; root.waitTicks = 4
                break

            case 8:
                root.log("done")
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
