# JBC DME-2A Monitor

Reads a JBC DME-2A soldering station over its USB-B port and shows all four ports
live: tip and set temperature, temperature levels, state, power, history.
The station stays fully usable. The monitor only changes something when you
ask for it: the temperature levels right in the tiles, everything else under
**SETTINGS** (see below). `--readonly` turns writing off completely.

![P1 heating up](screenshots/live-working.png)

![All tools idle](screenshots/live-idle.png)

## Run

```sh
pip install -r requirements.txt
./jbc-gui.sh                  # find the station automatically
./jbc-gui.sh --port /dev/ttyACM0
./jbc-gui.sh --demo           # without a station
./jbc-gui.sh --readonly       # never write to the station
./jbc-gui.sh --settings       # open the settings right away
./jbc-gui.sh --lang de        # German UI (also EN | DE top right, remembered)
```

### Temperature levels

| Action | Effect |
|---|---|
| Double click on a level | makes it the active level |
| Ctrl+Shift+mouse wheel on the **active** level | ±5 °C per notch, sent 0.7 s after the last notch |

The mouse has to be on the level. Without Ctrl+Shift the wheel does nothing.
Values are limited to the station's min/max temperature. After writing, the
levels are read back. A short message confirms or reports the error.

The UI is in English or German: **EN | DE** at the top right switches at
once and is remembered; the first start follows the system language.
Translations: `i18n/` (`translate_de.py` fills the .ts and builds the .qm).

### Settings

**SETTINGS** at the top right opens the settings that the station menu offers
and the USB protocol can reach:

| Page | Settings |
|---|---|
| Station | name, min./max. temperature, power limit, PIN lock and PIN; info: transformer temperature, station error, device ID |
| P1…P4 | port lock, set temperature, levels (on/off, enabled, temperature, active level), sleep temperature, sleep delay, hibernation delay, temperature adjust |

Changed values turn amber. **APPLY** writes all changes in one go (control
mode, a few seconds), then reads everything back and reports what was written
or refused. **UNDO** discards the changes, closing the panel too.
Level, sleep, hibernation and adjust are stored per tool type, so they can
only be edited for the tool that is plugged into the port.
Language, units, display and robot settings are not reachable over USB.

**SAVE …** writes the settings as the station reports them to a JSON file
(default folder `~/Documents/iSoSta`), **LOAD …** fills the form from such a
file — to undo a mistake or to carry the settings to another station. Nothing
is written before **APPLY**. Tool settings are only taken over for ports that
hold the same tool as in the file; the rest is reported. The format is shared
with the iSoSta Sailfish OS app (`settings_file.py`), so files move freely
between phone and PC.

Access to `/dev/ttyACM*` via the `uucp` or `dialout` group.

## Library

```python
import jbc_dme
d = jbc_dme.DME()
print(d.connect())
for p in d.read_all():
    print(p["port"], p["tool"], p["state"], p["temp"], p["set"])
d.close()
```

`jbc_dme.py` has no dependencies. By default it only sends read commands;
`DME(allow_write=True, control=True)` additionally allows
`set_level_temp(port, level, °C)`, `select_level(port, level)` (ports and
levels count from 0) and, for all settings:

```python
cfg = d.read_settings()                # {"station": {...}, "ports": [...]}
cfg["ports"][1]["sleep_temp"] = 180
back, written, errors = d.apply_settings(cfg)
```
Protocol: [PROTOCOL.md](PROTOCOL.md).

## Tools

```sh
python3 tools/jbc_probe.py                  # identification + raw data
python3 tools/jbc_monitor.py --csv log.csv  # logging
```

## Tested

DME-2A (`DME_TCH_04`, SW 8886937) with T210, T245, PA, DT530.

## Note

JBC is a trademark of JBC Soldering S.L. Not affiliated with JBC; contains no code
or files from JBC.

## License

MIT

LLM assisted development
