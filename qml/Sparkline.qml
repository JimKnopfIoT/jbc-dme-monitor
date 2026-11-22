import QtQuick
import "Theme.js" as T

// Temperaturverlauf: Flaeche + Linie, Soll gestrichelt, feine Rasterlinien
Canvas {
    id: cv
    property var values: []
    property var setValues: []
    property int capacity: 360
    property color lineColor: T.cyan
    property real sp: 14
    property real vmin: 0
    property real vmax: 500

    onValuesChanged: requestPaint()
    onLineColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        var w = width, h = height
        if (w <= 0 || h <= 0) return
        var lab = Math.max(9, sp * 0.7)
        var x0 = lab * 3.2
        var pw = w - x0, ph = h - 2

        function y(v) { return 1 + ph - (Math.max(vmin, Math.min(vmax, v)) - vmin) / (vmax - vmin) * ph }
        function x(i, n) { return x0 + pw - (n - 1 - i) * pw / (capacity - 1) }

        // Raster 100/200/300/400
        ctx.font = lab + "px '" + T.font + "'"
        ctx.textAlign = "right"
        ctx.textBaseline = "middle"
        var step = ph < lab * 7 ? 200 : 100
        for (var g = step; g < vmax; g += step) {
            ctx.strokeStyle = T.grid
            ctx.lineWidth = 1
            ctx.beginPath(); ctx.moveTo(x0, y(g)); ctx.lineTo(w, y(g)); ctx.stroke()
            ctx.fillStyle = T.textLow
            ctx.fillText(g + "°", x0 - lab * 0.5, y(g))
        }

        var n = values.length
        if (n < 2) return

        // Soll gestrichelt
        ctx.strokeStyle = T.alpha(T.text, 0.35)
        ctx.lineWidth = 1
        ctx.setLineDash ? ctx.setLineDash([4, 4]) : null
        ctx.beginPath()
        var pen = false
        for (var i = 0; i < setValues.length; ++i) {
            var s = setValues[i]
            if (s === null || isNaN(s)) { pen = false; continue }
            var xs = x(i, setValues.length)
            if (!pen) { ctx.moveTo(xs, y(s)); pen = true } else ctx.lineTo(xs, y(s))
        }
        ctx.stroke()
        ctx.setLineDash ? ctx.setLineDash([]) : null

        // Flaeche
        var grad = ctx.createLinearGradient(0, 0, 0, h)
        grad.addColorStop(0, T.alpha(lineColor, 0.28))
        grad.addColorStop(1, T.alpha(lineColor, 0.0))
        ctx.fillStyle = grad
        ctx.beginPath()
        var first = -1, last = -1
        for (i = 0; i < n; ++i) {
            var v = values[i]
            if (v === null || isNaN(v)) continue
            if (first < 0) { first = i; ctx.moveTo(x(i, n), h) }
            ctx.lineTo(x(i, n), y(v))
            last = i
        }
        if (first >= 0) { ctx.lineTo(x(last, n), h); ctx.closePath(); ctx.fill() }

        // Linie
        ctx.strokeStyle = lineColor
        ctx.lineWidth = Math.max(1.5, sp * 0.12)
        ctx.lineJoin = "round"
        ctx.beginPath()
        pen = false
        for (i = 0; i < n; ++i) {
            v = values[i]
            if (v === null || isNaN(v)) { pen = false; continue }
            if (!pen) { ctx.moveTo(x(i, n), y(v)); pen = true } else ctx.lineTo(x(i, n), y(v))
        }
        ctx.stroke()

        // Endpunkt
        if (last >= 0) {
            ctx.fillStyle = lineColor
            ctx.beginPath()
            ctx.arc(x(last, n), y(values[last]), Math.max(2.5, sp * 0.2), 0, 2 * Math.PI)
            ctx.fill()
        }
    }
}
