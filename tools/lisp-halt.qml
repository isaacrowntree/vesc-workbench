import QtQuick 2.7
// Stop the running LispBM script (releases the UART) without uploading anything.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property var cmds: null
    property int step: 0
    property int ticks: 0
    function log(m) { console.log("HALT: " + m) }
    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 80) { root.log("timeout"); Qt.quit() }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    var fw = VescIf.getFirmwareNow()
                    if (fw.indexOf("x.x") >= 0) break
                    root.cmds = VescIf.commands()
                    root.log("connected: " + fw)
                    root.step = 1
                }
                break
            case 1:
                root.log("stopping LispBM")
                root.cmds.lispSetRunning(false)
                root.step = 2; root.ticks = 0
                break
            case 2:
                if (root.ticks >= 6) {
                    root.log("stopped")
                    root.cmds = null
                    VescIf.disconnectPort()
                    Qt.quit()
                }
                break
            }
        }
    }
}
