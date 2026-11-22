#!/usr/bin/env python3
"""One-shot query of a JBC DME-2A with raw data (read-only).

Connects, reads the identification and, for every port, the raw replies to
48 (INF_PORT), 80 (SELECTTEMP), 82 (TIPTEMP) and 51 (LEVELSTEMPS).
Meant for checking the field layout, see PROTOCOL.md.

Usage: python3 tools/jbc_probe.py [/dev/ttyACM0]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jbc_dme  # noqa: E402


def main():
    d = jbc_dme.DME(sys.argv[1] if len(sys.argv) > 1 else None)
    info = d.connect()
    print(f"Station: {info['model']}  SW {info['sw']}  HW {info['hw']}  protocol {info['protocol']}  ({info['port']})")
    print(f"Addresses: station 0x{d.st:02x}, PC 0x{d.pc:02x}")
    try:
        usb = d.request(jbc_dme.CMD_R_USB_CONNECTSTATUS)
        print(f"USB connect status (224): {usb!r}")
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
            print(f"  -> {r['tool'] or 'no tool'}, {r['state']}, tip {r['temp']}, set {r['set']}, "
                  f"power {r['power']} %, levels {r['levels']} active {r['level']}")
    finally:
        d.close()


if __name__ == "__main__":
    main()
