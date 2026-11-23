#!/bin/sh
# Start the JBC DME-2A Monitor. Options: --port /dev/ttyACMx, --readonly, --demo
cd "$(dirname "$0")" && exec python3 jbc_gui.py "$@"
