import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import "Theme.js" as T

// Overlay with all settings of the station menu that the USB protocol offers.
// Changes are collected in `edit` and written together with APPLY.
Item {
    id: panel
    property var ctl: null
    property real sp: 14
    property bool open: false
    readonly property bool writable: ctl !== null && ctl.writable
    readonly property bool busy: ctl !== null && ctl.settingsBusy
    readonly property bool editable: writable && !busy && !waiting
    readonly property var src: ctl ? ctl.settings : ({})
    readonly property bool loaded: !!src && src.station !== undefined && src.station !== null

    property var orig: null
    property var edit: null
    property int rev: 0                 // bumped on every edit, bindings read it
    property int tab: 0                 // 0 = station, 1..4 = ports
    property bool waiting: false

    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 160 } }

    function show() {
        open = true
        waiting = true
        forceActiveFocus()
        ctl.loadSettings()
    }
    function close() { open = false }

    onSrcChanged: {
        waiting = false
        // do not use `loaded` here, its binding may not be updated yet
        if (!src || !src.station) return
        orig = JSON.parse(JSON.stringify(src))
        edit = JSON.parse(JSON.stringify(src))
        rev++
    }

    // -- edit helpers ----------------------------------------------------
    function at(obj, path) {
        var o = obj
        for (var i = 0; i < path.length && o !== null && o !== undefined; ++i) o = o[path[i]]
        return o
    }
    function val(path) { rev; return edit ? at(edit, path) : null }
    function dirty(path) {
        rev
        return edit !== null && orig !== null
               && JSON.stringify(at(edit, path)) !== JSON.stringify(at(orig, path))
    }
    function put(path, v) {
        if (!edit || !editable) return
        var o = edit
        for (var i = 0; i < path.length - 1; ++i) o = o[path[i]]
        o[path[path.length - 1]] = v
        rev++
    }
    function countDiff(a, b) {
        if (a === null || b === null || typeof a !== "object" || typeof b !== "object")
            return JSON.stringify(a) === JSON.stringify(b) ? 0 : 1
        var n = 0
        for (var k in a) n += countDiff(a[k], b[k])
        return n
    }
    readonly property int changes: { rev; return edit && orig ? countDiff(edit, orig) : 0 }
    readonly property int tMin: { rev; return val(["station", "min_temp"]) || 90 }
    readonly property int tMax: { rev; return val(["station", "max_temp"]) || 450 }

    function degC(v) { return v + " °C" }
    function minutes(v) { return qsTr("%1 min").arg(v) }

    Keys.onEscapePressed: close()

    // dim background, click outside closes
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.55)
        MouseArea { anchors.fill: parent; onClicked: panel.close(); onWheel: {} }
    }

    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(parent.width - panel.sp * 2, panel.sp * 56)
        height: Math.min(parent.height - panel.sp * 2, panel.sp * 40)
        radius: panel.sp * 1.3
        color: T.bgMid
        border.width: 1
        border.color: T.alpha(T.cyan, 0.3)
        MouseArea { anchors.fill: parent; onWheel: {} }     // keep clicks inside

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: panel.sp * 1.4
            spacing: panel.sp * 0.9

            // ---- head -------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: panel.sp * 0.8
                Text {
                    text: qsTr("Settings")
                    color: T.text
                    font.family: T.font; font.pixelSize: panel.sp * 1.8; font.weight: Font.Light
                }
                Text {
                    text: panel.writable ? qsTr("written to the station only with APPLY")
                                         : qsTr("read-only (started with --readonly)")
                    color: T.textLow
                    font.family: T.font; font.pixelSize: panel.sp * 0.85
                    Layout.alignment: Qt.AlignBottom
                    Layout.bottomMargin: panel.sp * 0.25
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "✕"
                    color: closeMouse.containsMouse ? T.text : T.textDim
                    font.pixelSize: panel.sp * 1.4
                    MouseArea {
                        id: closeMouse; anchors.fill: parent; anchors.margins: -8
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: panel.close()
                    }
                }
            }

            // ---- tabs -------------------------------------------------
            Flow {
                Layout.fillWidth: true
                spacing: panel.sp * 0.5
                Repeater {
                    model: 5
                    Pill {
                        readonly property var pd: index > 0 && panel.loaded ? panel.src.ports[index - 1] : null
                        label: index === 0 ? qsTr("STATION")
                               : "P" + index + (pd && pd.tool ? "  " + pd.tool : "")
                        tint: T.cyan
                        filled: panel.tab === index
                        dim: index > 0 && !(pd && pd.tool)
                        size: panel.sp * 0.85
                        clickable: true
                        onClicked: panel.tab = index
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: T.grid }

            // ---- content ----------------------------------------------
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Text {
                    anchors.centerIn: parent
                    visible: !panel.loaded || panel.waiting
                    text: panel.ctl && !panel.ctl.connected ? qsTr("station not connected") : qsTr("reading settings …")
                    color: T.textDim
                    font.family: T.font; font.pixelSize: panel.sp * 1.1; font.weight: Font.Light
                }

                Flickable {
                    id: flick
                    anchors.fill: parent
                    visible: panel.loaded && !panel.waiting && panel.edit !== null
                    contentHeight: page.height
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    Loader {
                        id: page
                        width: flick.width
                        sourceComponent: panel.tab === 0 ? stationPage : portPage
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: T.grid }

            // ---- foot -------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: panel.sp * 0.8
                Text {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    text: panel.busy ? qsTr("writing … (control mode, takes a few seconds)")
                          : panel.changes > 0 ? qsTr("%n value(s) changed, not written yet", "", panel.changes)
                          : qsTr("no changes")
                    color: panel.busy ? T.amber : (panel.changes > 0 ? T.amber : T.textLow)
                    font.family: T.font; font.pixelSize: panel.sp * 0.9
                }
                Pill {
                    label: qsTr("SAVE …")
                    tint: T.cyan
                    size: panel.sp * 0.85
                    clickable: panel.orig !== null && !panel.busy
                    dim: !clickable
                    onClicked: saveDialog.open()
                }
                Pill {
                    label: qsTr("LOAD …")
                    tint: T.cyan
                    size: panel.sp * 0.85
                    clickable: panel.edit !== null && panel.editable
                    dim: !clickable
                    onClicked: loadDialog.open()
                }
                Pill {
                    label: qsTr("RELOAD")
                    tint: T.cyan
                    size: panel.sp * 0.85
                    clickable: !panel.busy
                    dim: panel.busy
                    onClicked: { panel.waiting = true; panel.ctl.loadSettings() }
                }
                Pill {
                    label: qsTr("UNDO")
                    tint: T.cyan
                    size: panel.sp * 0.85
                    visible: panel.changes > 0 && !panel.busy
                    clickable: true
                    onClicked: { panel.edit = JSON.parse(JSON.stringify(panel.orig)); panel.rev++ }
                }
                Pill {
                    label: panel.changes > 0 ? qsTr("APPLY") + " " + panel.changes : qsTr("APPLY")
                    tint: T.amber
                    filled: panel.changes > 0
                    dim: !panel.writable || panel.changes === 0 || panel.busy
                    size: panel.sp * 0.85
                    clickable: panel.writable && panel.changes > 0 && !panel.busy
                    onClicked: panel.ctl.applySettings(panel.edit)
                }
            }
        }
    }

    // ---- settings files (format shared with the iSoSta phone app) ----------
    // SAVE writes what the station reported (not unapplied edits). LOAD only
    // fills the form; APPLY writes it.
    FileDialog {
        id: saveDialog
        title: qsTr("Save station settings")
        fileMode: FileDialog.SaveFile
        nameFilters: [qsTr("iSoSta settings (*.json)"), qsTr("All files (*)")]
        defaultSuffix: "json"
        currentFolder: panel.ctl ? panel.ctl.settingsFolder : ""
        selectedFile: {
            var st = panel.orig && panel.orig.station ? panel.orig.station : {}
            var base = (st.name || (panel.ctl && panel.ctl.info.model) || "DME-2A")
                       + " " + Qt.formatDate(new Date(), "yyyy-MM-dd")
            return currentFolder + "/" + base.replace(/[\/\\:*?"<>|]/g, "_") + ".json"
        }
        onAccepted: panel.ctl.saveSettingsFile(selectedFile, panel.orig)
    }
    FileDialog {
        id: loadDialog
        title: qsTr("Load station settings")
        fileMode: FileDialog.OpenFile
        nameFilters: [qsTr("iSoSta settings (*.json)"), qsTr("All files (*)")]
        currentFolder: panel.ctl ? panel.ctl.settingsFolder : ""
        onAccepted: {
            var r = panel.ctl.loadSettingsFile(selectedFile, panel.orig)
            if (!r || !r.settings) return
            // keep unapplied edits out of it: the file is merged into the station's values
            panel.edit = r.settings
            panel.rev++
        }
    }

    // ---- building blocks --------------------------------------------------
    component Label: Text {
        color: T.textDim
        font.family: T.font; font.pixelSize: panel.sp * 0.95; font.weight: Font.Light
        Layout.preferredWidth: panel.sp * 13
    }
    component Hint: Text {
        Layout.leftMargin: panel.sp * 0.5
        color: T.textLow
        font.family: T.font; font.pixelSize: panel.sp * 0.8; font.weight: Font.Light
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
    }
    component Head: Text {
        color: T.cyan
        font.family: T.font; font.pixelSize: panel.sp * 1.0; font.letterSpacing: 1
        Layout.topMargin: panel.sp * 0.6
    }
    component TempStep: Stepper {
        property var path: []
        sp: panel.sp
        value: panel.val(path)
        from: panel.tMin; to: panel.tMax; step: 5
        fmt: panel.degC
        changed: panel.dirty(path)
        enabled: panel.editable && value !== null && value !== undefined
        onMoved: (v) => panel.put(path, v)
    }
    component Switch: Toggle {
        property var path: []
        sp: panel.sp
        checked: panel.val(path) === true
        changed: panel.dirty(path)
        enabled: panel.editable && panel.val(path) !== null && panel.val(path) !== undefined
        onToggled: (v) => panel.put(path, v)
    }
    component Field: Rectangle {
        id: fld
        property var path: []
        property int maxLength: 16
        property string mask: ""
        width: panel.sp * 13; height: panel.sp * 1.9; radius: height / 2
        color: T.panel
        border.width: 1
        border.color: panel.dirty(path) ? T.amber : (inp.activeFocus ? T.cyan : T.grid)
        TextInput {
            id: inp
            anchors.fill: parent
            anchors.leftMargin: panel.sp * 0.8; anchors.rightMargin: panel.sp * 0.8
            verticalAlignment: TextInput.AlignVCenter
            text: { var v = panel.val(fld.path); return v === null || v === undefined ? "" : v }
            readOnly: !panel.editable
            maximumLength: fld.maxLength
            inputMask: fld.mask
            color: panel.dirty(fld.path) ? T.amber : T.text
            selectionColor: T.alpha(T.cyan, 0.4)
            font.family: T.font; font.pixelSize: panel.sp * 1.0
            clip: true
            onTextEdited: panel.put(fld.path, text)
            Keys.onEscapePressed: panel.close()
        }
    }

    // ---- station page ------------------------------------------------------
    Component {
        id: stationPage
        ColumnLayout {
            spacing: panel.sp * 0.55
            Head { text: qsTr("STATION") }
            RowLayout {
                Label { text: qsTr("Name") }
                Field { path: ["station", "name"]; maxLength: 16 }
                Hint { text: qsTr("max. 16 characters") }
            }
            RowLayout {
                Label { text: qsTr("Min. temperature") }
                TempStep { path: ["station", "min_temp"]; from: 90; to: panel.tMax }
                Hint { text: qsTr("lower limit for all set points") }
            }
            RowLayout {
                Label { text: qsTr("Max. temperature") }
                TempStep { path: ["station", "max_temp"]; from: panel.tMin; to: 450 }
                Hint { text: qsTr("upper limit for all set points") }
            }
            RowLayout {
                // the DME-2A does not answer 170
                visible: { var v = panel.val(["station", "power_limit"]); return v !== null && v !== undefined }
                Label { text: qsTr("Power limit") }
                Stepper {
                    readonly property var path: ["station", "power_limit"]
                    sp: panel.sp
                    value: panel.val(path)
                    from: 30; to: 160; step: 10
                    fmt: function (v) { return v + " W" }
                    changed: panel.dirty(path)
                    enabled: panel.editable && value !== null && value !== undefined
                    onMoved: (v) => panel.put(path, v)
                }
                Hint { text: qsTr("30 … 160 W") }
            }
            Head { text: qsTr("PIN") }
            RowLayout {
                Label { text: qsTr("PIN lock") }
                Switch { path: ["station", "pin_enabled"] }
                Hint { text: qsTr("the station menu asks for the PIN (default 0105)") }
            }
            RowLayout {
                // the DME-2A reports the PIN as four spaces
                visible: { var v = panel.val(["station", "pin"]); return v !== null && v !== undefined }
                Label { text: qsTr("PIN") }
                Field { path: ["station", "pin"]; maxLength: 4; mask: "9999" }
                Hint { text: qsTr("4 digits") }
            }
            Head { text: qsTr("INFO") }
            RowLayout {
                Label { text: qsTr("Transformer temperature") }
                Text {
                    text: { var v = panel.val(["station", "trafo_temp"]); return v === null || v === undefined ? "–" : v + " °C" }
                    color: T.text; font.family: T.font; font.pixelSize: panel.sp * 0.95
                }
            }
            RowLayout {
                Label { text: qsTr("Station error") }
                Text {
                    text: { var v = panel.val(["station", "error"]); return v === null || v === undefined ? "–" : (v === 0 ? qsTr("none") : qsTr("code %1").arg(v)) }
                    color: T.text; font.family: T.font; font.pixelSize: panel.sp * 0.95
                }
            }
            RowLayout {
                visible: !!panel.val(["station", "uuid"])
                Label { text: qsTr("Device ID") }
                Text {
                    text: panel.val(["station", "uuid"]) || "–"
                    color: T.textDim; font.family: T.mono; font.pixelSize: panel.sp * 0.85
                    Layout.fillWidth: true; elide: Text.ElideRight
                }
            }
            Hint {
                Layout.topMargin: panel.sp * 0.6
                text: qsTr("Language, units, display and robot settings exist only in the station menu; "
                      + "the USB protocol of the DME offers no command for them.")
            }
        }
    }

    // ---- port page -----------------------------------------------------------
    Component {
        id: portPage
        ColumnLayout {
            id: pp
            spacing: panel.sp * 0.55
            readonly property int pi: panel.tab - 1
            readonly property var base: ["ports", pi]
            readonly property bool hasTool: { panel.rev; var t = panel.val(base.concat(["tool_id"])); return t > 0 }
            function q(k) { return base.concat(k) }

            Head { text: qsTr("PORT %1").arg(panel.tab) + (pp.hasTool ? "  ·  " + panel.val(pp.q(["tool"])) : "") }
            RowLayout {
                Label { text: qsTr("Port locked") }
                Switch { path: pp.q(["locked"]); tint: T.red }
                Hint { text: qsTr("a locked port does not heat") }
            }
            RowLayout {
                Label { text: qsTr("Set temperature") }
                TempStep { path: pp.q(["set_temp"]) }
                Hint { text: qsTr("applies when levels are off") }
            }

            Hint {
                visible: !pp.hasTool
                Layout.topMargin: panel.sp
                text: qsTr("No tool in this port. Levels, sleep, hibernation and adjust are stored "
                      + "per tool type; plug in the tool to edit them.")
            }

            Head { visible: pp.hasTool; text: qsTr("LEVELS") }
            RowLayout {
                visible: pp.hasTool
                Label { text: qsTr("Levels") }
                Switch { path: pp.q(["levels_on"]) }
                Hint { text: qsTr("choose the active level with the dot") }
            }
            Repeater {
                model: pp.hasTool ? 3 : 0
                RowLayout {
                    readonly property var lvPath: pp.q(["levels", index])
                    readonly property bool active: panel.val(pp.q(["level"])) === index
                    Label { text: qsTr("Level %1").arg(index + 1) }
                    Switch { path: lvPath.concat(["on"]) }
                    TempStep { path: lvPath.concat(["temp"]) }
                    Rectangle {
                        width: panel.sp * 1.5; height: width; radius: width / 2
                        color: active ? T.alpha(T.orange, 0.9) : "transparent"
                        border.width: 1
                        border.color: panel.dirty(pp.q(["level"])) && active ? T.amber : T.alpha(T.orange, 0.6)
                        MouseArea {
                            anchors.fill: parent; anchors.margins: -4
                            enabled: panel.editable && panel.val(lvPath.concat(["on"])) === true
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: panel.put(pp.q(["level"]), index)
                        }
                    }
                    Hint { text: active ? qsTr("active") : "" }
                }
            }

            Head { visible: pp.hasTool; text: qsTr("SLEEP / HIBERNATION") }
            RowLayout {
                visible: pp.hasTool
                Label { text: qsTr("Sleep temperature") }
                TempStep { path: pp.q(["sleep_temp"]); from: 90 }
            }
            RowLayout {
                visible: pp.hasTool
                Label { text: qsTr("Sleep delay") }
                Switch { path: pp.q(["sleep_on"]) }
                Stepper {
                    readonly property var path: pp.q(["sleep_min"])
                    sp: panel.sp
                    value: { var v = panel.val(path); return v === null || v === undefined ? 0 : v }
                    values: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
                    fmt: panel.minutes
                    changed: panel.dirty(path)
                    enabled: panel.editable && panel.val(pp.q(["sleep_on"])) === true
                    onMoved: (v) => panel.put(path, v)
                }
                Hint { text: qsTr("tool in the stand → sleep") }
            }
            RowLayout {
                visible: pp.hasTool
                Label { text: qsTr("Hibernation delay") }
                Switch { path: pp.q(["hiber_on"]) }
                Stepper {
                    readonly property var path: pp.q(["hiber_min"])
                    sp: panel.sp
                    value: { var v = panel.val(path); return v === null || v === undefined ? 0 : v }
                    values: [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
                    fmt: panel.minutes
                    changed: panel.dirty(path)
                    enabled: panel.editable && panel.val(pp.q(["hiber_on"])) === true
                    onMoved: (v) => panel.put(path, v)
                }
                Hint { text: qsTr("sleep → heater off") }
            }

            Head { visible: pp.hasTool; text: qsTr("CALIBRATION") }
            RowLayout {
                visible: pp.hasTool
                Label { text: qsTr("Temperature adjust") }
                Stepper {
                    readonly property var path: pp.q(["adjust"])
                    sp: panel.sp
                    value: panel.val(path)
                    from: -50; to: 50; step: 1
                    fmt: function (v) { return (v > 0 ? "+" : "") + v + " °C" }
                    changed: panel.dirty(path)
                    enabled: panel.editable && value !== null && value !== undefined
                    onMoved: (v) => panel.put(path, v)
                }
                Hint { text: qsTr("offset for this tool, ±50 °C") }
            }
        }
    }
}
