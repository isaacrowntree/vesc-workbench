import QtQuick 2.7
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property var cmds: null
    property int step: 0
    property int ticks: 0
    function log(m) { console.log("ENUM: " + m) }
    Component.onCompleted: { VescIf.connectTcp(host, port) }
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 80) { Qt.quit() }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    var fw = VescIf.getFirmwareNow()
                    if (fw.indexOf("x.x") >= 0) break
                    root.cmds = VescIf.commands()
                    root.log("connected: " + fw)
                    root.step = 1; root.ticks = 0
                }
                break
            case 1:
                root.cmds.getAppConf()
                root.step = 2; root.ticks = 0
                break
            case 2:
                if (root.ticks < 10) break
                var names = VescIf.appConfig().getParamEnumNames("app_to_use")
                for (var i = 0; i < names.length; i++) root.log("  [" + i + "] " + names[i])
                root.log("current value = " + VescIf.appConfig().getParamEnum("app_to_use"))
                root.step = 3
                break
            case 3:
                root.cmds = null
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
