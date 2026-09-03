"""User configuration and the optional device knowledge database.

~/.config/usb-playback-router.conf (INI):

    [device]
    name = alsa_card.usb-...        ; optional, auto-detected otherwise

    [source]
    node = rec-bus-abhoere-out      ; source mode: relink this node's outputs

    [labels]                        ; optional overrides, per pair
    3/4 = USB 3/4 – Kanalzug 15/16

    [hints]
    1/2 = Am Pult Zug 15/16 stumm schalten!
"""
import configparser
import os
import tomllib
from dataclasses import dataclass, field
from importlib import resources

from . import APP_ID

DEFAULT_PATH = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                            f"{APP_ID}.conf")


@dataclass
class Config:
    path: str = DEFAULT_PATH
    device: str = ""
    source_node: str = ""
    labels: dict = field(default_factory=dict)
    hints: dict = field(default_factory=dict)

    @property
    def mode(self):
        return "source" if self.source_node else "session"

    @classmethod
    def load(cls, path=None):
        cfg = cls(path=path or DEFAULT_PATH)
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        try:
            cp.read(cfg.path, encoding="utf-8")
        except (OSError, configparser.Error):
            return cfg
        cfg.device = cp.get("device", "name", fallback="").strip()
        cfg.source_node = cp.get("source", "node", fallback="").strip()
        cfg.labels = dict(cp["labels"]) if cp.has_section("labels") else {}
        cfg.hints = dict(cp["hints"]) if cp.has_section("hints") else {}
        return cfg


class DeviceDB:
    """devices.toml shipped with the package, or a file given as `path`.
    Read as a package resource so it also works from a zipapp."""

    def __init__(self, path=None):
        try:
            if path:
                with open(path, "rb") as f:
                    data = f.read()
            else:
                data = resources.files(__package__).joinpath("devices.toml").read_bytes()
            self.entries = tomllib.loads(data.decode("utf-8")).get("devices", [])
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            self.entries = []

    def lookup(self, device):
        """Entry for an AudioDevice, or {}."""
        if device is None:
            return {}
        for e in self.entries:
            m = e.get("match", {})
            if not m:
                continue
            ok = True
            for key, value in (("vendor", device.vendor), ("product", device.product), ("name", device.id)):
                want = m.get(key)
                if want and want.lower() not in (value or "").lower():
                    ok = False
            if ok:
                return e
        return {}


class Labels:
    """Label and hint resolution: user config > device database > generic."""

    def __init__(self, config, db, device):
        self.config = config
        self.entry = db.lookup(device)

    def device_name(self, device):
        return self.entry.get("name") or (device.name if device else "")

    def label(self, pair):
        return (self.config.labels.get(pair.key)
                or self.entry.get("labels", {}).get(pair.key)
                or pair.generic_label)

    def hint(self, pair):
        return self.config.hints.get(pair.key) or self.entry.get("hints", {}).get(pair.key) or ""
