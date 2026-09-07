import QtQuick 2.7

// Continuous PPM readout - no phases, no timing to coordinate.
// Move the trigger whenever; the line only prints when the value CHANGES,
// so a static reading means the ESC genuinely is not seeing movement.
Item {
    id: root
    property string host:  "@@HOST@@"
    property int    port:  @@PORT@@
    property var cmds: null
    property int  step: 0
    property int  secs: 0
    property real last: -999
    property real hi: -1e9
    property real lo:  1e9
    property int  changes: 0

    function log(m) { console.log("PPM: " + m) }
    function f(x) { return (Math.round(x * 10000) / 10000).toFixed(4) }

    Connections {
        target: root.cmds
        function onDecodedPpmReceived(value, last_len) {
            if (last_len > root.hi) root.hi = last_len
            if (last_len < root.lo) root.lo = last_len
            if (Math.abs(last_len - root.last) > 0.002) {
                root.changes++
                root.log("  len=" + root.f(last_len) + "  value=" + root.f(value))
                root.last = last_len
            }
        }
    }

    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }

    Timer { interval: 50; running: true; repeat: true
            onTriggered: if (root.cmds) root.cmds.getDecodedPpm() }

    Timer {
        interval: 1000; running: true; repeat: true
        onTriggered: {
            if (root.step === 0) {
                if (VescIf.isPortConnected()) {
                    var fw = VescIf.getFirmwareNow()
                    if (fw.indexOf("x.x") >= 0) return
                    root.cmds = VescIf.commands()
                    root.log("connected. MOVE THE TRIGGER now - 25s. Only changes print.")
                    root.step = 1
                }
                return
            }
            root.secs++
            if (root.secs % 5 === 0) root.log("   ... " + root.secs + "s, changes seen: " + root.changes)
            if (root.secs >= 25) {
                root.log("=== range: " + root.f(root.lo) + " .. " + root.f(root.hi)
                         + "   changes: " + root.changes)
                root.cmds = null
                VescIf.disconnectPort()
                Qt.quit()
            }
        }
    }
}
