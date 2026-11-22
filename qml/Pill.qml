import QtQuick
import "Theme.js" as T

Rectangle {
    id: pill
    property string label: ""
    property color tint: T.cyan
    property bool filled: false
    property bool dim: false
    property real size: 12
    implicitWidth: txt.implicitWidth + size * 1.6
    implicitHeight: txt.implicitHeight + size * 0.7
    radius: height / 2
    color: filled ? T.alpha(tint, 0.22) : T.alpha(tint, 0.06)
    border.width: 1
    border.color: T.alpha(tint, dim ? 0.18 : (filled ? 0.8 : 0.45))
    Behavior on color { ColorAnimation { duration: 250 } }

    Text {
        id: txt
        anchors.centerIn: parent
        text: pill.label
        color: pill.dim ? T.textLow : (pill.filled ? T.text : pill.tint)
        font.family: T.font
        font.pixelSize: pill.size
        font.weight: pill.filled ? Font.Medium : Font.Normal
        font.letterSpacing: 0.8
    }
}
