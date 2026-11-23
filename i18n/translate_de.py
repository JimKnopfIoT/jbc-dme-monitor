#!/usr/bin/env python3
"""Fill the German translations into i18n/jbc-gui_de.ts and build the .qm.

The translations live here as an English -> German table, because lupdate
rewrites the .ts on every run:

    /usr/lib/qt6/bin/lupdate jbc_gui.py qml/*.qml qml/Theme.js -ts i18n/jbc-gui_de.ts
    python3 i18n/translate_de.py          # fills the .ts and runs lrelease

Terms match the iSoSta phone app.
"""
import html
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TS = os.path.join(HERE, "jbc-gui_de.ts")
LRELEASE = os.environ.get("LRELEASE", "/usr/lib/qt6/bin/lrelease")

DE = {
    "nothing to write": "nichts zu schreiben",
    "P%1: level %2 active": "P%1: Stufe %2 aktiv",
    "P%1: level %2 = %3 °C": "P%1: Stufe %2 = %3 °C",
    "looking for station …": "suche die Station …",
    "not saved: %1": "nicht gespeichert: %1",
    "saved: %1": "gespeichert: %1",
    "not loaded: %1": "nicht geladen: %1",
    "“%1” loaded - check and APPLY": "„%1“ geladen – prüfen und ÜBERNEHMEN",
    "P%1: no tool plugged in, %2 skipped": "P%1: kein Werkzeug eingesteckt, %2 übersprungen",
    "P%1: file has %2, port has %3 - tool settings skipped":
        "P%1: Datei hat %2, Port hat %3 – Werkzeug-Einstellungen übersprungen",
    "JBC DME-2A Monitor": "JBC DME-2A Monitor",
    "CONNECTED": "VERBUNDEN",
    "OFFLINE": "GETRENNT",
    "Connect the station via USB-B": "Station über USB-B anschließen",
    "SETTINGS": "EINSTELLUNGEN",
    "EDITABLE": "ÄNDERBAR",
    "READ-ONLY": "NUR LESEN",
    "History %1 min  ·  polling 2×/s": "Verlauf %1 min  ·  Abfrage 2×/s",
    "level: double click = activate, Ctrl+Shift+wheel = ±5 °C  ·  more under SETTINGS":
        "Stufe: Doppelklick = aktivieren, Strg+Umschalt+Rad = ±5 °C  ·  mehr unter EINSTELLUNGEN",
    "monitor only, the station stays usable": "nur Anzeige, die Station bleibt bedienbar",
    "Set –": "Soll –",
    "Set %1 °C": "Soll %1 °C",
    "Levels": "Stufen",
    "Power": "Leistung",
    "not connected": "nicht verbunden",
    "%1 min": "%1 min",
    "Settings": "Einstellungen",
    "written to the station only with APPLY": "wird erst mit ÜBERNEHMEN in die Station geschrieben",
    "read-only (started with --readonly)": "nur lesen (gestartet mit --readonly)",
    "STATION": "STATION",
    "station not connected": "Station nicht verbunden",
    "reading settings …": "lese Einstellungen …",
    "writing … (control mode, takes a few seconds)": "schreibe … (Steuermodus, dauert einige Sekunden)",
    "no changes": "keine Änderungen",
    "SAVE …": "SPEICHERN …",
    "LOAD …": "LADEN …",
    "RELOAD": "NEU LESEN",
    "UNDO": "VERWERFEN",
    "APPLY": "ÜBERNEHMEN",
    "Save station settings": "Stationseinstellungen speichern",
    "iSoSta settings (*.json)": "iSoSta-Einstellungen (*.json)",
    "All files (*)": "Alle Dateien (*)",
    "Load station settings": "Stationseinstellungen laden",
    "Name": "Name",
    "max. 16 characters": "max. 16 Zeichen",
    "Min. temperature": "Min. Temperatur",
    "lower limit for all set points": "Untergrenze aller Sollwerte",
    "Max. temperature": "Max. Temperatur",
    "upper limit for all set points": "Obergrenze aller Sollwerte",
    "Power limit": "Leistungsgrenze",
    "30 … 160 W": "30 … 160 W",
    "PIN": "PIN",
    "PIN lock": "PIN-Sperre",
    "the station menu asks for the PIN (default 0105)": "das Stationsmenü fragt nach der PIN (Standard 0105)",
    "4 digits": "4 Ziffern",
    "INFO": "INFO",
    "Transformer temperature": "Trafotemperatur",
    "Station error": "Stationsfehler",
    "none": "keiner",
    "code %1": "Code %1",
    "Device ID": "Geräte-ID",
    "Language, units, display and robot settings exist only in the station menu; the USB protocol "
    "of the DME offers no command for them.":
        "Sprache, Einheiten, Anzeige und Roboter gibt es nur im Stationsmenü; das USB-Protokoll "
        "der DME hat dafür keinen Befehl.",
    "PORT %1": "PORT %1",
    "Port locked": "Port gesperrt",
    "a locked port does not heat": "ein gesperrter Port heizt nicht",
    "Set temperature": "Solltemperatur",
    "applies when levels are off": "gilt, wenn die Stufen aus sind",
    "No tool in this port. Levels, sleep, hibernation and adjust are stored per tool type; "
    "plug in the tool to edit them.":
        "Kein Werkzeug in diesem Port. Stufen, Sleep, Hibernation und Abgleich gelten je "
        "Werkzeugtyp; zum Bearbeiten das Werkzeug einstecken.",
    "LEVELS": "STUFEN",
    "choose the active level with the dot": "aktive Stufe mit dem Punkt wählen",
    "Level %1": "Stufe %1",
    "active": "aktiv",
    "SLEEP / HIBERNATION": "SLEEP / HIBERNATION",
    "Sleep temperature": "Sleep-Temperatur",
    "Sleep delay": "Sleep-Verzögerung",
    "tool in the stand → sleep": "Werkzeug in der Ablage → Sleep",
    "Hibernation delay": "Hibernation-Verzögerung",
    "sleep → heater off": "Sleep → Heizung aus",
    "CALIBRATION": "ABGLEICH",
    "Temperature adjust": "Temperaturabgleich",
    "offset for this tool, ±50 °C": "Offset für dieses Werkzeug, ±50 °C",
    "WORKING": "ARBEIT",
    "STAND": "ABLAGE",
    "SLEEP": "SLEEP",
    "HIBERNATION": "HIBERNATION",
    "ERROR": "FEHLER",
    "NO TOOL": "KEIN WERKZEUG",
}
# German: one and everything else
DE_PLURAL = {
    "%n setting(s) written": ["%n Einstellung geschrieben", "%n Einstellungen geschrieben"],
    "%n setting(s) written (demo)": ["%n Einstellung geschrieben (Demo)", "%n Einstellungen geschrieben (Demo)"],
    "%n value(s) changed, not written yet": ["%n Wert geändert, noch nicht geschrieben",
                                             "%n Werte geändert, noch nicht geschrieben"],
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    text = open(TS, encoding="utf-8").read()
    m = re.search(r"<TS\b([^>]*)>", text)
    if m and "language=" not in m.group(1):
        text = text.replace(m.group(0), '<TS%s language="de_DE">' % m.group(1), 1)
    missing, used = [], set()
    pat = re.compile(r"(<message(?: numerus=\"yes\")?>\s*(?:<location[^>]*/>\s*)*<source>)(.*?)"
                     r"(</source>\s*)(<translation[^>]*>)(.*?)(</translation>)", re.S)

    def repl(mm):
        if "obsolete" in mm.group(4) or "vanished" in mm.group(4):
            return mm.group(0)
        src = html.unescape(mm.group(2))
        if "%n" in src:
            forms = DE_PLURAL.get(src)
            if forms is None:
                missing.append(src)
                return mm.group(0)
            body = "".join("<numerusform>%s</numerusform>" % esc(f) for f in forms)
            # lupdate does not see the count in Python's tr() wrapper: mark it here
            head = mm.group(1).replace("<message>", '<message numerus="yes">', 1)
            used.add(src)
            return "%s%s%s<translation>%s</translation>" % (head, mm.group(2), mm.group(3), body)
        else:
            if src not in DE:
                missing.append(src)
                return mm.group(0)
            body = esc(DE[src])
        used.add(src)
        return "%s%s%s<translation>%s</translation>" % (mm.group(1), mm.group(2), mm.group(3), body)

    text = pat.sub(repl, text)
    open(TS, "w", encoding="utf-8").write(text)
    for s in missing:
        print("MISSING:", repr(s))
    stale = (set(DE) | set(DE_PLURAL)) - used
    for s in sorted(stale):
        print("stale:", repr(s))
    print(f"{len(used)} translated, {len(missing)} missing, {len(stale)} stale")
    subprocess.run([LRELEASE, TS, "-qm", os.path.join(HERE, "jbc-gui_de.qm")], check=True)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
