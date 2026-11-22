#!/bin/sh
# Start the JBC DME-2A Monitor (read-only). Options: --port /dev/ttyACMx, --demo
cd "$(dirname "$0")" && exec python3 jbc_gui.py "$@"
