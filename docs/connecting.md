# Connecting: driving VESC Tool from the command line

This is the part that is not documented anywhere else, so it gets its own page.

**The short version:** VESC Tool's CLI cannot connect over the network, but
VESC Tool's *QML runtime* can, and the CLI will run arbitrary QML for you. So
you get the full configuration API over your phone's Bluetooth bridge, with
nothing plugged into the ESC.

---

## Why the obvious approach fails

VESC Tool ships a CLI. It looks like it should work:

```sh
vesc_tool --vescPort /dev/tty.usbmodem123 --xmlConfFile mcconf.xml
```

`--vescPort` goes straight to `connectSerial()`. It takes a serial device and
nothing else:

- an IP and port (`--vescPort 192.168.1.100:65102`) is rejected
- a `socat` PTY bridged to the TCP socket is opened, then the handshake never
  completes — VESC Tool drives the serial port directly and the pseudo-terminal
  does not behave like a real one

If your ESC is sealed inside a deck or an enclosure, that is the end of the
road for the documented CLI.

## What actually works

VESC Tool also accepts `--loadQml`, and QML loaded that way runs **inside the
application**, with the singleton `VescIf` in scope. `VescIf` exposes the whole
connection and configuration API to QML — including `connectTcp()`.

Combine that with the phone app's TCP bridge and the path is:

```
your laptop  --TCP-->  phone (VESC Tool app)  --BLE-->  ESC
```

Minimal working example — save as `connect.qml`:

```qml
import QtQuick 2.7

Item {
    id: root
    property int ticks: 0

    Component.onCompleted: VescIf.connectTcp("192.168.1.100", 65102)

    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 60) { console.log("timeout"); Qt.quit() }
            if (!VescIf.isPortConnected()) return

            // Firmware params arrive AFTER the socket connects. Until they do,
            // getFirmwareNow() returns "x.x" and every config read is garbage.
            var fw = VescIf.getFirmwareNow()
            if (fw.indexOf("x.x") >= 0) return

            console.log("connected, fw " + fw)
            VescIf.disconnectPort()
            Qt.quit()
        }
    }
}
```

Run it headless:

```sh
# macOS
"/Applications/VESC Tool.app/Contents/MacOS/VESC Tool" --offscreen --loadQml connect.qml

# Linux
vesc_tool --offscreen --loadQml connect.qml
```

`--offscreen` keeps the GUI from appearing. `console.log` goes to stdout, which
is how every target in this repo reports back.

> [!IMPORTANT]
> **Wait for the firmware string.** `isPortConnected()` goes true as soon as the
> socket is up, several seconds before the ESC has sent its firmware and config
> parameters. Reading `mcConfig()` in that window returns defaults that look
> exactly like a wiped controller. The same applies after any reboot — let the
> ESC settle before you read it back.

## Setting it up

### 1. Phone

1. Install **VESC Tool** (Android or iOS) and connect to the ESC over Bluetooth
   as normal — you should see live values.
2. Go to the **Start** page → **Wireless Bridge to Computer (TCP)** →
   **Activate Bridge**.
3. Note the phone's IP on your Wi-Fi. The bridge listens on **port 65102**.

Both devices must be on the same network, and the network must not have client
isolation enabled (most guest Wi-Fi does — use a phone hotspot instead if so).

> The bridge accepts **one client at a time**. Desktop VESC Tool's GUI counts as
> that client, so close it before running anything here.

### 2. Desktop

Install VESC Tool for desktop. You never open the GUI; the binary is just the
Qt runtime the scripts need.

| OS | Binary |
|---|---|
| macOS | `/Applications/VESC Tool.app/Contents/MacOS/VESC Tool` |
| Linux | `vesc_tool` on `PATH`, or `VESC=/opt/vesc_tool/vesc_tool` |

The Makefile detects the OS and picks the right one. Override with `VESC=`.

### 3. This repo

Put your phone's IP in a profile. `profiles/local.mk` is gitignored, so it is
the right place for anything specific to your network:

```make
# profiles/local.mk
HOST  ?= 192.168.1.100   # phone running the bridge
PORT  ?= 65102
CANID ?= 124             # second motor thread, if you have one
```

```sh
make check    # bridge reachable? desktop VESC Tool closed?
make probe    # connect, report firmware and LispBM stats
```

`make check` is worth running first every time. It tells the two failure modes
apart before you waste two minutes on a timeout.

Every other target takes the same profile:

```sh
make pull PROFILE=profiles/local.mk
```

## What you get once connected

`VescIf` is the whole API. The useful entry points:

| Call | What it is |
|---|---|
| `VescIf.connectTcp(host, port)` | open the bridge connection |
| `VescIf.isPortConnected()` | socket up (not: params received) |
| `VescIf.getFirmwareNow()` | firmware string, `"x.x"` until params arrive |
| `VescIf.mcConfig()` | motor config — `getParamDouble`, `updateParamDouble`, … |
| `VescIf.appConfig()` | app config: throttle, PPM, CAN, UART |
| `VescIf.commands()` | live commands and telemetry |
| `VescIf.commands().setMcconf(true)` | write motor config — **the `true` matters** |
| `VescIf.commands().lispGetStats(true)` | LispBM heap, CPU and globals |
| `VescIf.commands().lispSendReplCmd(str)` | evaluate Lisp on the ESC |
| `CodeLoader.lispUploadFromPath(...)` | upload a Lisp script (see below) |

Two that will cost you an afternoon if you get them wrong:

- **`setMcconf(false)` silently does nothing.** The write is accepted and
  discarded. Always pass `true`, which asks the ESC to check and confirm it.
- **`commands().lispWriteCode()` does not land code.** The ESC reports "did you
  forget to upload the code". Use `CodeLoader.lispUploadFromPath` instead —
  upload happens in 384-byte chunks with a per-chunk timeout, which is why
  `tools/minify-lisp.py` exists.

## Connection troubleshooting

| Symptom | Cause |
|---|---|
| `make check` says UNREACHABLE | Bridge not activated, phone asleep, wrong IP, or client isolation on the Wi-Fi |
| `make check` says desktop VESC Tool is running | The GUI is holding the bridge's one connection slot |
| Connects, then everything reads as defaults | Read taken before firmware params arrived — gate on `getFirmwareNow()` |
| Connects, then drops after ~30 s | Phone screen locked and the app was backgrounded; disable auto-lock while working |
| Silent hang until the timeout kills it | A blocking command was issued while another was in flight — serialise with a `busy` flag |
| Writes appear to work but nothing changes | `setMcconf(false)` |

## A second motor over CAN

On a dual controller (a FOCBOX Unity is one STM32 running two motor threads
over internal CAN) the second side is reached by CAN id. `make pull` reads both;
set `CANID` in your profile. `COMM_FORWARD_CAN` from LispBM is still
[unverified](known-issues.md) — the QML path is the one to trust today.
