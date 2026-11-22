#!/usr/bin/env python3
"""Einmalige Abfrage einer JBC DME-2A mit Rohdaten (nur lesend).

Verbindet, liest die Kennung und fragt fuer jeden Port die Rohantworten von
48 (INF_PORT), 80 (SELECTTEMP), 82 (TIPTEMP) und 51 (LEVELSTEMPS) ab.
Gedacht zum Nachpruefen der Feldzuordnung, siehe PROTOCOL.md.

Aufruf: python3 tools/jbc_probe.py [/dev/ttyACM0]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jbc_dme  # noqa: E402


def main():
    d = jbc_dme.DME(sys.argv[1] if len(sys.argv) > 1 else None)
    info = d.connect()
    print(f"Station: {info['model']}  SW {info['sw']}  HW {info['hw']}  Protokoll {info['protocol']}  ({info['port']})")
    print(f"Adressen: Station 0x{d.st:02x}, PC 0x{d.pc:02x}")
    try:
        usb = d.request(jbc_dme.CMD_R_USB_CONNECTSTATUS)
        print(f"USB-Verbindungsstatus (224): {usb!r}")
        for p in range(4):
            inf = d.request(jbc_dme.CMD_INF_PORT, bytes([p]))
            sel = d.request(jbc_dme.CMD_R_SELECTTEMP, bytes([p]))
            tip = d.request(jbc_dme.CMD_R_TIPTEMP, bytes([p]))
            tool = inf[0] if inf else 0
            lv = d.request(jbc_dme.CMD_R_LEVELSTEMPS, bytes([p, tool])) if tool else None
            print(f"\nPort {p + 1}")
            for name, raw in (("48 INF_PORT", inf), ("80 SELECTTEMP", sel),
                              ("82 TIPTEMP", tip), ("51 LEVELSTEMPS", lv)):
                print(f"  {name:15s} {raw.hex(' ') if raw else '-'}")
            r = d.read_port(p)
            print(f"  -> {r['tool'] or 'kein Tool'}, {r['state']}, Ist {r['temp']}, Soll {r['set']}, "
                  f"Leistung {r['power']} %, Stufen {r['levels']} aktiv {r['level']}")
    finally:
        d.close()


if __name__ == "__main__":
    main()
