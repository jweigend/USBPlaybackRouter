"""State icons, generated as SVG into the user's cache directory.

One icon per stereo pair ("1·2", "3·4", …) plus warning and offline. Files
are written once per start; tray backends get either the path (XApp) or the
directory as icon theme path and the file stem as icon name (AppIndicator).
"""
import os

from . import APP_ID

PALETTE = ["#e07b1a", "#2e9e5b", "#2f6fd6", "#8e44ad", "#c48a00", "#0f9aa5", "#a0522d", "#5b6c8f"]
WARNING = "#c9302c"
OFFLINE = "#7d7d7d"

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">\n'
       '  <rect x="1" y="3" width="22" height="18" rx="4" fill="{fill}"/>\n'
       '  <text x="12" y="12.6" text-anchor="middle" dominant-baseline="central" '
       'font-family="Noto Sans, DejaVu Sans, sans-serif" font-weight="bold" font-size="{size}" '
       'fill="#ffffff">{text}</text>\n</svg>\n')


def icon_dir():
    base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    d = os.path.join(base, APP_ID, "icons")
    os.makedirs(d, exist_ok=True)
    return d


def _write(name, fill, text, size):
    path = os.path.join(icon_dir(), f"{APP_ID}-{name}.svg")
    content = SVG.format(fill=fill, text=text, size=size)
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                return path
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def pair_icon(pair):
    a, b = pair.channels
    text = f"{a}·{b}"
    size = 12 if b < 10 else 8.5
    return _write(f"pair-{a}-{b}", PALETTE[pair.index % len(PALETTE)], text, size)


def warning_icon():
    return _write("warning", WARNING, "!", 15)


def offline_icon():
    return _write("offline", OFFLINE, "–", 15)


def icon_name(path):
    """Icon-theme name for AppIndicator: file stem."""
    return os.path.splitext(os.path.basename(path))[0]
