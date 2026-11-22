.pragma library
// Palette: dark gradient, cool accents, warm warning colours.

var bgTop    = "#1b2029"
var bgMid    = "#12161d"
var bgBottom = "#0b0e13"

var cyan   = "#19d2ff"
var teal   = "#31e0a0"
var green  = "#28c76f"
var lime   = "#8ef94a"
var amber  = "#ffb44a"
var orange = "#ff8a00"
var red    = "#ff5a52"
var violet = "#b58cff"
var yellow = "#ffd166"

var text    = "#e0e0e0"
var textDim = "#8a8a8a"
var textLow = "#6b6f7a"

var panel   = Qt.rgba(1, 1, 1, 0.045)
var panelHi = Qt.rgba(1, 1, 1, 0.09)
var grid    = Qt.rgba(1, 1, 1, 0.07)

var font = "Fira Sans"
var mono = "Fira Mono"

function stateColor(s) {
    if (s === "work")  return orange
    if (s === "stand") return amber
    if (s === "sleep") return violet
    if (s === "hiber") return cyan
    if (s === "error") return red
    return textLow
}

function stateLabel(s) {
    if (s === "work")  return "WORKING"
    if (s === "stand") return "STAND"
    if (s === "sleep") return "SLEEP"
    if (s === "hiber") return "HIBERNATION"
    if (s === "error") return "ERROR"
    return "NO TOOL"
}

// temperature -> colour: cold cyan, warm teal/amber, hot orange, too hot red
function tempColor(t, set) {
    if (t === null || t === undefined || isNaN(t)) return textLow
    if (set && t > set + 25) return red
    if (t < 60)  return cyan
    if (t < 150) return teal
    if (t < 250) return amber
    return orange
}

function alpha(c, a) {
    var q = Qt.color(c)
    return Qt.rgba(q.r, q.g, q.b, a)
}
