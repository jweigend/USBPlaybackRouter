"""Remembered selection for session mode (the only state the router stores).

Source mode never needs it: the state is in the links of a node somebody else
owns. Session mode has to recreate its node after a reconnect and therefore
remembers which pair the user chose, per device.
"""
import configparser
import os

from . import APP_ID

STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), APP_ID)
STATE_PATH = os.path.join(STATE_DIR, "state.ini")


def load(path=STATE_PATH):
    """{device_id: pair_key}"""
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return {}
    return dict(cp["last-pair"]) if cp.has_section("last-pair") else {}


def save(device_id, pair_key, path=STATE_PATH):
    data = load(path)
    data[device_id] = pair_key
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp["last-pair"] = data
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            cp.write(f)
    except OSError:
        pass
