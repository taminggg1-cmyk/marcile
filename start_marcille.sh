#!/usr/bin/env bash
# Launch Marcille on Linux / macOS.
# Requires: python3 + pip install pillow  (see README).
# Optional Linux helpers for the full experience:
#   xprintidle (idle detection), xdotool (active window),
#   playerctl (media keys), and a compositing window manager for clean
#   transparency (Marcille's cutout look). Without a compositor she shows
#   on a flat backdrop.
cd "$(dirname "$0")" || exit 1
exec python3 marcille.py "$@"
