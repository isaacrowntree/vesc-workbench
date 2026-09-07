import QtQuick 2.7

// Read the flight recorder's globals and print a ride summary.
Item {
    id: root
    property string host: "@@HOST@@"
    property int    port: @@PORT@@
    property var cmds: null
    property int step: 0
    property int ticks: 0

    function log(m) { console.log("LOG: " + m) }
    function g(m, k) { return (m && m[k] !== undefined) ? m[k] : 0 }

    Connections {
        target: root.cmds
        function onLispStatsRxMap(st) {
            var m = {}
            var gl = st["globals"]
            for (var i = 0; i < gl.length; i++) m[gl[i]["name"]] = gl[i]["value"]
            root.report(m)
        }
    }

    function report(m) {
        var mins = g(m, "uptime") / 60.0
        console.log("")
        console.log("=== ride summary, " + mins.toFixed(1) + " min, "
                    + g(m, "samples") + " samples ===")
        console.log("motor current  : " + g(m, "hi-motor").toFixed(0) + " A peak   "
                    + g(m, "lo-motor").toFixed(0) + " A regen")
        console.log("pack current   : " + g(m, "hi-batt").toFixed(0) + " A draw   "
                    + g(m, "lo-batt").toFixed(0) + " A charge")
        console.log("temperature    : FET " + g(m, "hi-fet").toFixed(0) + " C   motor "
                    + g(m, "hi-mot").toFixed(0) + " C")
        var sag = g(m, "lo-vin")
        console.log("voltage sag    : " + (sag > 199 ? "not seen under load" : sag.toFixed(1) + " V"))
        console.log("peak erpm/duty : " + g(m, "hi-erpm").toFixed(0) + "   "
                    + g(m, "hi-duty").toFixed(2))
        console.log("")
        var code = g(m, "flt-code")
        if (code === 0) {
            console.log("faults         : none")
        } else {
            console.log("FIRST FAULT    : code " + code + " of " + g(m, "flt-count") + " total")
            console.log("  at           : " + g(m, "flt-vin").toFixed(1) + " V, "
                        + g(m, "flt-erpm").toFixed(0) + " erpm, duty "
                        + g(m, "flt-duty").toFixed(2) + ", "
                        + g(m, "flt-motor").toFixed(0) + " A")
        }
        console.log("")
        var tc = g(m, "tc-events")
        console.log("traction control: " + (tc === 0 ? "never engaged" : tc + " engagements")
                    + ", worst wheel difference " + g(m, "tc-worst").toFixed(0) + " erpm")
        if (g(m, "tc-worst") === 0 && g(m, "hi-erpm") > 0)
            console.log("  (0 with the wheels having turned means the second"
                        + " motor could not be read, not that there was no slip)")
        VescIf.disconnectPort()
        Qt.quit()
    }

    Component.onCompleted: { log("connecting"); VescIf.connectTcp(host, port) }

    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 120) { root.log("TIMEOUT"); Qt.quit() }
            switch (root.step) {
            case 0:
                if (VescIf.isPortConnected()) {
                    if (VescIf.getFirmwareNow().indexOf("x.x") >= 0) break
                    root.cmds = VescIf.commands()
                    root.step = 1
                }
                break
            case 1:
                root.cmds.lispGetStats(true)
                root.step = 2; root.ticks = 100
                break
            }
        }
    }
}
