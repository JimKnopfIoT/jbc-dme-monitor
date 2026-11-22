#!/usr/bin/env python3
"""JBC DME-2A Monitor - desktop GUI (PySide6/QML), read-only.

Usage:
    python3 jbc_gui.py                 # find the station automatically
    python3 jbc_gui.py --port /dev/ttyACM0
    python3 jbc_gui.py --demo          # no station, simulated data
    python3 jbc_gui.py --demo --screenshot shot.png
"""
import argparse
import math
import os
import random
import sys
import time

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (wrapper for grabWindow)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jbc_dme  # noqa: E402

HIST_SECONDS = 180
POLL_INTERVAL = 0.5


class Worker(QThread):
    connectedChanged = Signal(bool, str, dict)
    data = Signal(list)

    def __init__(self, port=None, demo=False):
        super().__init__()
        self.port = port
        self.demo = demo
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        if self.demo:
            self._run_demo()
            return
        while not self._stop:
            dme = jbc_dme.DME(self.port)
            try:
                info = dme.connect()
                self.connectedChanged.emit(True, "connected", info)
                while not self._stop:
                    t0 = time.monotonic()
                    self.data.emit(dme.read_all())
                    time.sleep(max(0.0, POLL_INTERVAL - (time.monotonic() - t0)))
            except (OSError, jbc_dme.StationError) as e:
                self.connectedChanged.emit(False, str(e), {})
            finally:
                dme.close()
            for _ in range(20):
                if self._stop:
                    break
                time.sleep(0.1)

    def _run_demo(self):
        self.connectedChanged.emit(True, "Demo", {
            "protocol": "02", "model": "DME_TCH_04", "sw": "8886937",
            "hw": "0012408C", "port": "demo"})
        sim = [
            {"tool": "T210", "id": 1, "levels": [270, 370, 450], "lvl": 1, "temp": 120.0, "state": "work"},
            {"tool": "T245", "id": 2, "levels": [220, 370, 450], "lvl": 0, "temp": 200.0, "state": "sleep"},
            {"tool": "PA", "id": 3, "levels": [220, 370, 430], "lvl": 0, "temp": 30.0, "state": "hiber"},
            {"tool": "DT530", "id": 10, "levels": [270, 380, 450], "lvl": 1, "temp": 320.0, "state": "stand"},
        ]
        t = 0
        while not self._stop:
            t += 1
            out = []
            for i, s in enumerate(sim):
                target = {"work": s["levels"][s["lvl"]], "stand": 300, "sleep": 200,
                          "hiber": 25}[s["state"]]
                d = target - s["temp"]
                s["temp"] += d * (0.08 if d > 0 else 0.03) + random.uniform(-1.2, 1.2)
                pw = max(0.0, min(100.0, d * 1.5 + 8 + 4 * math.sin(t / 3))) if s["state"] == "work" else 0.0
                st = {"work": 0, "stand": 8, "sleep": 2, "hiber": 4}[s["state"]]
                out.append({"port": i + 1, "tool_id": s["id"], "tool": s["tool"], "error": 0,
                            "status": st, "state": s["state"], "temp": s["temp"],
                            "set": float(s["levels"][s["lvl"]]), "power": pw,
                            "levels": [float(x) for x in s["levels"]], "level": s["lvl"]})
            if t == 40:
                sim[1]["state"] = "work"
            self.data.emit(out)
            time.sleep(POLL_INTERVAL)


class Station(QObject):
    changed = Signal()

    def __init__(self, port=None, demo=False):
        super().__init__()
        self._connected = False
        self._message = "looking for station …"
        self._info = {}
        self._ports = []
        self._hist = [[] for _ in range(4)]
        self._last = 0.0
        self._worker = Worker(port, demo)
        self._worker.connectedChanged.connect(self._on_conn)
        self._worker.data.connect(self._on_data)
        self._worker.start()

    def shutdown(self):
        self._worker.stop()
        self._worker.wait(3000)

    @Slot(bool, str, dict)
    def _on_conn(self, ok, msg, info):
        self._connected = ok
        self._message = msg
        if ok:
            self._info = info
        else:
            self._ports = []
        self.changed.emit()

    @Slot(list)
    def _on_data(self, ports):
        now = time.time()
        self._last = now
        n = int(HIST_SECONDS / POLL_INTERVAL)
        for p in ports:
            h = self._hist[p["port"] - 1]
            h.append([p["temp"] if p["temp"] is not None else float("nan"),
                      p["set"] if p["set"] is not None else float("nan")])
            del h[:-n]
            p["hist"] = [x[0] for x in h]
            p["histSet"] = [x[1] for x in h]
        self._ports = ports
        self.changed.emit()

    @Property(bool, notify=changed)
    def connected(self):
        return self._connected

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Property("QVariantMap", notify=changed)
    def info(self):
        return self._info

    @Property("QVariantList", notify=changed)
    def ports(self):
        return self._ports

    @Property(int, constant=True)
    def histLength(self):
        return int(HIST_SECONDS / POLL_INTERVAL)

    @Property(int, constant=True)
    def histSeconds(self):
        return HIST_SECONDS


def main():
    ap = argparse.ArgumentParser(description="JBC DME-2A Monitor (read-only)")
    ap.add_argument("--port")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--screenshot")
    ap.add_argument("--delay", type=float, default=8.0)
    ap.add_argument("--size", default="1280x800")
    args = ap.parse_args()

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("JBC DME Monitor")
    app.setWindowIcon(QIcon(os.path.join(HERE, "qml", "icon.svg")))

    station = Station(args.port, args.demo)
    engine = QQmlApplicationEngine()
    w, h = (int(x) for x in args.size.split("x"))
    engine.setInitialProperties({"station": station, "width": w, "height": h})
    engine.load(QUrl.fromLocalFile(os.path.join(HERE, "qml", "Main.qml")))
    if not engine.rootObjects():
        station.shutdown()
        return 1
    win = engine.rootObjects()[0]

    if args.screenshot:
        def shot():
            try:
                win.grabWindow().save(args.screenshot)
            finally:
                app.quit()
        QTimer.singleShot(int(args.delay * 1000), shot)

    rc = app.exec()
    station.shutdown()
    return rc


if __name__ == "__main__":
    sys.exit(main())
