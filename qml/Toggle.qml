import QtQuick
import "Theme.js" as T

Rectangle {
    id: tg
    property real sp: 14
    property bool checked: false
    property bool changed: false
    property color tint: T.cyan
    signal toggled(bool v)
    width: sp * 3.2; height: sp * 1.7; radius: height / 2
    opacity: enabled ? 1.0 : 0.4
    color: checked ? T.alpha(tint, 0.30) : T.panel
    border.width: 1
    border.color: changed ? T.amber : T.alpha(tint, checked ? 0.8 : 0.3)
    Behavior on color { ColorAnimation { duration: 150 } }
    Rectangle {
        width: parent.height - 6; height: width; radius: width / 2
        y: 3; x: tg.checked ? parent.width - width - 3 : 3
        color: tg.checked ? tg.tint : T.textLow
        Behavior on x { NumberAnimation { duration: 150 } }
    }
    MouseArea {
        anchors.fill: parent; enabled: tg.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: tg.toggled(!tg.checked)
    }
}
