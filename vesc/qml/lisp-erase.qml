import QtQuick 2.7
// Stop LispBM, then reboot the ESC so the PPM app restarts.
// uart-start stops the PPM+UART app; nothing restarts it except a reboot or a
// config write, which is why the PPM decoder stayed frozen.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property var cmds: null
    property int step: 0
    property int ticks: 0
    function log(m) { console.log("BOOT: " + m) }
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
                root.log("stopping and ERASING LispBM so it cannot autostart")
                root.cmds.lispSetRunning(false)
                root.cmds.lispEraseCode(16)
                root.step = 2; root.ticks = 0
                break
            case 2:
                if (root.ticks >= 6) {
                    root.log("rebooting ESC")
                    root.cmds.reboot()
                    root.step = 3; root.ticks = 0
                }
                break
            case 3:
                if (root.ticks >= 6) {
                    root.log("done - PPM app should be running again")
                    root.cmds = null
                    VescIf.disconnectPort()
                    Qt.quit()
                }
                break
            }
        }
    }
}
