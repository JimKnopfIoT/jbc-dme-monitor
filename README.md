# JBC DME-2A Monitor

Liest eine JBC DME-2A über USB-B aus und zeigt die vier Ports live an:
Ist-/Solltemperatur, Stufen, Zustand, Leistung, Verlauf. Nur lesend, die Station
bleibt bedienbar.

![P1 heizt auf](screenshots/live-working.png)

![Alle Tools in Ruhe](screenshots/live-idle.png)

## Start

```sh
pip install -r requirements.txt
./jbc-gui.sh                  # Station automatisch suchen
./jbc-gui.sh --port /dev/ttyACM0
./jbc-gui.sh --demo           # ohne Station
```

Zugriff auf `/dev/ttyACM*` über die Gruppe `uucp` bzw. `dialout`.

## Bibliothek

```python
import jbc_dme
d = jbc_dme.DME()
print(d.connect())
for p in d.read_all():
    print(p["port"], p["tool"], p["state"], p["temp"], p["set"])
d.close()
```

`jbc_dme.py` hat keine Abhängigkeiten und sendet nur Lesekommandos.
Protokoll: [PROTOCOL.md](PROTOCOL.md).

## Werkzeuge

```sh
python3 tools/jbc_probe.py                  # Kennung + Rohdaten
python3 tools/jbc_monitor.py --csv log.csv  # Mitschnitt
```

## Getestet

DME-2A (`DME_TCH_04`, SW 8886937) mit T210, T245, PA, DT530.

## Hinweis

JBC ist eine Marke der JBC Soldering S.L. Kein Bezug zu JBC, enthält keinen Code
oder Dateien von JBC.

## Lizenz

MIT

LLM assisted development
