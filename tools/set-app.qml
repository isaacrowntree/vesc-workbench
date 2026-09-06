import QtQuick 2.7
// Set app_to_use alone, then read it back. Writing the whole XML did not
// stick; this narrows it to one field so the failure has one cause.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property int    want: @@CANID@@      // reused as the value to write
    property var cmds: null
    property int step: 0
    property int ticks: 0
    property int waitTicks: 0
    function log(m) { console.log("APP: " + m) }
    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 120) { root.log("TIMEOUT"); Qt.quit() }
            if (root.waitTicks > 0) { root.waitTicks--; return }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    if (VescIf.getFirmwareNow().indexOf("x.x") >= 0) break
                    root.cmds = VescIf.commands()
                    root.log("connected: " + VescIf.getFirmwareNow())
                    root.step = 1; root.waitTicks = 4
                }
                break
            case 1:
                root.cmds.setSendCan(false)
                root.cmds.getAppConf()
                root.step = 2; root.waitTicks = 14
                break
            case 2:
                root.log("before: app_to_use=" + VescIf.appConfig().getParamEnum("app_to_use")
                         + "  can_msgs=" + VescIf.appConfig().getParamInt("can_status_msgs_r1"))
                VescIf.appConfig().updateParamEnum("app_to_use", root.want)
                // A control field that nothing else touches, to tell "this
                // one value is being overwritten" from "no write persists".
                VescIf.appConfig().updateParamInt("can_status_msgs_r1", 15)
                root.log("in memory now: app_to_use=" + VescIf.appConfig().getParamEnum("app_to_use")
                         + "  can_msgs=" + VescIf.appConfig().getParamInt("can_status_msgs_r1"))
                root.cmds.setAppConf()
                root.step = 3; root.waitTicks = 24
                break
            case 3:
                root.cmds.getAppConf()
                root.step = 4; root.waitTicks = 14
                break
            case 4:
                root.log("after: app_to_use=" + VescIf.appConfig().getParamEnum("app_to_use")
                         + "  can_msgs=" + VescIf.appConfig().getParamInt("can_status_msgs_r1"))
                root.log("done")
                VescIf.disconnectPort(); Qt.quit()
                break
            }
        }
    }
}
