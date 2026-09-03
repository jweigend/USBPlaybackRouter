#!/bin/bash
# install.sh [remove] — run from a checkout without pip: symlink into
# ~/.local/bin and enable autostart. With pipx, use instead:
#   pipx install .   (or pipx install git+https://github.com/jweigend/USBPlaybackRouter)
#   usb-playback-router autostart on
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin/usb-playback-router"
if [[ "${1:-}" == "remove" ]]; then
    "$HERE/usb-playback-router" uninstall
    rm -f "$BIN"
    pkill -u "$USER" -f "$HERE/usb-playback-router" 2>/dev/null || true
    echo "removed: $BIN"
    exit 0
fi
mkdir -p "$(dirname "$BIN")"
ln -sfn "$HERE/usb-playback-router" "$BIN"
"$BIN" autostart on
echo "installed: $BIN -> $HERE/usb-playback-router"
echo "start now: usb-playback-router &"
