"""Station settings as files - save, load, carry to another station.

The format is shared with iSoSta (the Sailfish OS app), so a file saved on the
phone loads on the PC and the other way round:

    {"format": "isosta-settings", "version": 1, "name": "...", "saved": ISO time,
     "station": {"model": ..., "sw": ..., "hw": ...},
     "settings": {"station": {...}, "ports": [...]}}     # as DME.read_settings()

Default folder: ~/Documents/iSoSta (the same as on the phone).

Loading never writes to the station: merge() fills a settings dict that is then
written with DME.apply_settings() (APPLY in the GUI). The station keeps the
levels, sleep, hibernation and adjust per tool, so those are only taken over
for ports that hold the same tool now as in the file.
"""
import copy
import datetime
import json
import os

FORMAT = "isosta-settings"
VERSION = 1

STATION_KEYS = ("name", "min_temp", "max_temp", "power_limit", "pin_enabled", "pin")
PORT_KEYS = ("locked", "set_temp")
TOOL_KEYS = ("levels_on", "level", "levels", "sleep_temp", "sleep_on", "sleep_min",
             "hiber_on", "hiber_min", "adjust")


class SettingsFileError(Exception):
    pass


def default_folder():
    return os.path.join(os.path.expanduser("~"), "Documents", "iSoSta")


def save(path, settings, info=None, name=None):
    """Write `settings` (as read_settings() returns it) to `path`."""
    if not isinstance(settings, dict) or "station" not in settings or "ports" not in settings:
        raise SettingsFileError("no settings to save")
    info = info or {}
    doc = {
        "format": FORMAT, "version": VERSION,
        "name": name or os.path.splitext(os.path.basename(path))[0],
        "saved": datetime.datetime.now().replace(microsecond=0).isoformat(),
        "station": {k: info.get(k) for k in ("model", "sw", "hw")},
        "settings": settings,
    }
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=4, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def load(path):
    """The whole file as a dict. Raises SettingsFileError if it is not ours."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise SettingsFileError(f"cannot read {path}: {e}")
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise SettingsFileError("not an iSoSta settings file")
    s = doc.get("settings")
    if not isinstance(s, dict) or not isinstance(s.get("station"), dict) \
            or not isinstance(s.get("ports"), list):
        raise SettingsFileError("not an iSoSta settings file")
    return doc


def _copy(dst, src, keys):
    for k in keys:
        if src.get(k) is not None and dst.get(k) is not None:
            dst[k] = copy.deepcopy(src[k])


def note_text(n):
    """English text of a note from merge()."""
    if n["kind"] == "no_tool":
        return f"P{n['port']}: no tool plugged in, {n['file_tool']} skipped"
    return f"P{n['port']}: file has {n['file_tool']}, port has {n['port_tool']} - tool settings skipped"


def merge(current, file_settings):
    """Settings `current` (from the station) with the values of `file_settings`
    filled in where they apply. Returns (merged, notes): notes say what was
    skipped, as dicts {"kind": "no_tool" | "other_tool", "port": 1..4,
    "file_tool", "port_tool"} (note_text() gives the English text). Only
    values the station reported are touched."""
    out = copy.deepcopy(current)
    notes = []
    _copy(out["station"], file_settings.get("station", {}), STATION_KEYS)
    for p, (op, fp) in enumerate(zip(out["ports"], file_settings.get("ports", []))):
        _copy(op, fp, PORT_KEYS)
        ft, ot = fp.get("tool_id") or 0, op.get("tool_id") or 0
        if not ft:
            continue
        note = {"port": p + 1, "file_tool": fp.get("tool"), "port_tool": op.get("tool")}
        if not ot:
            notes.append(dict(note, kind="no_tool"))
        elif ft != ot:
            notes.append(dict(note, kind="other_tool"))
        else:
            _copy(op, fp, TOOL_KEYS)
    return out, notes
