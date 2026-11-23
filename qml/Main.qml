import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import "Theme.js" as T

Window {
    id: win
    required property var station
    visible: true
    title: qsTr("JBC DME-2A Monitor")
    minimumWidth: 720
    minimumHeight: 520
    color: T.bgBottom

    readonly property var ports: station.ports
    property bool autoOpened: false
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

    // warm glow bottom left while any tool is working
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

    // short feedback for write commands
    Rectangle {
        id: toast
        z: 30
        property bool ok: true
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.sp * 3.2
        width: toastText.implicitWidth + win.sp * 2.4
        height: toastText.implicitHeight + win.sp * 1.0
        radius: height / 2
        color: T.bgMid
        border.width: 1
        border.color: ok ? T.green : T.red
        opacity: 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text {
            id: toastText
            anchors.centerIn: parent
            color: toast.ok ? T.text : T.red
            font.family: T.font; font.pixelSize: win.sp * 0.95
        }
        Timer { id: toastTimer; interval: 2500; onTriggered: toast.opacity = 0 }
        Connections {
            target: win.station
            function onNotice(ok, text) {
                toast.ok = ok
                toastText.text = text
                toast.opacity = 1
                toastTimer.interval = Math.max(2500, Math.min(12000, text.length * 60))
                toastTimer.restart()
            }
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

        // ---- Header ---------------------------------------------------
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
                    text: station.connected ? qsTr("CONNECTED") : qsTr("OFFLINE")
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
                    text: station.connected ? (station.info.port || "") : qsTr("Connect the station via USB-B")
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
                    Pill {
                        label: "⚙  " + qsTr("SETTINGS")
                        tint: T.cyan
                        filled: settingsPanel.open
                        dim: !station.connected
                        size: win.sp * 0.75
                        clickable: station.connected
                        onClicked: settingsPanel.show()
                    }
                    Repeater {
                        model: ["EN", "DE"]
                        Pill {
                            label: modelData
                            tint: T.cyan
                            filled: station.language === modelData.toLowerCase()
                            size: win.sp * 0.75
                            clickable: !filled
                            onClicked: station.setLanguage(modelData.toLowerCase())
                        }
                    }
                    Pill {
                        label: station.writable ? qsTr("EDITABLE") : qsTr("READ-ONLY")
                        tint: station.writable ? T.amber : T.cyan
                        size: win.sp * 0.75
                    }
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
                    ctl: win.station
                }
            }
        }

        // ---- Footer ---------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("History %1 min  ·  polling 2×/s").arg(Math.round(station.histSeconds / 60)) + "  ·  "
                      + (station.writable
                         ? qsTr("level: double click = activate, Ctrl+Shift+wheel = ±5 °C  ·  more under SETTINGS")
                         : qsTr("monitor only, the station stays usable"))
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

    SettingsPanel {
        id: settingsPanel
        objectName: "settingsPanel"
        anchors.fill: parent
        z: 20
        ctl: win.station
        sp: win.sp
    }

    // --settings: open the panel right after start (for screenshots)
    Connections {
        target: win.station
        enabled: win.station.openSettings && !win.autoOpened
        function onChanged() {
            if (win.station.connected) {
                win.autoOpened = true
                settingsPanel.show()
            }
        }
    }
}
