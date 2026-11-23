#!/usr/bin/env python3
"""JBC DME-2A Monitor - desktop GUI (PySide6/QML).

Usage:
    python3 jbc_gui.py                 # find the station automatically
    python3 jbc_gui.py --port /dev/ttyACM0
    python3 jbc_gui.py --readonly      # never write to the station
    python3 jbc_gui.py --demo          # no station, simulated data
    python3 jbc_gui.py --demo --screenshot shot.png
    python3 jbc_gui.py --lang de       # German (EN | DE top right, remembered)

Temperature levels (only without --readonly):
    double click on a level           -> make it the active level
    Ctrl+Shift+wheel on active level  -> change its temperature in 5 °C steps

SETTINGS (top right) opens all station and tool settings the station menu
offers. Changes are collected and written together with APPLY. SAVE/LOAD keep
them in a file (format shared with the iSoSta phone app, see settings_file.py).
"""
import copy
import argparse
import math
import os
import queue
import random
import sys
import time

from PySide6.QtCore import (QCoreApplication, QLocale, QObject, QSettings, QThread, QTimer,
                            QTranslator, QUrl, Property, Signal, Slot)
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (wrapper for grabWindow)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jbc_dme  # noqa: E402
import settings_file  # noqa: E402

I18N = os.path.join(HERE, "i18n")
LANGUAGES = ("en", "de")


def tr(text, n=-1):
    """Translate a GUI message (context "jbc_gui", German in i18n/jbc-gui_de.qm)."""
    return QCoreApplication.translate("jbc_gui", text, None, n)


HIST_SECONDS = 180
POLL_INTERVAL = 0.5


class Worker(QThread):
    connectedChanged = Signal(bool, str, dict)
    data = Signal(list)
    notice = Signal(bool, str)      # ok, text
    settings = Signal(dict)
    busy = Signal(bool)

    def __init__(self, port=None, demo=False, write=False, control=False):
        super().__init__()
        self.port = port
        self.demo = demo
        self.write = write
        self.control = control
        self._stop = False
        self._cmds = queue.Queue()

    def stop(self):
        self._stop = True

    def submit(self, *cmd):
        """Queue a write command, executed in the worker thread between polls."""
        self._cmds.put(cmd)

    def _do_cmds(self, dme):
        while True:
            try:
                cmd = self._cmds.get_nowait()
            except queue.Empty:
                return
            try:
                if cmd[0] == "settings":
                    self.settings.emit(dme.read_settings())
                    continue
                if cmd[0] == "apply":
                    self.busy.emit(True)
                    try:
                        back, done, errors = dme.apply_settings(cmd[1])
                    finally:
                        self.busy.emit(False)
                    self.settings.emit(back)
                    if errors:
                        self.notice.emit(False, "; ".join(errors))
                    else:
                        self.notice.emit(True, tr("%n setting(s) written", len(done))
                                         if done else tr("nothing to write"))
                    continue
                if cmd[0] == "select":
                    _, p, lvl = cmd
                    dme.select_level(p, lvl)
                    self.notice.emit(True, tr("P%1: level %2 active").replace("%1", str(p + 1))
                                     .replace("%2", str(lvl + 1)))
                elif cmd[0] == "temp":
                    _, p, lvl, c = cmd
                    c = dme.set_level_temp(p, lvl, c)
                    self.notice.emit(True, tr("P%1: level %2 = %3 °C").replace("%1", str(p + 1))
                                     .replace("%2", str(lvl + 1)).replace("%3", str(c)))
            except (ValueError, jbc_dme.StationError) as e:
                self.notice.emit(False, str(e))
                if cmd[0] in ("settings", "apply"):
                    self.settings.emit({})

    def run(self):
        if self.demo:
            self._run_demo()
            return
        while not self._stop:
            dme = jbc_dme.DME(self.port, allow_write=self.write, control=self.control)
            try:
                info = dme.connect()
                self.connectedChanged.emit(True, "connected", info)
                while not self._stop:
                    t0 = time.monotonic()
                    self._do_cmds(dme)
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
            "hw": "0012408C", "port": "demo", "min_temp": 90, "max_temp": 450})
        sim = [
            {"tool": "T210", "id": 1, "levels": [270, 370, 450], "lvl": 1, "temp": 120.0, "state": "work"},
            {"tool": "T245", "id": 2, "levels": [220, 370, 450], "lvl": 0, "temp": 200.0, "state": "sleep"},
            {"tool": "PA", "id": 3, "levels": [220, 370, 430], "lvl": 0, "temp": 30.0, "state": "hiber"},
            {"tool": "DT530", "id": 10, "levels": [270, 380, 450], "lvl": 1, "temp": 320.0, "state": "stand"},
        ]
        cfg = {"station": {"name": "DME-2A", "min_temp": 90, "max_temp": 450, "power_limit": 160,
                           "pin_enabled": False, "pin": "0105", "uuid": "demo", "trafo_temp": 41,
                           "error": 0},
               "ports": [{"port": i + 1, "tool_id": s["id"], "tool": s["tool"], "locked": False,
                          "set_temp": 350, "levels_on": True, "level": s["lvl"],
                          "levels": [{"on": True, "temp": x} for x in s["levels"]],
                          "sleep_temp": 200, "sleep_on": True, "sleep_min": 3,
                          "hiber_on": True, "hiber_min": 30, "adjust": 0}
                         for i, s in enumerate(sim)]}

        def sync_cfg():
            for c, s in zip(cfg["ports"], sim):
                c["level"] = s["lvl"]
                for L, x in zip(c["levels"], s["levels"]):
                    L["temp"] = x

        t = 0
        while not self._stop:
            t += 1
            while not self._cmds.empty():
                cmd = self._cmds.get_nowait()
                if cmd[0] == "settings":
                    sync_cfg()
                    self.settings.emit(copy.deepcopy(cfg))
                    continue
                if cmd[0] == "apply":
                    sync_cfg()
                    try:
                        plan = jbc_dme.DME(None, allow_write=True).plan_settings(cfg, cmd[1])
                    except jbc_dme.StationError as e:
                        self.notice.emit(False, str(e))
                        self.settings.emit(copy.deepcopy(cfg))
                        continue
                    self.busy.emit(True)
                    time.sleep(1.5)
                    self.busy.emit(False)
                    new = copy.deepcopy(cmd[1])
                    for c, n, s in zip(cfg["ports"], new["ports"], sim):
                        if n.get("tool_id") != c["tool_id"]:
                            continue
                        c.update(n)
                        s["lvl"] = n["level"] if n["level"] is not None else s["lvl"]
                        s["levels"] = [L["temp"] for L in n["levels"]]
                    cfg["station"].update(new["station"])
                    self.settings.emit(copy.deepcopy(cfg))
                    self.notice.emit(True, tr("%n setting(s) written (demo)", len(plan)))
                    continue
                s = sim[cmd[1]]
                if cmd[0] == "select":
                    s["lvl"] = cmd[2]
                    self.notice.emit(True, tr("P%1: level %2 active").replace("%1", str(cmd[1] + 1))
                                     .replace("%2", str(cmd[2] + 1)) + " (demo)")
                elif not 90 <= cmd[3] <= 450:
                    self.notice.emit(False, f"{cmd[3]} °C outside 90…450 °C")
                else:
                    s["levels"][cmd[2]] = cmd[3]
                    self.notice.emit(True, tr("P%1: level %2 = %3 °C").replace("%1", str(cmd[1] + 1))
                                     .replace("%2", str(cmd[2] + 1)).replace("%3", str(cmd[3])) + " (demo)")
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
                            "levels": [float(x) for x in s["levels"]], "level": s["lvl"],
                            "levels_on": True})
            if t == 40:
                sim[1]["state"] = "work"
            self.data.emit(out)
            time.sleep(POLL_INTERVAL)


