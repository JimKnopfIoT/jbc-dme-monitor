#!/usr/bin/env python3
"""Poll a JBC DME-2A and log it as text/CSV (read-only).

Usage: python3 tools/jbc_monitor.py [--port /dev/ttyACM0] [--seconds 120] [--csv file.csv]

One line per sample (twice per second): time and, for each port, tool, state,
tip/set temperature and power. With --csv also machine-readable.
"""
import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jbc_dme  # noqa: E402


def fmt(v, nd=0):
    return "-" if v is None else f"{v:.{nd}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port")
    ap.add_argument("--seconds", type=float, default=120)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--csv")
    a = ap.parse_args()

    d = jbc_dme.DME(a.port)
    info = d.connect()
    print(f"# {time.strftime('%F %T')} {info['model']} SW {info['sw']} HW {info['hw']} ({info['port']})")
    w = None
    if a.csv:
        f = open(a.csv, "a", newline="")
        w = csv.writer(f)
        if f.tell() == 0:
            w.writerow(["time", "port", "tool", "state", "status", "temp", "set", "power", "level"])
    try:
        end = time.monotonic() + a.seconds
        while time.monotonic() < end:
            t0 = time.monotonic()
            ports = d.read_all()
            ts = time.strftime("%T")
            print(ts + " | " + " | ".join(
                f"P{p['port']} {p['tool'] or '-':6s} {p['state']:5s} {fmt(p['temp']):>4s}/{fmt(p['set']):>3s} "
                f"{fmt(p['power'], 1):>5s}%" for p in ports), flush=True)
            if w:
                for p in ports:
                    w.writerow([ts, p["port"], p["tool"], p["state"], p["status"], fmt(p["temp"], 1),
                                fmt(p["set"]), fmt(p["power"], 1), p["level"]])
            time.sleep(max(0.0, a.interval - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        pass
    finally:
        d.close()


if __name__ == "__main__":
    main()
