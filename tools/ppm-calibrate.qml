import QtQuick 2.7

// Live PPM calibration for the Hoyt Puck.
// Samples the decoded pulse length while you sweep the trigger, then reports
// true min / centre / max - more precise than the wizard's one-shot capture.
//
//   make ppm-cal
//
// PHASES (announced as it runs):
//   1. NEUTRAL  - hands off the trigger
//   2. THROTTLE - hold full throttle to the mechanical stop
//   3. BRAKE    - hold full brake to the mechanical stop
Item {
    id: root
    property string host:  "@@HOST@@"
    property int    port:  @@PORT@@

    property var cmds: null
    property int step: 0
    property int ticks: 0

    // ms, as reported by last_len
    property real cur: 0
    property real neutral: 0
    property real hi: -1e9
    property real lo:  1e9
    property int  samples: 0
    property real val: 0
    property real vhi: -1e9
    property real vlo: 1e9

    function log(m) { console.log("PPM: " + m) }
    function f(x) { return (Math.round(x * 10000) / 10000).toFixed(4) }

    Connections {
        target: root.cmds
        function onDecodedPpmReceived(value, last_len) {
            root.cur = last_len
            root.val = value
            if (value > root.vhi) root.vhi = value
            if (value < root.vlo) root.vlo = value
            root.samples++
            if (root.step === 2 || root.step === 3) {
                if (last_len > root.hi) root.hi = last_len
                if (last_len < root.lo) root.lo = last_len
            }
        }
    }

    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }

    // poll fast so a brief full-travel hold is caught
    Timer {
        interval: 60; running: true; repeat: true
        onTriggered: if (root.cmds && root.step > 0) root.cmds.getDecodedPpm()
    }

    Timer {
        interval: 1000; running: true; repeat: true
        onTriggered: {
            root.ticks++
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    var fw = VescIf.getFirmwareNow()
                    if (fw.indexOf("x.x") >= 0) return
                    root.cmds = VescIf.commands()
                    root.log("connected: " + fw)
                    root.log("")
                    root.log(">>> PHASE 1: HANDS OFF the trigger (4s)")
                    root.step = 1; root.ticks = 0
                }
                break
            case 1:
                root.log("   len=" + root.f(root.cur) + "  value=" + root.f(root.val))
                if (root.ticks >= 4) {
                    root.neutral = root.cur
                    root.log("")
                    root.log(">>> PHASE 2: HOLD FULL THROTTLE to the stop (6s)")
                    root.step = 2; root.ticks = 0
                }
                break
            case 2:
                root.log("   len=" + root.f(root.cur) + " value=" + root.f(root.val) + "   maxlen " + root.f(root.hi) + " maxval " + root.f(root.vhi))
                if (root.ticks >= 6) {
                    root.log("")
                    root.log(">>> PHASE 3: HOLD FULL BRAKE to the stop (6s)")
                    root.step = 3; root.ticks = 0
                }
                break
            case 3:
                root.log("   len=" + root.f(root.cur) + " value=" + root.f(root.val) + "   minlen " + root.f(root.lo) + " minval " + root.f(root.vlo))
                if (root.ticks >= 6) { root.step = 4 }
                break
            case 4:
                root.log("")
                root.log("=== RESULT (" + root.samples + " samples) ===")
                root.log("pulse_start  = " + root.f(root.lo))
                root.log("pulse_center = " + root.f(root.neutral))
                root.log("pulse_end    = " + root.f(root.hi))
                root.log("throttle travel above centre = " + root.f(root.hi - root.neutral))
                root.log("brake travel below centre    = " + root.f(root.neutral - root.lo))
                root.log("decoded value range: " + root.f(root.vlo) + " .. " + root.f(root.vhi))
                root.step = 5
                break
            case 5:
                root.cmds = null
                VescIf.disconnectPort()
                Qt.quit()
                break
            }
        }
    }
}
