import QtQuick 2.7

// Smallest possible LispBM test over the phone's TCP bridge.
// Proves the REPL is reachable before uploading any real script.
Item {
    id: root
    property string host:  "@@HOST@@"
    property int    port:  @@PORT@@
    property int step: 0
    property int ticks: 0
    property int waitTicks: 0

    function log(m) { console.log("PROBE: " + m) }

    Component.onCompleted: {
        log("connecting")
        VescIf.connectTcp(host, port)
    }

    property var cmds: null

    Connections {
        target: root.cmds
        function onPrintReceived(str) { console.log("LISP-OUT: " + str) }
        function onLispStatsRxMap(stats) { console.log("LISP-STATS: " + JSON.stringify(stats)) }
    }

    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 90) { root.log("timeout"); Qt.quit() }
            if (root.waitTicks > 0) { root.waitTicks--; return }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    root.cmds = VescIf.commands()
                    root.log("connected; fw=" + VescIf.getFirmwareNow())
                    root.step = 1; root.waitTicks = 4
                }
                break
            case 1:
                root.log("asking for lisp stats")
                VescIf.commands().lispGetStats(true)
                root.step = 2; root.waitTicks = 8
                break
            case 2:
                root.log("sending REPL: (+ 1 2)")
                VescIf.commands().lispSendReplCmd("(+ 1 2)")
                root.step = 3; root.waitTicks = 10
                break
            case 3:
                root.log("sending REPL: (print \"shim-probe-ok\")")
                VescIf.commands().lispSendReplCmd("(print \"shim-probe-ok\")")
                root.step = 4; root.waitTicks = 10
                break
            case 4:
                root.log("done")
                root.cmds = null
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
