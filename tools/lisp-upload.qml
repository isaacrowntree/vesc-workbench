import QtQuick 2.7
import Vedder.vesc.codeloader 1.0

// Upload a LispBM script over the phone's TCP bridge and run it.
//   vesc --offscreen --loadQml tools/lisp-upload.qml
// Set `codePath` to the .lisp file. Prints anything the script emits.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property string codePath: "@@LISP@@"
    property int runSeconds: 20

    property var cmds: null

    CodeLoader { id: loader }
    property string code: ""
    property int step: 0
    property int ticks: 0
    property int waitTicks: 0
    property bool uploadOk: false
    property bool busy: false

    function log(m) { console.log("UP: " + m) }

    Connections {
        target: root.cmds
        function onPrintReceived(str)   { console.log("LISP-OUT: " + str) }
        function onLispEraseCodeRx(ok)  { console.log("UP: erase ack=" + ok) }
        function onLispWriteCodeRx(ok, offset) { console.log("UP: write ack=" + ok + " offset=" + offset) }
        function onLispRunningResRx(ok) { console.log("UP: running ack=" + ok) }
        function onLispStatsRxMap(s)    { console.log("LISP-STATS: " + JSON.stringify(s)) }
    }

    Component.onCompleted: {
        code = Utility.arr2str(Utility.readAllFromFile(codePath))
        log("code loaded, " + code.length + " chars from " + codePath)
        log("connecting")
        VescIf.connectTcp(host, port)
    }

    Timer {
        interval: 250; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 240) { root.log("timeout at step " + root.step); Qt.quit() }
            if (root.waitTicks > 0) { root.waitTicks--; return }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    // wait for the fw params to actually arrive - "x.x" means not yet,
                    // and the lisp upload path needs them.
                    var fw = VescIf.getFirmwareNow()
                    if (fw.indexOf("x.x") >= 0) { break }
                    root.cmds = VescIf.commands()
                    root.log("connected: " + fw)
                    root.step = 1; root.waitTicks = 4
                }
                break
            case 1:
                if (root.code.length === 0) { root.log("FAILED: empty or missing script " + root.codePath); root.step = 9; break }
                root.step = 2; root.waitTicks = 3
                root.log("stopping any running script")
                root.cmds.lispSetRunning(false)
                break
            case 2:
                // lispUploadFromPath blocks; the timer re-enters while it runs.
                // Guard with a flag rather than advancing early, so the result
                // is recorded before the start-gate reads it.
                if (root.busy) break
                root.busy = true
                loader.setVesc(VescIf)
                root.log("uploading: " + root.codePath)
                // lispStreamString has a 4s per-chunk timeout vs lispUploadFromPath's
                // 1s, which the WiFi->phone->BLE hop cannot meet. Streams to RAM and
                // runs immediately, so no lispSetRunning needed either.
                var ok = false
                for (var i = 0; i < 3 && !ok; i++) {
                    ok = loader.lispUploadFromPath(root.codePath, true)
                    root.log("upload attempt " + (i+1) + " = " + ok)
                }
                root.uploadOk = ok
                root.step = 4; root.waitTicks = 3
                break
            case 4:
                root.step = 5; root.waitTicks = root.runSeconds * 4
                if (!root.uploadOk) { root.log("UPLOAD FAILED"); root.step = 9; break }
                root.log("starting script")
                root.cmds.lispSetRunning(true)
                break
            case 5:
                root.log("collecting stats")
                root.cmds.lispGetStats(true)
                root.step = 6; root.waitTicks = 3
                break
            case 6:
                root.log("QMLDONE script running")
                root.step = 9
                break
            case 9:
                root.cmds = null
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
