import QtQuick
import "Theme.js" as T

// − value + ; also mouse wheel. Either a numeric range or a list of values.
Row {
    id: st
    property real sp: 14
    property var value: 0
    property real from: 0
    property real to: 100
    property real step: 1
    property var values: null           // list of allowed values instead of a range
    property var fmt: function (v) { return String(v) }
    property bool changed: false        // differs from the station
    signal moved(var v)
    spacing: sp * 0.3
    opacity: enabled ? 1.0 : 0.4

    function shift(n) {
        if (!enabled) return
        var v
        if (values) {
            var i = values.indexOf(value)
            v = values[Math.max(0, Math.min(values.length - 1, (i < 0 ? 0 : i) + n))]
        } else {
            v = Math.round((Number(value) + n * step) / step) * step
            v = Math.max(from, Math.min(to, v))
        }
        if (v !== value) moved(v)
    }

    component Btn: Rectangle {
        property string sym
        property int dir
        width: st.sp * 1.9; height: width; radius: width / 2
        color: m.pressed ? T.alpha(T.cyan, 0.25) : (m.containsMouse ? T.alpha(T.cyan, 0.12) : T.panel)
        border.width: 1; border.color: T.alpha(T.cyan, 0.35)
        Text {
            anchors.centerIn: parent; text: parent.sym; color: T.cyan
            font.family: T.font; font.pixelSize: st.sp * 1.1
        }
        MouseArea {
            id: m; anchors.fill: parent; hoverEnabled: true
            readonly property int dir: parent.dir
            enabled: st.enabled
            cursorShape: Qt.PointingHandCursor
            onClicked: st.shift(m.dir)
            onPressAndHold: rep.start()
            onReleased: rep.stop()
            Timer { id: rep; interval: 90; repeat: true; onTriggered: st.shift(m.dir) }
        }
    }

    Btn { sym: "−"; dir: -1 }
    Rectangle {
        width: st.sp * 6; height: st.sp * 1.9; radius: height / 2
        color: st.changed ? T.alpha(T.amber, 0.14) : "transparent"
        border.width: 1; border.color: st.changed ? T.alpha(T.amber, 0.7) : T.grid
        Text {
            anchors.centerIn: parent
            text: st.value === null || st.value === undefined ? "–" : st.fmt(st.value)
            color: st.changed ? T.amber : T.text
            font.family: T.font; font.pixelSize: st.sp * 1.0
        }
        MouseArea {
            anchors.fill: parent
            onWheel: (w) => { st.shift(w.angleDelta.y > 0 || w.angleDelta.x > 0 ? 1 : -1) }
        }
    }
    Btn { sym: "+"; dir: 1 }
}
