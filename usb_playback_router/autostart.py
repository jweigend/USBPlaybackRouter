"""Desktop entries: autostart at login and the application menu.

Both point at the executable that is running right now, so a checkout
launcher and a pipx installation work alike. Written and removed by the tool;
nothing is copied.
"""
import os
import shutil
import sys
from importlib import resources

from . import APP_ID
from .icons import icon_dir

CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
DATA_HOME = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
AUTOSTART = os.path.join(CONFIG_HOME, "autostart", f"{APP_ID}.desktop")
APP_MENU = os.path.join(DATA_HOME, "applications", f"{APP_ID}.desktop")


def icon_path():
    """The application icon as a file on disk. Written from the package
    resource into the cache directory, so it exists for a zipapp too."""
    path = os.path.join(icon_dir(), f"{APP_ID}.svg")
    data = resources.files(__package__).joinpath("icon.svg").read_bytes()
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return path
    except OSError:
        pass
    with open(path, "wb") as f:
        f.write(data)
    return path


def executable():
    exe = sys.argv[0] if sys.argv else ""
    if exe and os.path.basename(exe) != "__main__.py":
        return os.path.realpath(exe)
    return shutil.which(APP_ID) or exe


def desktop_entry(autostart):
    lines = ["[Desktop Entry]", "Type=Application", "Name=USB Playback Router",
             "Comment=Choose which USB stereo pair of the mixer receives desktop audio",
             f"Exec={executable()}", f"Icon={icon_path()}", "Terminal=false",
             "Categories=AudioVideo;Audio;"]
    if autostart:
        lines += ["X-GNOME-Autostart-enabled=true", "X-GNOME-Autostart-Delay=5"]
    return "\n".join(lines) + "\n"


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def enabled():
    return os.path.exists(AUTOSTART)


def set_enabled(on):
    """Enable: autostart entry plus application-menu entry. Disable: remove
    the autostart entry only; the menu entry stays until `uninstall`."""
    if on:
        _write(AUTOSTART, desktop_entry(autostart=True))
        _write(APP_MENU, desktop_entry(autostart=False))
    else:
        try:
            os.remove(AUTOSTART)
        except FileNotFoundError:
            pass
    return enabled()


def remove_all():
    for path in (AUTOSTART, APP_MENU):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
