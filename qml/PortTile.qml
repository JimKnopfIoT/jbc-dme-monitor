import QtQuick
import QtQuick.Layouts
import "Theme.js" as T

Rectangle {
    id: tile
    property int portNo: 1
    property var d: null
    property bool online: false
    property int histLength: 360
    property int histSeconds: 180
    property real sp: 14
    property var ctl: null
    readonly property bool writable: hasTool && ctl !== null && ctl.writable
    readonly property int tMin: ctl && ctl.info.min_temp ? ctl.info.min_temp : 90
    readonly property int tMax: ctl && ctl.info.max_temp ? ctl.info.max_temp : 450

    readonly property string st: (online && d) ? d.state : "none"
    readonly property color sc: T.stateColor(st)
    readonly property bool hasTool: online && d && d.tool_id > 0
    readonly property real temp: hasTool && d.temp !== null ? d.temp : NaN
    readonly property real setT: hasTool && d.set !== null ? d.set : NaN
    readonly property color tc: T.tempColor(temp, setT)

    radius: sp * 1.3
    color: T.panel
    border.width: 1
    border.color: T.alpha(sc, st === "none" ? 0.12 : 0.40)
    Behavior on border.color { ColorAnimation { duration: 400 } }
    clip: true

    // coloured glow from the top, strong while working
    Rectangle {
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        height: parent.height * 0.65
        radius: tile.radius
        opacity: tile.st === "work" ? 0.16 : (tile.st === "none" ? 0.0 : 0.06)
        Behavior on opacity { NumberAnimation { duration: 600 } }
        gradient: Gradient {
            GradientStop { position: 0.0; color: tile.sc }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: tile.sp * 1.2
        spacing: tile.sp * 0.5

        // head: port, tool, state
        RowLayout {
            Layout.fillWidth: true
            spacing: tile.sp * 0.6
            Rectangle { width: 3; Layout.preferredHeight: tile.sp * 1.6; color: T.cyan; radius: 1 }
            Text {
                text: "P" + tile.portNo
                color: T.cyan
                font.family: T.font; font.pixelSize: tile.sp * 1.4; font.weight: Font.Light
            }
            Text {
                text: tile.hasTool ? tile.d.tool : "—"
                color: tile.hasTool ? T.text : T.textLow
                font.family: T.font; font.pixelSize: tile.sp * 1.4; font.weight: Font.Normal
            }
            Item { Layout.fillWidth: true }
            Pill {
                label: T.stateLabel(tile.st)
                tint: tile.sc
                filled: tile.st === "work"
                dim: tile.st === "none"
                size: tile.sp * 0.75
            }
        }

        // large temperature
        RowLayout {
            Layout.fillWidth: true
            spacing: tile.sp * 0.3
            Text {
                id: big
                text: isNaN(tile.temp) ? "– –" : Math.round(tile.temp)
                color: tile.tc
                Behavior on color { ColorAnimation { duration: 500 } }
                font.family: T.font
                font.pixelSize: Math.min(tile.height * 0.22, tile.width * 0.18)
                font.weight: Font.ExtraLight
                Layout.alignment: Qt.AlignBottom
            }
            ColumnLayout {
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: big.font.pixelSize * 0.16
                spacing: 0
                Text {
                    text: "°C"
                    color: T.alpha(tile.tc, 0.8)
                    font.family: T.font; font.pixelSize: big.font.pixelSize * 0.28
                    font.weight: Font.Light
                }
                Text {
                    text: isNaN(tile.setT) ? "Set –" : "Set " + Math.round(tile.setT) + " °C"
                    color: T.textDim
                    font.family: T.font; font.pixelSize: tile.sp * 1.0
                    font.weight: Font.Light
                }
            }
            Item { Layout.fillWidth: true }
            // deviation from set point
            Text {
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: big.font.pixelSize * 0.18
                visible: tile.st === "work" && !isNaN(tile.temp) && !isNaN(tile.setT)
                readonly property int dv: Math.round(tile.temp - tile.setT)
                text: (dv > 0 ? "+" : "") + dv + " K"
                color: Math.abs(dv) <= 10 ? T.green : (dv > 0 ? T.red : T.amber)
                font.family: T.font; font.pixelSize: tile.sp * 1.3; font.weight: Font.Light
            }
        }

        // temperature levels
        RowLayout {
            Layout.fillWidth: true
            spacing: tile.sp * 0.5
            visible: tile.hasTool
            Text {
                text: "Levels"
                color: T.textLow
                font.family: T.font; font.pixelSize: tile.sp * 0.8
            }
            Repeater {
                model: (tile.hasTool && tile.d.levels) ? tile.d.levels : []
                Pill {
                    id: lvPill
                    readonly property bool active: index === tile.d.level
                    readonly property bool usable: modelData !== null
                    // value shown while the wheel is turning, until the station reports it
                    property real pending: NaN
                    readonly property bool busy: !isNaN(pending)
                    label: !usable ? "–" : Math.round(busy ? pending : modelData) + "°"
                    tint: busy ? T.amber : (active ? tile.tc : T.textDim)
                    filled: active || busy
                    dim: !usable
                    size: tile.sp * 0.8
                    scale: lvMouse.containsMouse && tile.writable && usable ? 1.08 : 1.0
                    Behavior on scale { NumberAnimation { duration: 120 } }

                    readonly property var value: modelData
                    onValueChanged: if (busy && value !== null
                                        && Math.round(value) === Math.round(pending)) {
                        pending = NaN
                        giveUp.stop()
                    }

                    // send 0.7 s after the last wheel step, not on every step
                    Timer {
                        id: commit
                        interval: 700
                        onTriggered: {
                            tile.ctl.setLevelTemp(tile.portNo - 1, index, Math.round(lvPill.pending))
                            giveUp.restart()
                        }
                    }
                    // station did not take the value: show the real value again
                    Timer { id: giveUp; interval: 4000; onTriggered: lvPill.pending = NaN }

                    MouseArea {
                        id: lvMouse
                        anchors.fill: parent
                        anchors.margins: -3
                        enabled: tile.writable && lvPill.usable
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onDoubleClicked: if (!lvPill.active) tile.ctl.selectLevel(tile.portNo - 1, index)
                        onWheel: (wheel) => {
                            var mods = Qt.ControlModifier | Qt.ShiftModifier
                            if (!lvPill.active || (wheel.modifiers & mods) !== mods) {
                                wheel.accepted = false
                                return
                            }
                            // Shift turns the wheel into horizontal scrolling on some systems
                            var dl = wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : wheel.angleDelta.x
                            acc += dl
                            var steps = Math.trunc(acc / 120)
                            if (steps === 0) return
                            acc -= steps * 120
                            var base = lvPill.busy ? lvPill.pending : Math.round(modelData)
                            var v = Math.round((base + steps * 5) / 5) * 5
                            lvPill.pending = Math.max(tile.tMin, Math.min(tile.tMax, v))
                            giveUp.stop()
                            commit.restart()
                        }
                        property real acc: 0
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                text: "Power"
                color: T.textDim
                font.family: T.font; font.pixelSize: tile.sp * 0.85; font.weight: Font.Light
            }
            Text {
                text: tile.hasTool && tile.d.power !== null ? tile.d.power.toFixed(1) + " %" : "–"
                color: T.cyan
                font.family: T.font; font.pixelSize: tile.sp * 0.95
                Layout.minimumWidth: tile.sp * 3.6
                horizontalAlignment: Text.AlignRight
            }
        }

        // power bar
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            visible: tile.hasTool
            Rectangle {
                Layout.fillWidth: true
                height: Math.max(3, tile.sp * 0.22)
                radius: height / 2
                color: T.grid
                Rectangle {
                    height: parent.height; radius: parent.radius
                    width: parent.width * Math.min(1, (tile.hasTool && tile.d.power ? tile.d.power : 0) / 100)
                    color: (tile.hasTool && tile.d.power > 80) ? T.orange : T.cyan
                    Behavior on width { NumberAnimation { duration: 300 } }
                }
            }
        }

        // history
        Sparkline {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: tile.sp * 3
            values: tile.hasTool && tile.d.hist ? tile.d.hist : []
            setValues: tile.hasTool && tile.d.histSet ? tile.d.histSet : []
            capacity: tile.histLength
            lineColor: tile.tc
            sp: tile.sp
        }
    }

    // offline hint
    Text {
        anchors.centerIn: parent
        visible: !tile.online
        text: "not connected"
        color: T.textLow
        font.family: T.font; font.pixelSize: tile.sp * 1.1; font.weight: Font.Light
    }
}
