import QtQuick 2.7
// DAVEGA proxy health check: samples the LispBM counters twice and reports rates.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property var cmds: null
    property int step: 0
    property int ticks: 0
    property var s1: null
    property int windowSecs: @@SECS@@

    function log(m) { console.log("DBG: " + m) }
    function g(m, k) { return (m && m[k] !== undefined) ? m[k] : 0 }

    Connections {
        target: root.cmds
        function onLispStatsRxMap(st) {
            var m = {}
            var gl = st["globals"]
            for (var i = 0; i < gl.length; i++) m[gl[i]["name"]] = gl[i]["value"]
            m["cpu"] = st["cpu_use"]
            if (root.step === 2) { root.s1 = m; root.log("baseline captured") }
            else if (root.step === 4) root.report(m)
        }
    }

    function report(m) {
        var din  = g(m,"dbg-in")   - g(root.s1,"dbg-in")
        var dout = g(m,"dbg-out")  - g(root.s1,"dbg-out")
        var dbad = g(m,"dbg-bad")  - g(root.s1,"dbg-bad")
        var dpro = g(m,"dbg-proc") - g(root.s1,"dbg-proc")
        var d50  = g(m,"dbg-c50")  - g(root.s1,"dbg-c50")
        var d51  = g(m,"dbg-c51")  - g(root.s1,"dbg-c51")
        var d0   = g(m,"dbg-c0")   - g(root.s1,"dbg-c0")
        var dblk = g(m,"dbg-blk")  - g(root.s1,"dbg-blk")
        var dsyn = g(m,"dbg-sync") - g(root.s1,"dbg-sync")
        log("")
        log("=== DAVEGA proxy over " + root.windowSecs + "s ===")
        log("frames in        : " + din  + "   (" + (din/root.windowSecs).toFixed(1) + "/s)")
        log("replies out      : " + dout + "   (" + (dout/root.windowSecs).toFixed(1) + "/s)")
        log("forwarded to fw  : " + dpro)
        log("malformed frames : " + dbad)
        log("resync skips     : " + dsyn + "   (bytes dropped hunting for a frame start)")
        log("blocking handled : " + dblk + "   (ping " + (g(m,"dbg-ping")-g(root.s1,"dbg-ping")) + ")")
        log("")
        log("command mix:")
        log("  50 GET_VALUES_SELECTIVE       : " + d50)
        log("  51 GET_VALUES_SETUP_SELECTIVE : " + d51)
        log("  0  FW_VERSION (version gate)  : " + d0)
        log("  34 FORWARD_CAN (2nd motor)    : " + (din - dout - dbad) + "  <- not answered")
        log("  last other id                 : " + g(m,"dbg-cx"))
        log("")
        var rate = din > 0 ? (dout / din * 100) : 0
        log("reply rate       : " + rate.toFixed(0) + "%")
        log("telemetry rate   : " + ((d50 + d51) / root.windowSecs).toFixed(1) + "/s   <- what the display refreshes at")
        log("lisp cpu         : " + g(m,"cpu") + "%")
        log("")
        if (din === 0)                 log("VERDICT: NO TRAFFIC - DAVEGA not polling (check cable/power)")
        else if (dbad > din * 0.1)     log("VERDICT: FRAMING PROBLEM - many malformed frames")
        else if (dsyn > din)           log("VERDICT: FRAMING PROBLEM - losing sync more often than framing")
        else if (rate < 50)            log("VERDICT: DEGRADED - under half of requests answered")
        else if (d0 > 0 && d50 === 0)  log("VERDICT: STUCK AT HANDSHAKE - version asked repeatedly, no telemetry")
        else if ((d50 + d51) / root.windowSecs < 3)
                                       log("VERDICT: SLOW - telemetry under 3/s, the display will read laggy")
        else if (d50 > 0 || d51 > 0)   log("VERDICT: HEALTHY - telemetry flowing")
        else                           log("VERDICT: UNCLEAR - traffic present but no telemetry commands")
    }

    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }

    Timer {
        interval: 1000; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 90) { root.log("timeout"); Qt.quit() }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    var fw = VescIf.getFirmwareNow()
                    if (fw.indexOf("x.x") >= 0) return
                    root.cmds = VescIf.commands()
                    root.log("connected: " + fw)
                    root.step = 1
                }
                break
            case 1: root.cmds.lispGetStats(true); root.step = 2; root.ticks = 0; break
            case 2: if (root.s1 !== null) { root.log("sampling for " + root.windowSecs + "s..."); root.step = 3; root.ticks = 0 } break
            case 3: if (root.ticks >= root.windowSecs) { root.cmds.lispGetStats(true); root.step = 4; root.ticks = 0 } break
            case 4: if (root.ticks >= 4) root.step = 5; break
            case 5: root.cmds = null; VescIf.disconnectPort(); Qt.quit(); break
            }
        }
    }
}
