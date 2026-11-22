#!/bin/sh
# JBC DME-2A Monitor starten (nur lesend). Optionen: --port /dev/ttyACMx, --demo
cd "$(dirname "$0")" && exec python3 jbc_gui.py "$@"