class Station(QObject):
    changed = Signal()
    notice = Signal(bool, str)

    def __init__(self, port=None, demo=False, write=False, control=False, open_settings=False):
        super().__init__()
        self._openSettings = open_settings
        self._writable = write
        self._connected = False
        self._message = tr("looking for station …")
        self._info = {}
        self._ports = []
        self._hist = [[] for _ in range(4)]
        self._last = 0.0
        self._settings = {}
        self._settingsBusy = False
        self._worker = Worker(port, demo, write, control)
        self._worker.notice.connect(self.notice)
        self._worker.settings.connect(self._on_settings)
        self._worker.busy.connect(self._on_busy)
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

    settingsChanged = Signal()
    settingsBusyChanged = Signal()
    languageChanged = Signal()

    # -- language (EN | DE in the header) ------------------------------------
    language_handler = None         # set by main(): applies a language code

    @Property(str, notify=languageChanged)
    def language(self):
        return getattr(self, "_language", "en")

    @Slot(str)
    def setLanguage(self, code):
        if code not in LANGUAGES or code == self.language:
            return
        self._language = code
        QSettings("jbc-dme-monitor", "gui").setValue("language", code)
        if self.language_handler:
            self.language_handler(code)
        self.languageChanged.emit()

    @Slot(dict)
    def _on_settings(self, cfg):
        self._settings = cfg
        self.settingsChanged.emit()

    @Slot(bool)
    def _on_busy(self, b):
        self._settingsBusy = b
        self.settingsBusyChanged.emit()

    @Property("QVariantMap", notify=settingsChanged)
    def settings(self):
        return self._settings

    @Property(bool, notify=settingsBusyChanged)
    def settingsBusy(self):
        return self._settingsBusy

    @Slot()
    def loadSettings(self):
        """Read all settings from the station (answer comes as settingsChanged)."""
        if self._connected:
            self._worker.submit("settings")

    @Slot("QVariant")
    def applySettings(self, cfg):
        """Write everything in cfg that differs from the station, in one session."""
        if not self._writable:
            return
        if hasattr(cfg, "toVariant"):
            cfg = cfg.toVariant()
        self._worker.submit("apply", _plain(cfg))

    # -- settings files ------------------------------------------------------
    @Property(QUrl, constant=True)
    def settingsFolder(self):
        folder = settings_file.default_folder()
        os.makedirs(folder, exist_ok=True)
        return QUrl.fromLocalFile(folder)

    @Slot(QUrl, "QVariant", result=bool)
    def saveSettingsFile(self, url, cfg):
        """Save the settings as the station reported them (`cfg`) to a file."""
        if hasattr(cfg, "toVariant"):
            cfg = cfg.toVariant()
        path = url.toLocalFile()
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            settings_file.save(path, _plain(cfg), self._info)
        except (OSError, settings_file.SettingsFileError) as e:
            self.notice.emit(False, tr("not saved: %1").replace("%1", str(e)))
            return False
        self.notice.emit(True, tr("saved: %1").replace("%1", path))
        return True

    @Slot(QUrl, "QVariant", result="QVariantMap")
    def loadSettingsFile(self, url, current):
        """Merge a file into `current` (the settings read from the station).
        Returns {"settings": merged} or {} - nothing is written here."""
        if hasattr(current, "toVariant"):
            current = current.toVariant()
        try:
            doc = settings_file.load(url.toLocalFile())
            merged, notes = settings_file.merge(_plain(current), doc["settings"])
        except (settings_file.SettingsFileError, KeyError, TypeError, AttributeError) as e:
            self.notice.emit(False, tr("not loaded: %1").replace("%1", str(e)))
            return {}
        head = tr("\u201c%1\u201d loaded - check and APPLY").replace("%1", str(doc.get("name", "")))
        texts = []
        for n in notes:
            t = (tr("P%1: no tool plugged in, %2 skipped") if n["kind"] == "no_tool"
                 else tr("P%1: file has %2, port has %3 - tool settings skipped"))
            texts.append(t.replace("%1", str(n["port"])).replace("%2", str(n["file_tool"]))
                         .replace("%3", str(n["port_tool"])))
        self.notice.emit(not notes, "; ".join([head] + texts))
        return {"settings": merged}

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

    @Property(bool, constant=True)
    def openSettings(self):
        return self._openSettings

    @Property(bool, constant=True)
    def writable(self):
        return self._writable

    @Slot(int, int)
    def selectLevel(self, port, level):
        if self._writable:
            self._worker.submit("select", port, level)

    @Slot(int, int, int)
    def setLevelTemp(self, port, level, celsius):
        if self._writable:
            self._worker.submit("temp", port, level, celsius)

    @Property(int, constant=True)
    def histLength(self):
        return int(HIST_SECONDS / POLL_INTERVAL)

    @Property(int, constant=True)
    def histSeconds(self):
        return HIST_SECONDS


