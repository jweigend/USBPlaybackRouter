#!/bin/bash
# build.sh — single-file executable dist/usb-playback-router.pyz (Python zipapp).
#
# The file contains the package only; it still needs the system packages
# (`usb-playback-router check` lists them). Run it directly or drop it into
# ~/.local/bin as usb-playback-router.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import usb_playback_router as m; print(m.__version__)' "$HERE")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/src" "$HERE/dist"
cp -r "$HERE/usb_playback_router" "$STAGE/src/"
find "$STAGE/src" -name __pycache__ -type d -exec rm -rf {} +
OUT="$HERE/dist/usb-playback-router-$VERSION.pyz"
python3 -m zipapp "$STAGE/src" -m "usb_playback_router.cli:main" -p "/usr/bin/env python3" -c -o "$OUT"
ln -sfn "$(basename "$OUT")" "$HERE/dist/usb-playback-router.pyz"
echo "built: $OUT ($(du -h "$OUT" | cut -f1))"
