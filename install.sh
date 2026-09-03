#!/bin/bash
# install.sh [remove] — run from a checkout: check the system packages,
# symlink into ~/.local/bin, enable autostart. Nothing is copied and nothing
# is installed with root; missing packages are reported with the apt command.
#
# Without a checkout use pipx instead:
#   pipx install git+https://github.com/jweigend/USBPlaybackRouter
#   usb-playback-router check && usb-playback-router autostart on
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
if ! command -v python3 >/dev/null; then
    echo "missing  python3 (3.11 or newer)"; exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "missing  python3 3.11 or newer (found $(python3 --version 2>&1))"; exit 1
fi
"$HERE/usb-playback-router" check || exit 1
mkdir -p "$(dirname "$BIN")"
ln -sfn "$HERE/usb-playback-router" "$BIN"
"$BIN" autostart on
echo "installed: $BIN -> $HERE/usb-playback-router"
echo "start now: usb-playback-router &"