def _plain(v):
    """QML values -> plain Python (JS numbers arrive as float)."""
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def main():
    ap = argparse.ArgumentParser(description="JBC DME-2A Monitor")
    ap.add_argument("--port")
    ap.add_argument("--readonly", action="store_true", help="never write to the station")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--settings", action="store_true", help="open the settings at start")
    ap.add_argument("--screenshot")
    ap.add_argument("--delay", type=float, default=8.0)
    ap.add_argument("--size", default="1280x800")
    ap.add_argument("--lang", choices=LANGUAGES, help="UI language (default: as last chosen, "
                    "else the system language)")
    args = ap.parse_args()

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("JBC DME Monitor")
    app.setWindowIcon(QIcon(os.path.join(HERE, "qml", "icon.svg")))

    # the station NACKs writes in monitor mode: every write goes :C -> 52 -> :M + reconnect
    station = Station(args.port, args.demo, write=not args.readonly, control=not args.readonly,
                      open_settings=args.settings)
    engine = QQmlApplicationEngine()

    # Language: --lang, else the last choice, else the system language. Qt 6
    # retranslates the running UI, so EN | DE switches at once.
    translator = QTranslator(app)

    def apply_language(code):
        app.removeTranslator(translator)
        if code != "en" and translator.load(f"jbc-gui_{code}", I18N):
            app.installTranslator(translator)
        QLocale.setDefault(QLocale(code))
        engine.retranslate()

    saved = QSettings("jbc-dme-monitor", "gui").value("language", "")
    lang = args.lang or (saved if saved in LANGUAGES else
                         "de" if QLocale.system().name().startswith("de") else "en")
    station._language = lang
    station.language_handler = apply_language
    apply_language(lang)
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
