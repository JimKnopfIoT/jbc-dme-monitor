import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import "Theme.js" as T

Window {
    id: win
    required property var station
    visible: true
    title: "JBC DME-2A Monitor"
    minimumWidth: 720
    minimumHeight: 520
    color: T.bgBottom

    readonly property var ports: station.ports
    readonly property bool wide: width > 1600
    readonly property real sp: Math.max(12, Math.min(width, height) * 0.022)

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: T.bgTop }
            GradientStop { position: 0.6; color: T.bgMid }
            GradientStop { position: 1.0; color: T.bgBottom }
        }
    }

    // warmer Schimmer unten links, sobald ein Tool arbeitet (wie PM5)
    Canvas {
        anchors.fill: parent
        opacity: win.anyWorking ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 900 } }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var r = Math.max(width, height) * 0.75
            var g = ctx.createRadialGradient(0, height, 0, 0, height, r)
            g.addColorStop(0, T.alpha(T.orange, 0.16))
            g.addColorStop(0.5, T.alpha(T.orange, 0.05))
            g.addColorStop(1, T.alpha(T.orange, 0.0))
            ctx.fillStyle = g
            ctx.fillRect(0, 0, width, height)
        }
    }

    property bool anyWorking: {
        for (var i = 0; i < ports.length; ++i)
            if (ports[i].state === "work") return true
        return false
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: win.sp * 1.6
        spacing: win.sp * 1.2

        // ---- Kopfzeile ------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: win.sp * 1.2

            StatusLed {
                on: station.connected
                size: win.sp * 3.4
            }

            ColumnLayout {
                spacing: 2
                Text {
                    text: station.connected ? "CONNECTED" : "OFFLINE"
                    color: station.connected ? T.green : T.red
                    font.family: T.font; font.pixelSize: win.sp * 1.5
                    font.weight: Font.Normal; font.letterSpacing: 1
                }
                Text {
                    text: station.connected
                          ? [station.info.model || "", "SW " + (station.info.sw || "–"),
                             "HW " + (station.info.hw || "–")].join("  ·  ")
                          : station.message
                    color: T.textDim
                    font.family: T.font; font.pixelSize: win.sp * 0.95
                    font.weight: Font.Light
                }
                Text {
                    text: station.connected ? (station.info.port || "") : "Station per USB-B anschließen"
                    color: T.cyan
                    font.family: T.font; font.pixelSize: win.sp * 0.85
                    font.weight: Font.Light
                }
            }

            Item { Layout.fillWidth: true }

            ColumnLayout {
                spacing: 4
                Text {
                    Layout.alignment: Qt.AlignRight
                    text: "JBC DME-2A"
                    color: T.text
                    font.family: T.font; font.pixelSize: win.sp * 2.6
                    font.weight: Font.Light
                }
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    spacing: 8
                    Pill { label: "NUR LESEN"; tint: T.cyan; size: win.sp * 0.75 }
                    Text {
                        id: clock
                        color: T.textDim
                        font.family: T.font; font.pixelSize: win.sp * 0.95
                        font.weight: Font.Light
                        Timer {
                            interval: 1000; running: true; repeat: true; triggeredOnStart: true
                            onTriggered: clock.text = Qt.formatTime(new Date(), "HH:mm:ss")
                        }
                    }
                }
            }
        }

        // ---- Ports ------------------------------------------------------
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: win.wide ? 4 : 2
            rowSpacing: win.sp
            columnSpacing: win.sp

            Repeater {
                model: 4
                PortTile {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 1
                    portNo: index + 1
                    d: index < win.ports.length ? win.ports[index] : null
                    online: station.connected
                    histLength: station.histLength
                    histSeconds: station.histSeconds
                    sp: win.sp
                }
            }
        }

        // ---- Fußzeile ---------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "Verlauf " + Math.round(station.histSeconds / 60) + " min  ·  Abfrage 2×/s  ·  "
                      + "Monitor ohne Steuerung, Station bleibt bedienbar"
                color: T.textLow
                font.family: T.font; font.pixelSize: win.sp * 0.8
                font.weight: Font.Light
            }
            Item { Layout.fillWidth: true }
            Repeater {
                model: ["work", "stand", "sleep", "hiber"]
                RowLayout {
                    spacing: 6
                    Layout.leftMargin: win.sp * 0.8
                    Rectangle {
                        width: win.sp * 0.55; height: width; radius: width / 2
                        color: T.stateColor(modelData)
                    }
                    Text {
                        text: T.stateLabel(modelData)
                        color: T.textDim
                        font.family: T.font; font.pixelSize: win.sp * 0.75
                        font.letterSpacing: 0.5
                    }
                }
            }
        }
    }
}
