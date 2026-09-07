import QtQuick 2.7

// Headless config pull over the phone's TCP bridge.
//   vesc --offscreen --loadQml tools/pull-configs.qml
// Works around the CLI being serial-only: VescIf.connectTcp() is Q_INVOKABLE,
// so QML can reach the ESC over TCP where --vescPort cannot.
Item {
    id: root

    property string host:  "@@HOST@@"
    property int    port:  @@PORT@@
    property int    canId: @@CANID@@
    property string outDir: "@@OUTDIR@@"

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
            if (root.ticks > 240) { root.log("TIMEOUT at step " + root.step); Qt.quit() }
            if (root.waitTicks > 0) { root.waitTicks--; return }

            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    root.log("connected: " + VescIf.getConnectedPortName())
                    root.step = 1; root.waitTicks = 4
                }
                break

            case 1:
                root.log("reading LOCAL mcconf")
                VescIf.commands().setSendCan(false)
                VescIf.commands().getMcconf()
                root.step = 2; root.waitTicks = 12
                break

            case 2:
                root.log("save local mcconf: " + VescIf.mcConfig().saveXml(root.outDir + "/local-mcconf.xml", "MCConfiguration"))
                VescIf.commands().getAppConf()
                root.step = 3; root.waitTicks = 12
                break

            case 3:
                root.log("save local appconf: " + VescIf.appConfig().saveXml(root.outDir + "/local-appconf.xml", "APPConfiguration"))
                root.log("switching to CAN " + root.canId)
                VescIf.commands().setSendCan(true, root.canId)
                VescIf.commands().getMcconf()
                root.step = 4; root.waitTicks = 12
                break

            case 4:
                root.log("save can mcconf: " + VescIf.mcConfig().saveXml(root.outDir + "/can" + root.canId + "-mcconf.xml", "MCConfiguration"))
                VescIf.commands().getAppConf()
                root.step = 5; root.waitTicks = 12
                break

            case 5:
                root.log("save can appconf: " + VescIf.appConfig().saveXml(root.outDir + "/can" + root.canId + "-appconf.xml", "APPConfiguration"))
                VescIf.commands().setSendCan(false)
                root.step = 6; root.waitTicks = 4
                break

            case 6:
                root.log("done, disconnecting")
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
