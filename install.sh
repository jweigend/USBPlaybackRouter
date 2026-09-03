#!/bin/bash
# install.sh [remove] — put the tray icon into PATH and autostart.
# Nothing is copied: ~/.local/bin/usb-playback-router is a symlink into this
# checkout and the autostart entry runs the script from here.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin/usb-playback-router"
AUTO="$HOME/.config/autostart/usb-playback-router.desktop"
if [[ "${1:-}" == "remove" ]]; then
    rm -f "$BIN" "$AUTO"
    pkill -f "$HERE/usb-playback-router" 2>/dev/null || true
    echo "removed: $BIN, $AUTO"
    exit 0
fi
mkdir -p "$(dirname "$BIN")" "$(dirname "$AUTO")"
ln -sfn "$HERE/usb-playback-router" "$BIN"
sed "s|@HERE@|$HERE|g" "$HERE/usb-playback-router.desktop" > "$AUTO"
echo "installed: $BIN -> $HERE/usb-playback-router"
echo "autostart: $AUTO"
echo "start now: usb-playback-router &"
