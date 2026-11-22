import QtQuick
import "Theme.js" as T

// Glow-LED wie im PM5-Header
Item {
    id: led
    property bool on: false
    property real size: 48
    readonly property color c: on ? T.green : T.red
    width: size; height: size

    Rectangle {           // aeusserer Hof
        anchors.centerIn: parent
        width: led.size * 1.5; height: width; radius: width / 2
        color: T.alpha(led.c, 0.06)
        SequentialAnimation on opacity {
            running: led.on; loops: Animation.Infinite
            NumberAnimation { to: 0.35; duration: 1400; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.0;  duration: 1400; easing.type: Easing.InOutSine }
        }
    }
    Rectangle {           // Ring
        anchors.fill: parent
        radius: width / 2
        color: "transparent"
        border.width: Math.max(2, led.size * 0.05)
        border.color: T.alpha(led.c, 0.45)
    }
    Rectangle {           // Glow
        anchors.centerIn: parent
        width: led.size * 0.62; height: width; radius: width / 2
        color: T.alpha(led.c, 0.25)
    }
    Rectangle {           // Kern
        anchors.centerIn: parent
        width: led.size * 0.42; height: width; radius: width / 2
        color: led.c
    }
}
