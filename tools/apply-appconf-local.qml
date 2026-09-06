import QtQuick 2.7

// Write the local side's app config. Used to switch app_to_use between
// PPM+UART (4, normal) and PPM only (1, so LispBM can own the UART).
Item {
    id: root
    property string host:  "@@HOST@@"
    property int    port:  @@PORT@@
    property string dir:   "@@CONFDIR@@"
    property var cmds: null
    property bool ctrlTypeWasNone: false
    property int step: 0
    property int ticks: 0
    property int waitTicks: 0

    function log(m) { console.log("VESCQ: " + m) }

    Component.onCompleted: { log("connecting to " + host + ":" + port); VescIf.connectTcp(host, port) }

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
                root.log("reading current appconf")
                root.cmds.setSendCan(false)
                root.cmds.getAppConf()
                root.step = 15; root.waitTicks = 12
                break
            case 15:
                // While ppm ctrl_type is 0 ("None") the ESC accepts writes to the
                // PPM block and reads back defaults. Establishing a real control
                // type first makes the same write stick, so do that pass now and
                // apply the full config afterwards.
                root.ctrlTypeWasNone = (VescIf.appConfig().getParamEnum("app_ppm_conf.ctrl_type") === 0)
                if (!root.ctrlTypeWasNone) { root.step = 2; root.waitTicks = 0; break }
                root.log("ppm ctrl_type is None - priming it before the real write")
                VescIf.appConfig().loadXml(root.dir + "/local-appconf.xml", "APPConfiguration")
                root.cmds.setAppConf()
                root.step = 2; root.waitTicks = 16
                break
            case 2:
                if (root.ctrlTypeWasNone) root.log("priming pass done - applying config for real")
                root.log("loadXml = " + VescIf.appConfig().loadXml(root.dir + "/local-appconf.xml", "APPConfiguration"))
                root.log("app_to_use now " + VescIf.appConfig().getParamEnum("app_to_use"))
                root.log("  after loadXml: ppm ctrl_type=" + VescIf.appConfig().getParamEnum("app_ppm_conf.ctrl_type")
                         + " tc=" + VescIf.appConfig().getParamBool("app_ppm_conf.tc")
                         + " ramp_pos=" + VescIf.appConfig().getParamDouble("app_ppm_conf.ramp_time_pos"))
                root.cmds.setAppConf()
                root.step = 3; root.waitTicks = 16
                break
            case 3:
                root.log("SKIP CAN side (ids collide) - local only")
                root.step = 32; root.waitTicks = 2
                break
            case 31:
                root.log("CAN loadXml = " + VescIf.appConfig().loadXml(root.dir + "/can124-appconf.xml", "APPConfiguration"))
                root.cmds.setAppConf()
                root.step = 32; root.waitTicks = 16
                break
            case 32:
                root.log("verifying both sides")
                root.cmds.setSendCan(false)
                root.cmds.getAppConf()
                root.step = 4; root.waitTicks = 12
                break
            case 4:
                root.log("VERIFY local: app_to_use=" + VescIf.appConfig().getParamEnum("app_to_use")
                         + " can_msgs_r1=" + VescIf.appConfig().getParamInt("can_status_msgs_r1")
                         + " ctrl_id=" + VescIf.appConfig().getParamInt("controller_id"))
                root.cmds.setSendCan(true, 124)
                root.cmds.getAppConf()
                root.step = 41; root.waitTicks = 12
                break
            case 41:
                root.log("VERIFY can124: app_to_use=" + VescIf.appConfig().getParamEnum("app_to_use")
                         + " can_msgs_r1=" + VescIf.appConfig().getParamInt("can_status_msgs_r1")
                         + " ctrl_id=" + VescIf.appConfig().getParamInt("controller_id"))
                root.cmds.setSendCan(false)
                root.step = 5; root.waitTicks = 2
                break
            case 5:
                root.log("done")
                root.cmds = null
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
